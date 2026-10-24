#!/usr/bin/env python3

import os
import time
from datetime import datetime, timezone


def cpu_burn(seconds):
    end = time.time() + seconds
    value = 0

    while time.time() < end:
        value = (value * 3 + 7) % 1000003


def main():
    pid = os.getpid()

    print(f"[STRESS] Started | PID={pid}", flush=True)

    counter = 0

    while True:
        counter += 1

        print(
            f"[STRESS] PID={pid} | "
            f"phase={counter} | "
            f"time={datetime.now(timezone.utc).isoformat()}",
            flush=True,
        )

        cpu_burn(20)


if __name__ == "__main__":
    main()
