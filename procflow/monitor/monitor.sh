#!/bin/bash

SOURCE="migration-source"
CONFIG="$(dirname "$0")/config.conf"

source "$CONFIG"

echo "=========================================="
echo " Intelligent Process Migration Monitor"
echo "=========================================="
echo "[CONFIG] CPU threshold    = ${CPU_THRESHOLD}%"
echo "[CONFIG] Memory threshold = ${MEMORY_THRESHOLD}%"
echo "[CONFIG] Check interval   = ${CHECK_INTERVAL}s"
echo "=========================================="

while true; do

    STATE=$(sudo runc state "$SOURCE" 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo "[MONITOR] Destination container not found."
        sleep "$CHECK_INTERVAL"
        continue
    fi

    PID=$(echo "$STATE" | grep '"pid"' | head -1 | grep -o '[0-9]\+')
    STATUS=$(echo "$STATE" | grep '"status"' | head -1 | cut -d'"' -f4)

    if [ "$PID" -gt 0 ] 2>/dev/null; then

        CPU=$(ps -p "$PID" -o %cpu= | xargs)
        MEM=$(ps -p "$PID" -o %mem= | xargs)

        echo "[MONITOR] PID=$PID | STATUS=$STATUS | CPU=${CPU}% | MEM=${MEM}%"

        CPU_ALERT=$(awk -v cpu="$CPU" -v threshold="$CPU_THRESHOLD" 'BEGIN {print (cpu >= threshold) ? 1 : 0}')
        MEM_ALERT=$(awk -v mem="$MEM" -v threshold="$MEMORY_THRESHOLD" 'BEGIN {print (mem >= threshold) ? 1 : 0}')

        if [ "$CPU_ALERT" -eq 1 ]; then
            echo "[DECISION] CPU threshold exceeded."
            echo "[DECISION] Migration recommended."
        fi

        if [ "$MEM_ALERT" -eq 1 ]; then
            echo "[DECISION] Memory threshold exceeded."
            echo "[DECISION] Migration recommended."
        fi

    else
        echo "[MONITOR] STATUS=$STATUS"
    fi

    sleep "$CHECK_INTERVAL"
done
