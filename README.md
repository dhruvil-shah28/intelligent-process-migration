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
