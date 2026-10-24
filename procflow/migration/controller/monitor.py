#!/usr/bin/env python3

import argparse
import json
import time
from datetime import datetime, timezone

import psutil


def get_process_metrics(process):
    """Collect resource metrics for a running process."""

    memory = process.memory_info()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pid": process.pid,
        "cpu_percent": process.cpu_percent(interval=None),
        "memory_percent": process.memory_percent(),
        "rss_bytes": memory.rss,
        "vms_bytes": memory.vms,
        "status": process.status(),
        "system_load_1m": psutil.getloadavg()[0],
    }


def monitor(pid, interval):
    """Continuously monitor a process."""

    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(json.dumps({
            "error": "process_not_found",
            "pid": pid
        }))
        return

    # Prime CPU measurement.
    process.cpu_percent(interval=None)

    print(json.dumps({
        "event": "monitor_started",
        "pid": pid,
        "interval_seconds": interval
    }))

    try:
        while process.is_running():
            time.sleep(interval)

            if not process.is_running():
                break

            try:
                metrics = get_process_metrics(process)
                print(json.dumps(metrics), flush=True)
            except psutil.NoSuchProcess:
                break

    except KeyboardInterrupt:
        print(json.dumps({
            "event": "monitor_stopped",
            "pid": pid
        }))


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Process Migration resource monitor"
    )

    parser.add_argument(
        "pid",
        type=int,
        help="PID of the process to monitor"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Sampling interval in seconds (default: 2)"
    )

    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be greater than zero")

    monitor(args.pid, args.interval)


if __name__ == "__main__":
    main()
