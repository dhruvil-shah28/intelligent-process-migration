#!/bin/bash

set -e

PROJECT="/home/dhruvil/intelligent-process-migration"

SOURCE="migration-source"
DEST="migration-restored"

CHECKPOINT="$PROJECT/migration/checkpoint"
CHECKPOINT_WORK="$PROJECT/migration/checkpoint-work"
DEST_BUNDLE="$PROJECT/migration/runc-destination-bundle"

echo "=========================================="
echo " Intelligent Process Migration Controller"
echo "=========================================="

echo "[1/5] Checking source container..."

if ! sudo runc state "$SOURCE" >/dev/null 2>&1; then
    echo "[ERROR] Source container '$SOURCE' is not running."
    exit 1
fi

echo "[OK] Source container is running."

echo "[2/5] Preparing checkpoint directory..."

sudo rm -rf "$CHECKPOINT" "$CHECKPOINT_WORK"
sudo mkdir -p "$CHECKPOINT" "$CHECKPOINT_WORK"

echo "[OK] Checkpoint directory ready."

echo "[3/5] Checkpointing source..."

sudo runc checkpoint "$SOURCE" \
    --image-path "$CHECKPOINT" \
    --work-path "$CHECKPOINT_WORK"

echo "[OK] Source checkpointed."

echo "[4/5] Restoring destination..."

sudo runc restore \
    --bundle "$DEST_BUNDLE" \
    --image-path "$CHECKPOINT" \
    --work-path "$CHECKPOINT_WORK" \
    "$DEST" >"$CHECKPOINT_WORK/restore-console.log" 2>&1 &
RESTORE_PID=$!

echo "[INFO] Restore process started with PID=$RESTORE_PID"

sleep 2

if ! sudo runc state "$DEST" >/dev/null 2>&1; then
    echo "[ERROR] Destination failed to start."
    echo "[ERROR] Restore log:"
    sudo tail -30 "$CHECKPOINT_WORK/restore-console.log"
    exit 1
fi

echo "[OK] Destination restored."

echo "[5/5] Migration complete."

sudo runc state "$DEST"
