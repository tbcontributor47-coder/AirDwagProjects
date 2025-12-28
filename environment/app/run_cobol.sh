#!/usr/bin/env bash
set -euo pipefail

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

SRC="/app/main.cob"
BIN="/tmp/cobol_main"

if [ $# -ne 1 ]; then
	echo "Usage: /app/run_cobol.sh /path/to/input.txt" >&2
	exit 2
fi

INPUT_PATH="$1"

# Compile and run. Any compile error should surface as a failing test.
cobc -x -free "$SRC" -o "$BIN"

"$BIN" "$INPUT_PATH"
