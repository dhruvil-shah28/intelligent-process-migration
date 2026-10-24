#!/usr/bin/env python3
"""Local API bridge for the existing cgroup monitor and runc controller."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONITOR_SCRIPT = PROJECT_ROOT / "monitor" / "cgroup-monitor.sh"
CONTROLLER_SCRIPT = PROJECT_ROOT / "controller" / "migrate.sh"
CONFIG_FILE = PROJECT_ROOT / "monitor" / "config.conf"
SOURCE_BUNDLE = PROJECT_ROOT / "migration" / "runc-source-bundle"
DESTINATION_BUNDLE = PROJECT_ROOT / "migration" / "runc-destination-bundle"
WORKLOAD_CONTEXT = PROJECT_ROOT / "workloads"
WORKLOAD_DOCKERFILE = WORKLOAD_CONTEXT / "Dockerfile"
WORKLOAD_IMAGE = "ipm-workload:local"
DEFAULT_CGROUP_BASE = Path(
    "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/"
    "app-org.kde.konsole-33815.scope"
)
SOURCE_ID = "migration-source"
DESTINATION_ID = "migration-restored"
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}

state_lock = threading.RLock()
monitor_process: subprocess.Popen[str] | None = None
monitor_active = False
migration_active = False
load_process: subprocess.Popen[str] | None = None
event_log: deque[dict[str, str]] = deque(maxlen=1000)
cpu_previous: tuple[int, float] | None = None
restore_log_offset = 0


def add_event(message: str, level: str = "info") -> None:
    with state_lock:
        event_log.appendleft({"time": time.strftime("%H:%M:%S"), "message": message[:500], "level": level})


def read_config() -> dict[str, Any]:
    values: dict[str, str] = {}
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    except OSError as exc:
        add_event(f"Unable to read monitor config: {exc}", "error")
    return {
        "cpu_threshold": float(values.get("CPU_THRESHOLD", "50")),
        "memory_threshold": float(values.get("MEMORY_THRESHOLD", "70")),
        "check_interval": max(1, int(float(values.get("CHECK_INTERVAL", "2")))),
        "auto_migrate": values.get("AUTO_MIGRATE", "false").lower() == "true",
    }


def cgroup_path(source_pid: int | None = None, container_id: str = SOURCE_ID) -> Path:
    configured_base = os.environ.get("IPM_CGROUP_BASE")
    if configured_base:
        base = Path(configured_base)
    elif source_pid and sys.platform.startswith("linux"):
        try:
            for line in (Path("/proc") / str(source_pid) / "cgroup").read_text(encoding="ascii").splitlines():
                hierarchy, _, relative = line.partition("::")
                if hierarchy == "0" and relative:
                    return Path("/sys/fs/cgroup") / relative.lstrip("/")
        except OSError:
            pass
        base = DEFAULT_CGROUP_BASE
    else:
        base = DEFAULT_CGROUP_BASE
    return base / container_id


def bundle_rootfs(bundle: Path) -> Path | None:
    try:
        specification = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
        root_path = (bundle / specification["root"]["path"]).resolve()
        root_path.relative_to(bundle.resolve())
        return root_path
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def bundle_ready(bundle: Path) -> bool:
    rootfs = bundle_rootfs(bundle)
    return (bundle / "config.json").is_file() and rootfs is not None and rootfs.is_dir()


def require_linux_root() -> str | None:
    if not sys.platform.startswith("linux"):
        return "This operation must run on the Linux migration host."
    if os.geteuid() != 0:
        return "Run the local API bridge as root on Linux so it can manage runc, cgroups, and the controller."
    return None


def capture_process_output(process: subprocess.Popen[str], label: str) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        message = line.rstrip()
        if message:
            add_event(f"{label}{message}", "error" if "[ERROR]" in message else "info")
    process.stdout.close()


def tail_restore_output() -> None:
    global restore_log_offset
    restore_log = PROJECT_ROOT / "migration" / "checkpoint-work" / "restore-console.log"
    try:
        with restore_log.open("rb") as output:
            size = output.seek(0, os.SEEK_END)
            if size < restore_log_offset:
                restore_log_offset = 0
            output.seek(restore_log_offset)
            chunk = output.read()
            restore_log_offset = output.tell()
        for line in chunk.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                add_event(f"[RESTORE] {line}", "error" if "error" in line.lower() else "info")
    except OSError:
        return


def read_usage_usec(path: Path) -> int | None:
    try:
        for line in (path / "cpu.stat").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(" ")
            if key == "usage_usec":
                return int(value)
    except (OSError, ValueError):
        return None
    return None


def read_memory_mb(path: Path) -> float | None:
    try:
        return int((path / "memory.current").read_text(encoding="ascii").strip()) / (1024 * 1024)
    except (OSError, ValueError):
        return None


def runc_state(container_id: str) -> dict[str, Any]:
    runc = shutil.which("runc")
    if not runc:
        return {"status": "unavailable", "error": "runc is not installed or not on PATH."}

    base_command = [runc, "state", container_id]
    commands = [base_command] if os.name != "posix" or os.geteuid() == 0 else [["sudo", "-n", *base_command], base_command]
    last_error = "Container state could not be read."
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
            continue
        if result.returncode == 0:
            try:
                raw = json.loads(result.stdout)
                return {
                    "id": raw.get("id", container_id),
                    "status": raw.get("status", "unknown"),
                    "pid": raw.get("pid"),
                    "bundle": raw.get("bundle"),
                }
            except json.JSONDecodeError:
                last_error = "runc returned invalid JSON."
        else:
            last_error = (result.stderr or result.stdout or last_error).strip()[-500:]
    if "does not exist" in last_error.lower() or "not found" in last_error.lower():
        return {"id": container_id, "status": "stopped", "pid": None}
    return {"id": container_id, "status": "unavailable", "error": last_error}


def controller_is_authorized() -> bool:
    if os.name == "posix" and os.geteuid() == 0:
        return True
    sudo = shutil.which("sudo")
    if not sudo:
        return False
    try:
        result = subprocess.run(
            [sudo, "-n", "-l", str(CONTROLLER_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def monitor_is_running() -> bool:
    global monitor_process, monitor_active, migration_active
    with state_lock:
        process = monitor_process
        if process is None:
            return False
        return_code = process.poll()
        if return_code is None:
            return True
        monitor_process = None
        monitor_active = False
        migration_active = False
    was_requested_stop = return_code in {-15, 143}
    add_event(f"Live monitor exited with code {return_code}.", "info" if return_code == 0 or was_requested_stop else "error")
    return False


def collect_status() -> dict[str, Any]:
    global cpu_previous
    source = runc_state(SOURCE_ID)
    destination = runc_state(DESTINATION_ID)
    active_container = source if source.get("status") == "running" else destination if destination.get("status") == "running" else source
    active_id = DESTINATION_ID if active_container is destination else SOURCE_ID
    path = cgroup_path(active_container.get("pid"), active_id)
    tail_restore_output()
    config = read_config()
    now = time.monotonic()
    usage = read_usage_usec(path)
    memory_mb = read_memory_mb(path)
    cpu_percent: float | None = None
    with state_lock:
        if usage is not None and cpu_previous is not None:
            previous_usage, previous_time = cpu_previous
            elapsed = now - previous_time
            if elapsed > 0:
                cpu_percent = max(0.0, (usage - previous_usage) / (elapsed * 10_000))
        if usage is not None:
            cpu_previous = (usage, now)

    cpu_file = path / "cpu.stat"
    memory_file = path / "memory.current"
    can_run_controller = controller_is_authorized()
    is_linux = sys.platform.startswith("linux")
    runc_available = shutil.which("runc") is not None
    criu_available = shutil.which("criu") is not None
    cgroup_ready = cpu_file.is_file() and memory_file.is_file() and usage is not None and memory_mb is not None
    if not is_linux:
        reason = "The process migration runtime needs a Linux host; this bridge is running on another OS."
    elif not runc_available:
        reason = "runc is not available to the bridge process."
    elif not criu_available:
        reason = "CRIU is not available to the bridge process."
    elif not cgroup_ready:
        reason = f"cgroup metrics could not be read at {path}. Set IPM_CGROUP_BASE to the parent directory and confirm the bridge user can read cpu.stat and memory.current."
    elif source.get("status") == "unavailable" and destination.get("status") == "unavailable":
        reason = source.get("error", "Container state is unavailable. Check runc permissions.")
    else:
        reason = None

    active = monitor_is_running()
    with state_lock:
        migration_in_progress = migration_active
        is_load_running = load_process is not None and load_process.poll() is None
        events = list(event_log)
    return {
        "connected": reason is None,
        "reason": reason,
        "platform": sys.platform,
        "runc_available": runc_available,
        "criu_available": criu_available,
        "can_operate": is_linux and os.geteuid() == 0 if is_linux else False,
        "source": source,
        "destination": destination,
        "active_container": active_id,
        "cpu_percent": round(cpu_percent, 2) if cpu_percent is not None else None,
        "memory_mb": memory_mb,
        "config": config,
        "controller_authorized": can_run_controller,
        "source_bundle_ready": bundle_ready(SOURCE_BUNDLE),
        "destination_bundle_ready": bundle_ready(DESTINATION_BUNDLE),
        "docker_available": shutil.which("docker") is not None,
        "load_running": is_load_running,
        "cgroup_path": str(path),
        "monitor_running": active,
        "migration_active": migration_in_progress,
        "events": events,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def consume_monitor_output(process: subprocess.Popen[str]) -> None:
    global migration_active, monitor_active
    assert process.stdout is not None
    for line in process.stdout:
        message = line.strip()
        if not message:
            continue
        level = "error" if "[ERROR]" in message else "warning" if "[DECISION]" in message or "[ACTION]" in message else "info"
        add_event(message, level)
        with state_lock:
            if "Starting migration controller" in message:
                migration_active = True
            elif "Migration controller completed" in message:
                migration_active = False
            elif "Migration controller failed" in message:
                migration_active = False
    process.stdout.close()
    with state_lock:
        monitor_active = False
        migration_active = False


def prepare_runtime_bundles() -> tuple[bool, str]:
    problem = require_linux_root()
    if problem:
        return False, problem
    docker = shutil.which("docker")
    if not docker:
        return False, "Docker is required to build the project workload image and prepare the runc root filesystems."
    source_rootfs = bundle_rootfs(SOURCE_BUNDLE)
    destination_rootfs = bundle_rootfs(DESTINATION_BUNDLE)
    if source_rootfs is None or destination_rootfs is None:
        return False, "The source or destination OCI config.json has an invalid root.path."
    if source_rootfs.is_dir() and destination_rootfs.is_dir():
        return True, "Both runc workload bundles are already prepared."
    if source_rootfs.is_dir() and not destination_rootfs.exists():
        try:
            shutil.copytree(source_rootfs, destination_rootfs)
            add_event("[SETUP] Copied the prepared source rootfs into the destination bundle.")
            return True, "The destination bundle is ready. You can start the source workload."
        except OSError as exc:
            return False, f"Could not prepare destination rootfs: {exc}"
    if destination_rootfs.is_dir() and not source_rootfs.exists():
        try:
            shutil.copytree(destination_rootfs, source_rootfs)
            add_event("[SETUP] Copied the prepared destination rootfs into the source bundle.")
            return True, "The source bundle is ready. You can start the source workload."
        except OSError as exc:
            return False, f"Could not prepare source rootfs: {exc}"
    if source_rootfs.exists() or destination_rootfs.exists():
        return False, "A partial rootfs already exists. Move it aside on the Linux host before preparing bundles again."

    add_event("[SETUP] Building the project workload image with Docker.")
    try:
        build = subprocess.run(
            [docker, "build", "--tag", WORKLOAD_IMAGE, "--file", str(WORKLOAD_DOCKERFILE), str(WORKLOAD_CONTEXT)],
            capture_output=True, text=True, timeout=600, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        add_event(f"[SETUP][ERROR] Docker image build failed: {exc}", "error")
        return False, f"Docker image build failed: {exc}"
    for line in (build.stdout + "\n" + build.stderr).splitlines()[-25:]:
        if line.strip():
            add_event(f"[DOCKER] {line}", "error" if build.returncode else "info")
    if build.returncode != 0:
        return False, "Docker could not build the workload image. See the Docker output below."

    created = subprocess.run([docker, "create", WORKLOAD_IMAGE], capture_output=True, text=True, timeout=30, check=False)
    if created.returncode != 0 or not created.stdout.strip():
        return False, f"Docker could not create a temporary container: {(created.stderr or created.stdout).strip()[-400:]}"
    container_id = created.stdout.strip().splitlines()[-1]
    source_rootfs.mkdir(parents=True)
    exported: subprocess.Popen[bytes] | None = None
    try:
        exported = subprocess.Popen([docker, "export", container_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert exported.stdout is not None
        with tarfile.open(fileobj=exported.stdout, mode="r|*") as archive:
            for member in archive:
                destination = (source_rootfs / member.name).resolve()
                try:
                    destination.relative_to(source_rootfs.resolve())
                except ValueError:
                    raise RuntimeError("Docker export contained a path outside the rootfs.")
                archive.extract(member, path=source_rootfs)
        stderr = exported.stderr.read().decode("utf-8", errors="replace") if exported.stderr else ""
        return_code = exported.wait(timeout=120)
        if return_code != 0:
            raise RuntimeError(stderr.strip()[-400:] or f"docker export exited with {return_code}")
        shutil.copytree(source_rootfs, destination_rootfs)
    except (OSError, RuntimeError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        if exported is not None and exported.poll() is None:
            exported.kill()
            exported.wait()
        shutil.rmtree(source_rootfs, ignore_errors=True)
        shutil.rmtree(destination_rootfs, ignore_errors=True)
        add_event(f"[SETUP][ERROR] Rootfs export failed: {exc}", "error")
        return False, f"Could not prepare the runc rootfs: {exc}"
    finally:
        try:
            subprocess.run([docker, "rm", container_id], capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            add_event(f"[SETUP][WARNING] Could not remove temporary Docker container: {exc}", "warning")

    add_event("[SETUP] Source and destination runc root filesystems are ready.")
    return True, "Both runc workload bundles are ready. You can start the source workload."


def reset_demo_containers() -> tuple[bool, str]:
    problem = require_linux_root()
    if problem:
        return False, problem
    runc = shutil.which("runc")
    if not runc:
        return False, "runc is not installed or not on PATH on this Linux host."
    with state_lock:
        if migration_active or (monitor_process is not None and monitor_process.poll() is None):
            return False, "Stop the monitor and wait for any migration to finish before resetting the demo."
    for container_id in (SOURCE_ID, DESTINATION_ID):
        state = runc_state(container_id)
        if state.get("status") == "unavailable":
            return False, f"Cannot safely reset {container_id}: {state.get('error', 'runc state is unavailable.')}"
        result = subprocess.run([runc, "delete", "--force", container_id], capture_output=True, text=True, timeout=20, check=False)
        error_text = (result.stderr or result.stdout).strip()
        if result.returncode != 0 and "does not exist" not in error_text.lower():
            return False, f"Could not reset {container_id}: {error_text[-400:]}"
    add_event("[RESET] Source and destination containers were removed for a fresh demo.")
    return True, "Demo containers reset. Start a fresh source workload when ready."


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "IPMBridge/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return False
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host in {"127.0.0.1", "localhost"}

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS or not self._origin_allowed():
            self._json(403, {"error": "This local origin is not allowed."})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._json(403, {"error": "This local origin is not allowed."})
            return
        if urlparse(self.path).path != "/api/status":
            self._json(404, {"error": "Unknown endpoint."})
            return
        self._json(200, collect_status())

    def do_POST(self) -> None:  # noqa: N802
        global monitor_process, monitor_active, migration_active, load_process
        if not self._origin_allowed() or self.headers.get("Origin") not in ALLOWED_ORIGINS:
            self._json(403, {"error": "A request from the local project page is required."})
            return
        endpoint = urlparse(self.path).path
        if endpoint == "/api/runtime/prepare":
            ready, message = prepare_runtime_bundles()
            self._json(200 if ready else 409, {"ok": ready, "message": message} if ready else {"error": message})
            return

        if endpoint == "/api/demo/reset":
            ready, message = reset_demo_containers()
            self._json(200 if ready else 409, {"ok": ready, "message": message} if ready else {"error": message})
            return

        if endpoint == "/api/container/source/start":
            problem = require_linux_root()
            if problem:
                self._json(409, {"error": problem})
                return
            runc = shutil.which("runc")
            if not runc:
                self._json(409, {"error": "runc is not installed or not on PATH on this Linux host."})
                return
            if not bundle_ready(SOURCE_BUNDLE):
                self._json(409, {"error": "Prepare the source runc bundle first. Its OCI rootfs is missing."})
                return
            source = runc_state(SOURCE_ID)
            if source.get("status") == "running":
                self._json(409, {"error": "The source workload is already running."})
                return
            if source.get("status") != "stopped":
                self._json(409, {"error": f"The source container state is {source.get('status')}; reset the demo and inspect the runc error before starting it."})
                return
            destination = runc_state(DESTINATION_ID)
            if destination.get("status") == "running":
                self._json(409, {"error": "The destination is already running. Reset the completed demo before starting another source workload."})
                return
            try:
                process = subprocess.Popen(
                    [runc, "run", "--bundle", str(SOURCE_BUNDLE), SOURCE_ID],
                    cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                )
            except OSError as exc:
                self._json(500, {"error": f"Could not start the source workload: {exc}"})
                return
            add_event("[WORKLOAD] Starting migration-source through runc.")
            threading.Thread(target=capture_process_output, args=(process, ""), daemon=True).start()
            self._json(200, {"ok": True, "message": "Source workload started. Its stdout is now streamed to Host events."})
            return

        if endpoint == "/api/load/start":
            problem = require_linux_root()
            if problem:
                self._json(409, {"error": problem})
                return
            runc = shutil.which("runc")
            source = runc_state(SOURCE_ID)
            if not runc or source.get("status") != "running":
                self._json(409, {"error": "Start the migration-source workload before applying CPU load."})
                return
            if not monitor_is_running():
                self._json(409, {"error": "Start the live monitor before applying CPU load."})
                return
            with state_lock:
                if load_process is not None and load_process.poll() is None:
                    self._json(409, {"error": "A bounded CPU burst is already running."})
                    return
                cpu_burst = (
                    "import time; end=time.monotonic()+12; value=0; "
                    "print('[LOAD] 12-second CPU burst started', flush=True); "
                    "exec('while time.monotonic()<end:\\n value=(value*3+7)%1000003'); "
                    "print('[LOAD] CPU burst finished', flush=True)"
                )
                try:
                    load_process = subprocess.Popen(
                        [runc, "exec", SOURCE_ID, "python3", "-u", "-c", cpu_burst],
                        cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, bufsize=1,
                    )
                except OSError as exc:
                    self._json(500, {"error": f"Could not start the bounded CPU burst: {exc}"})
                    return
                process = load_process
            add_event("[LOAD] Starting a bounded 12-second CPU burst in migration-source.")
            threading.Thread(target=capture_process_output, args=(process, ""), daemon=True).start()
            self._json(200, {"ok": True, "message": "A bounded 12-second CPU burst started inside migration-source."})
            return

        if endpoint == "/api/monitor/start":
            status = collect_status()
            if not status["connected"]:
                self._json(409, {"error": status["reason"] or "The Linux runtime is unavailable."})
                return
            if status["source"].get("status") != "running":
                self._json(409, {"error": "Start the migration-source container before monitoring."})
                return
            if status["config"]["auto_migrate"] and not status["controller_authorized"]:
                self._json(409, {"error": "The bridge user cannot run the controller without a password. Add the exact controller rule from the live-bridge setup instructions."})
                return
            with state_lock:
                if monitor_process is not None and monitor_process.poll() is None:
                    self._json(409, {"error": "The live monitor is already running."})
                    return
                env = os.environ.copy()
                env["IPM_CGROUP_BASE"] = str(cgroup_path(status["source"].get("pid")).parent)
                try:
                    monitor_process = subprocess.Popen(
                        ["bash", str(MONITOR_SCRIPT)],
                        cwd=PROJECT_ROOT,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                except OSError as exc:
                    self._json(500, {"error": f"Could not start the existing cgroup monitor: {exc}"})
                    return
                monitor_active = True
                migration_active = False
                process = monitor_process
            add_event("Live cgroup monitor started from the project UI.")
            threading.Thread(target=consume_monitor_output, args=(process,), daemon=True).start()
            self._json(200, {"ok": True, "message": "Live monitor started. Automatic migration is enabled by project config."})
            return

        if endpoint == "/api/monitor/stop":
            with state_lock:
                process = monitor_process
                active_migration = migration_active
            if active_migration:
                self._json(409, {"error": "A migration is in progress. The monitor cannot be stopped mid-checkpoint or restore."})
                return
            if process is None or process.poll() is not None:
                self._json(200, {"ok": True, "message": "The live monitor is already stopped."})
                return
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            add_event("Live cgroup monitor stopped from the project UI.")
            self._json(200, {"ok": True, "message": "Live monitor stopped."})
            return

        self._json(404, {"error": "Unknown endpoint."})

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    port = int(os.environ.get("IPM_API_PORT", "4174"))
    server = ThreadingHTTPServer(("127.0.0.1", port), BridgeHandler)
    print(f"Intelligent Process Migration API listening on http://127.0.0.1:{port}", flush=True)
    print(f"Project root: {PROJECT_ROOT}", flush=True)
    print(f"cgroup base: {cgroup_path().parent}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping local bridge.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
