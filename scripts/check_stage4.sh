#!/bin/sh
SCRIPT_DIR=$(CDPATH= cd -- "${0%/*}" && pwd)
PROJECT_DIR=${SCRIPT_DIR%/*}
exec python3 "$PROJECT_DIR/src/main.py" \
    --vfs-path "$PROJECT_DIR/vfs/demo.xml" \
    --prompt 'stage4> ' --script "$SCRIPT_DIR/stage4.txt"
