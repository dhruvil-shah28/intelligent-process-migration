#!/usr/bin/env python3

import argparse
import json
import time
from datetime import datetime, timezone

import psutil

from migration.controller.decision import evaluate
from migration.controller.persistence import PressurePersistence


def collect_metrics(pid, previous_cpu=None, previous_time=None):
    process = psutil.Process(pid)

    with process.oneshot():
        cpu_times = process.cpu_times()
        current_cpu = cpu_times.user + cpu_times.system
        current_time = time.monotonic()

        if previous_cpu is None or previous_time is None:
            cpu_percent = 0.0
        else:
            elapsed = current_time - previous_time
            cpu_delta = current_cpu - previous_cpu
            cpu_percent = (cpu_delta / elapsed) * 100.0 if elapsed > 0 else 0.0
        memory_percent = process.memory_percent()
        memory_info = process.memory_info()
        status = process.status()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pid": pid,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "rss_bytes": memory_info.rss,
        "vms_bytes": memory_info.vms,
        "status": status,
        "system_load_1m": psutil.getloadavg()[0],
        "cpu_cores": psutil.cpu_count(logical=True) or 1,
        "migration_cost_percent": 0.0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Process Migration controller"
    )

    parser.add_argument(
        "pid",
        type=int,
        help="Target process PID",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Monitoring interval in seconds",
    )

    args = parser.parse_args()

    try:
        process = psutil.Process(args.pid)
        process.cpu_percent()
    except psutil.NoSuchProcess:
        raise SystemExit(
            f"Process {args.pid} does not exist"
        )

    persistence = PressurePersistence(
        monitor_threshold=0.50,
        persistence_seconds=10.0,
    )

    print(
        json.dumps({
            "event": "controller_started",
            "pid": args.pid,
            "mode": "DRY_RUN",
            "interval_seconds": args.interval,
            "persistence_seconds": 10.0,
        }),
        flush=True,
    )

    previous_cpu = None
    previous_time = None

    try:
        while True:
            metrics = collect_metrics(
                args.pid,
                previous_cpu,
                previous_time,
            )

            cpu_times = process.cpu_times()
            previous_cpu = cpu_times.user + cpu_times.system
            previous_time = time.monotonic()

            decision = evaluate(metrics)

            temporal = persistence.update(
                decision["score"]
            )

            raw_action = decision["action"]

            # Persistence-aware action.
            if raw_action == "MIGRATE":
                if temporal["persistent"]:
                    action = "MIGRATE"
                else:
                    action = "MONITOR"
            else:
                action = raw_action

            output = {
                "event": "decision",
                "timestamp": metrics["timestamp"],
                "pid": args.pid,
                "metrics": metrics,
                "score": decision["score"],
                "raw_action": raw_action,
                "action": action,
                "temporal": temporal,
            }

            print(
                json.dumps(output),
                flush=True,
            )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(
            json.dumps({
                "event": "controller_stopped",
                "pid": args.pid,
            }),
            flush=True,
        )


if __name__ == "__main__":
    main()
