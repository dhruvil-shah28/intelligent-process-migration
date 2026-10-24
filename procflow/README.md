# Intelligent Process Migration

An automated Linux process migration prototype using runc, CRIU, cgroup v2 monitoring, and threshold-based decision logic.

## Overview

The system monitors a running containerized workload and automatically migrates it when resource usage exceeds a configured threshold.

The migration pipeline is:

Source Workload
→ cgroup v2 Monitoring
→ Decision Engine
→ CRIU Checkpoint
→ runc Restore
→ Destination Workload

## Core Components

### 1. Workload

A persistent Python workload maintains an incrementing counter and prints its execution state.

### 2. Resource Monitor

`monitor/cgroup-monitor.sh`

Uses Linux cgroup v2 metrics:

- `cpu.stat`
- `memory.current`

CPU utilization is calculated from the change in cumulative CPU usage over elapsed time.

### 3. Decision Engine

Configured through:

`monitor/config.conf`

Current configuration:

- CPU threshold: 50%
- Memory threshold: 70%
- Monitoring interval: 2 seconds
- Automatic migration: enabled

### 4. Migration Controller

`controller/migrate.sh`

Performs:

1. Source validation
2. Checkpoint directory preparation
3. CRIU checkpoint
4. Background runc restore
5. Destination validation
6. Migration completion reporting

## Automatic Migration

When CPU usage exceeds the configured threshold:

1. The monitor detects high resource usage.
2. The decision engine marks the workload as a migration candidate.
3. If automatic migration is enabled, the migration controller is invoked.
4. CRIU checkpoints the source process.
5. runc restores the process in the destination container.
6. The restored workload continues execution from its checkpointed state.

## Demonstrated Result

The prototype successfully demonstrated:

- Real container-level CPU monitoring
- Real container-level memory monitoring
- CPU threshold detection
- Automatic migration triggering
- CRIU checkpointing
- runc restoration
- Background destination restoration
- Process state continuity

During the final demonstration, the system detected approximately 100% CPU utilization, automatically triggered migration, restored the destination, and the workload continued incrementing its counter after migration.

## Technology Stack

- Linux
- Bash
- Python
- runc
- CRIU
- cgroup v2
- OCI container specification

## Project Structure

```text
intelligent-process-migration/
├── controller/
│   └── migrate.sh
├── monitor/
│   ├── cgroup-monitor.sh
│   ├── monitor.sh
│   ├── config.conf
│   └── load-test.sh
├── migration/
│   ├── checkpoint/
│   ├── checkpoint-work/
│   ├── runc-source-bundle/
│   ├── runc-destination-bundle/
│   └── workloads/
├── evidence/
│   ├── final-controller.sh
│   ├── final-cgroup-monitor.sh
│   └── final-config.conf
└── README.md
```

## Interactive web interface and live host bridge

The React/Vite interface has a plain-language landing page and a live workspace connected to the local API bridge. The workspace reads real `runc state`, `cpu.stat`, and `memory.current` values, controls `monitor/cgroup-monitor.sh`, and displays backend events and migration progress. When `AUTO_MIGRATE=true`, the existing monitor invokes the real checkpoint/restore controller at the configured CPU threshold. Starting the live monitor in the UI requires confirmation because it can migrate the running source workload and replaces the existing checkpoint directory.

The main experience lives in `src/App.tsx` and `src/styles.css`. It has two views: a plain-language home page and a live workspace for preparing the runtime, starting the workload, operating monitoring, applying load, and reading backend output.

With Node.js (Vite 7 requires Node.js 20.19+ or 22.12+) and the pinned pnpm 11.25.0 package manager:

```sh
pnpm install
pnpm dev
```

The development server listens on port 3000. Create a production bundle with:

```sh
pnpm build
```

### Connect to a Linux host

Run the API bridge on the Linux host that will run runc and CRIU. The complete demo controls require Linux, runc, cgroup v2, Docker, and a root API process. The bridge binds to loopback only. If the UI is on another computer, use an SSH tunnel so the API is not exposed to the network.

On the Linux host, from `procflow/`, start the bridge as root:

```sh
sudo -E python3 api/server.py
```

The bridge derives the source container's cgroup from its runc PID. Set `IPM_CGROUP_BASE` only when the host uses a nonstandard cgroup layout; it should name the parent of the `migration-source` cgroup. In the live workspace, choose **Prepare workload bundles** to build the image from `workloads/Dockerfile` and create the ignored source and destination `rootfs` directories. Then start the source workload, start monitoring, and apply the bounded 12-second CPU burst. When CPU crosses the configured threshold, the existing monitor invokes the migration controller.

If using SSH, forward the API port from the UI computer:

```sh
ssh -L 4174:127.0.0.1:4174 <user>@<linux-host>
```

Run `pnpm dev` in a second terminal on the UI computer. Its Vite proxy forwards `/api` to `127.0.0.1:4174`. Keep the SSH tunnel open. For a local Linux setup, the API and Vite server can both run from `procflow/` on the same host.

The root bridge reads the cgroup files and runs fixed project actions. Do not expose the API port publicly. The UI asks before starting monitoring or applying load because the automatic controller may checkpoint the source, replace existing checkpoint directories, and restore to the destination. The monitor cannot be stopped through the UI during checkpoint/restore.

The workspace reports missing Linux tools, Docker access, root filesystems, cgroup metrics, or controller permissions from the live host. It does not substitute simulated readings or claim a migration succeeded without backend state and output.

The Linux migration flow itself has no portable one-command bootstrap sequence in the current documentation. The existing host scripts refer to a developer-specific home directory and cgroup scope; review their assumptions and the documented prerequisites before attempting a real run.
