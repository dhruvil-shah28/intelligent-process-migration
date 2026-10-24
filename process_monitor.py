import psutil


def inspect_process(pid):
    try:
        process = psutil.Process(pid)

        with process.oneshot():
            result = {
                "pid": process.pid,
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(interval=1),
                "memory_mb": round(
                    process.memory_info().rss / (1024 * 1024), 2
                ),
            }

        return result

    except psutil.NoSuchProcess:
        return {"error": f"Process {pid} does not exist"}

    except psutil.AccessDenied:
        return {"error": f"Permission denied for process {pid}"}


if __name__ == "__main__":
    pid = int(input("Enter the worker PID: "))
    print("\n=== PROCESS INSPECTION ===")
    print(inspect_process(pid))
