#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "${0%/*}" && pwd)
PROJECT_DIR=${SCRIPT_DIR%/*}
APP="$PROJECT_DIR/src/main.py"
STARTUP="$SCRIPT_DIR/startup.txt"

echo "=== --vfs-path ==="
printf 'exit\n' | python3 "$APP" --vfs-path "$PROJECT_DIR/vfs.xml"

echo "=== --prompt ==="
printf 'exit\n' | python3 "$APP" --prompt 'demo> '

echo "=== --script ==="
python3 "$APP" --script "$STARTUP"

echo "=== all parameters ==="
python3 "$APP" --vfs-path "$PROJECT_DIR/vfs.xml" \
    --prompt 'demo> ' --script "$STARTUP"
