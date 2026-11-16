# Intelligent Process Migration

An automated Linux process migration prototype using runc, CRIU, cgroup v2 monitoring, and threshold-based decision logic.

## Overview

The system monitors a running containerized workload and automatically migrates it when resource usage exceeds a configured threshold.

The migration pipeline is:

Source Workload → cgroup v2 Monitoring → Decision Engine → CRIU Checkpoint → runc Restore → Destination Workload

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

### 5. Live Frontend (procflow)

A Vite + React web interface (`procflow/`) backed by a Python host bridge (`procflow/api/server.py`). It lets you start the source workload, run the monitor, trigger a CPU burst, and watch each migration stage and the backend output live in the browser.

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
- React, Vite, TypeScript (frontend)

## Running the Frontend Demo

The live demo has two parts: a Vite frontend and a Python host bridge (API) that runs the migration scripts. Run both from the `procflow` folder, each in its own terminal tab.

### Requirements

- Linux with cgroup v2, `runc`, and `criu` installed
- Node.js 20.19+ and pnpm 11
- Python 3
- `sudo` access (runc and CRIU need root)

### One-time setup

```bash
cd procflow
pnpm install
```

### Tab 1: Frontend

```bash
cd procflow
pnpm dev
```

Open http://localhost:3000/

### Tab 2: Host bridge (API)

```bash
cd procflow
export IPM_CGROUP_BASE=/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.kde.konsole-<ID>.scope
sudo -E python3 api/server.py
```

The API listens on `127.0.0.1:4174`.

`IPM_CGROUP_BASE` must be the cgroup of the terminal window that runs the API. The Konsole scope number (`<ID>`) changes whenever a new Konsole window is opened. Find yours with:

```bash
cat /proc/self/cgroup
```

Use the path from that output without the trailing `/tab(...).scope` part, prefixed with `/sys/fs/cgroup`.

### Using the demo

In the browser, open **Live Workspace**, then:

1. Click **Start source workload**
2. Start the monitor
3. Click **Apply 12-second CPU burst**

The monitor detects the CPU spike, CRIU checkpoints the source, runc restores it as `migration-restored`, and the counter continues from its checkpointed value.

Use **Reset demo** to start over.

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
├── procflow/
│   ├── api/
│   │   └── server.py
│   ├── src/
│   └── package.json
├── evidence/
│   ├── final-controller.sh
│   ├── final-cgroup-monitor.sh
│   └── final-config.conf
└── README.md
```
