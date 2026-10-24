import os
import time

print(f"Worker started! PID = {os.getpid()}", flush=True)

counter = 0

try:
    while True:
        # Perform a small amount of CPU work.
        for i in range(100_000):
            counter += i % 7

        print(f"PID={os.getpid()} | counter={counter}", flush=True)
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nWorker stopped safely.")
