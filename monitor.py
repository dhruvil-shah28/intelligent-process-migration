import os
import platform
import time

import psutil


def collect_metrics():
    return {
        "node_id": platform.node(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "available_ram_mb": round(
            psutil.virtual_memory().available / (1024 * 1024), 2
        ),
        "process_count": len(psutil.pids()),
    }


if __name__ == "__main__":
    print("=== INTELLIGENT PROCESS MIGRATION ===")
    print("Node monitoring started. Press Ctrl+C to stop.\n")

    try:
        while True:
            metrics = collect_metrics()

            print(f"Node:          {metrics['node_id']}")
            print(f"CPU usage:     {metrics['cpu_percent']}%")
            print(f"RAM usage:     {metrics['ram_percent']}%")
            print(f"Available RAM: {metrics['available_ram_mb']} MB")
            print(f"Processes:     {metrics['process_count']}")
            print("-" * 40)

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
