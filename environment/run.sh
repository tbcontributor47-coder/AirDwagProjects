#!/usr/bin/env bash
set -euo pipefail

# compile and run the environment (buggy) COBOL program
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COB_SRC="$SCRIPT_DIR/main.cob"
BIN=/tmp/cobol_env_main

if command -v cobc >/dev/null 2>&1; then
  cobc -x -free "$COB_SRC" -o "$BIN" || true
fi

if [ -x "$BIN" ]; then
  "$BIN"
else
  echo "(environment program unavailable)"
fi
