#!/usr/bin/env bash
set -euo pipefail

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

SRC="/app/main.cob"
BIN="/tmp/cobol_main"

# Compile and run. Any compile error should surface as a failing test.
cobc -x -free "$SRC" -o "$BIN"

OUT="$($BIN)"
printf '%s\n' "$OUT"
