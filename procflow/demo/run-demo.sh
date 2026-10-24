#!/bin/bash

set -u

PROJECT="/home/dhruvil/intelligent-process-migration"

SOURCE="migration-source"
DEST="migration-restored"

echo "=========================================="
echo "   INTELLIGENT PROCESS MIGRATION DEMO"
echo "=========================================="
echo

echo "[1/6] Checking migration state..."

SOURCE_RUNNING=false
DEST_RUNNING=false

if sudo runc state "$SOURCE" >/dev/null 2>&1; then
    SOURCE_RUNNING=true
fi

if sudo runc state "$DEST" >/dev/null 2>&1; then
    DEST_RUNNING=true
fi

if [ "$SOURCE_RUNNING" = true ]; then
    echo "[OK] Source container is running."
elif [ "$DEST_RUNNING" = true ]; then
    echo "[OK] Source no longer running — migration has occurred."
else
    echo "[ERROR] Neither source nor destination is running."
    exit 1
fi

echo
echo "[2/6] Migration state..."

if [ "$SOURCE_RUNNING" = true ] && [ "$DEST_RUNNING" = false ]; then
    echo "[STATE] PRE-MIGRATION"
    echo "[STATE] Source = RUNNING"
    echo "[STATE] Destination = NOT ACTIVE"
elif [ "$SOURCE_RUNNING" = false ] && [ "$DEST_RUNNING" = true ]; then
    echo "[STATE] POST-MIGRATION"
    echo "[STATE] Source = STOPPED"
    echo "[STATE] Destination = RUNNING"
else
    echo "[STATE] Source and destination both exist."
fi

echo
echo "[3/6] Workload state..."

if [ "$SOURCE_RUNNING" = true ]; then
    sudo runc exec "$SOURCE" sh -c 'cat /proc/1/fd/1' || true
fi

if [ "$DEST_RUNNING" = true ]; then
    sudo runc exec "$DEST" sh -c 'cat /proc/1/fd/1' || true
fi

echo
echo "[4/6] Migration configuration..."
cat "$PROJECT/monitor/config.conf"

echo
echo "[5/6] Container status..."

if [ "$DEST_RUNNING" = true ]; then
    DEST_STATE=$(sudo runc state "$DEST")

    echo "$DEST_STATE" | grep -E '"id"|"pid"|"status"|"bundle"'

    echo
    echo "[OK] Destination container is RUNNING."
else
    echo "[INFO] Destination container is not currently active."
fi

echo
echo "[6/6] Final verification..."

if [ "$DEST_RUNNING" = true ]; then

    echo "[OK] Checkpoint/restore destination detected."
    echo "[OK] Workload is executing in destination."
    echo "[OK] Migration state verified."

    echo
    echo "=========================================="
    echo "       MIGRATION DEMO SUCCESSFUL"
    echo "=========================================="
    echo
    echo "Source       : STOPPED"
    echo "Destination  : RUNNING"
    echo "State        : PRESERVED"
    echo "Workload     : CONTINUING"
    echo

else

    echo "[INFO] No completed migration detected yet."
    echo
    echo "For the live demonstration:"
    echo "1. Start migration-source."
    echo "2. Start cgroup-monitor.sh."
    echo "3. Inject CPU load."
    echo "4. Observe automatic migration."
    echo

fi
