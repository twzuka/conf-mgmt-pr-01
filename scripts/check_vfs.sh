#!/bin/sh
SCRIPT_DIR=$(CDPATH= cd -- "${0%/*}" && pwd)
PROJECT_DIR=${SCRIPT_DIR%/*}
APP="$PROJECT_DIR/src/main.py"

for name in minimal files nested invalid invalid_base64 missing; do
    echo "=== VFS: $name ==="
    python3 "$APP" --vfs-path "$PROJECT_DIR/vfs/$name.xml" \
        --prompt 'demo> ' --script "$SCRIPT_DIR/startup.txt"
    echo "Exit code: $?"
done

echo "=== missing --vfs-path ==="
python3 "$APP"
echo "Exit code: $?"

echo "=== missing startup script ==="
printf 'exit\n' | python3 "$APP" --vfs-path "$PROJECT_DIR/vfs/minimal.xml" \
    --script "$SCRIPT_DIR/missing.txt"
echo "Exit code: $?"
