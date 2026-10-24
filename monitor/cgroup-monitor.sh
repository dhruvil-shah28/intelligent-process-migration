#!/bin/bash

SOURCE="migration-source"
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CGROUP_BASE="${IPM_CGROUP_BASE:-/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.kde.konsole-33815.scope}"

CGROUP="$CGROUP_BASE/$SOURCE"

CONFIG="$(dirname "$0")/config.conf"
source "$CONFIG"

INTERVAL="$CHECK_INTERVAL"

trap 'echo "[INFO] Stop requested; exiting monitor."; exit 0' TERM INT

echo "=========================================="
echo " Container Resource Monitor (cgroup v2)"
echo "=========================================="

if [ ! -f "$CGROUP/cpu.stat" ]; then
    echo "[ERROR] CPU cgroup metric not found."
    exit 1
fi

if [ ! -f "$CGROUP/memory.current" ]; then
    echo "[ERROR] Memory cgroup metric not found."
    exit 1
fi

PREV_CPU=$(awk '/usage_usec/ {print $2}' "$CGROUP/cpu.stat")
PREV_TIME=$(date +%s%N)

while true; do

    sleep "$INTERVAL"

    CURRENT_CPU=$(awk '/usage_usec/ {print $2}' "$CGROUP/cpu.stat")
    CURRENT_TIME=$(date +%s%N)

    CPU_DELTA=$((CURRENT_CPU - PREV_CPU))
    TIME_DELTA=$((CURRENT_TIME - PREV_TIME))

    CPU_PERCENT=$(awk \
        -v cpu="$CPU_DELTA" \
        -v time="$TIME_DELTA" \
        'BEGIN {
            if (time > 0)
                printf "%.2f", (cpu * 100000 / time);
            else
                printf "0.00";
        }')

    MEMORY_BYTES=$(cat "$CGROUP/memory.current")

    MEMORY_MB=$(awk \
        -v bytes="$MEMORY_BYTES" \
        'BEGIN {
            printf "%.2f", bytes / 1024 / 1024;
        }')

    echo "[MONITOR] CPU=${CPU_PERCENT}% | MEMORY=${MEMORY_MB} MB"

if awk -v cpu="$CPU_PERCENT" -v threshold="$CPU_THRESHOLD" 'BEGIN {exit !(cpu >= threshold)}'; then

    echo "[DECISION] CPU threshold exceeded → MIGRATION CANDIDATE"

    if [ "$AUTO_MIGRATE" = "true" ]; then
        echo "[ACTION] Automatic migration enabled."
        echo "[ACTION] Starting migration controller..."

        if [ "$(id -u)" -eq 0 ]; then
            "$PROJECT/controller/migrate.sh"
        else
            sudo -n "$PROJECT/controller/migrate.sh"
        fi
        RESULT=$?
        if [ "$RESULT" -eq 0 ]; then
            echo "[ACTION] Migration controller completed."
        else
            echo "[ERROR] Migration controller failed with exit code $RESULT."
        fi
        break
    else
        echo "[ACTION] AUTO_MIGRATE=false → dry-run only."
    fi

else
    echo "[DECISION] Resource usage normal"
fi

    PREV_CPU="$CURRENT_CPU"
    PREV_TIME="$CURRENT_TIME"

done
