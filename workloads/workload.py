import os
import time
from datetime import datetime

COUNTER = 0

print(f"[WORKLOAD] Started | PID={os.getpid()}", flush=True)

while True:
    COUNTER += 1

    if COUNTER % 10 == 0:
        print(
            f"[WORKLOAD] PID={os.getpid()} | "
            f"counter={COUNTER} | "
            f"time={datetime.now().isoformat()}",
            flush=True,
        )

    time.sleep(1)
