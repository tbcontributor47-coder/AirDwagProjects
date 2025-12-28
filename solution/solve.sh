#!/usr/bin/env bash
set -euo pipefail

# Fixer script (oracle-style): overwrite the buggy program in /app so verifier tests pass.
# Mirrors the established pattern used by `eft-file-validation`.

export LANG=C.UTF-8
export LC_ALL=C.UTF-8

cat > /app/main.cob <<'COBOL'
*> Correct COBOL program: prints deterministic message
       identification division.
       program-id. MAIN.
       environment division.
       data division.
       procedure division.
           display "COBOL: Hello, world".
           goback.
       end program MAIN.
COBOL

# Ensure the runner remains executable (in case the base image changes)
chmod +x /app/run_cobol.sh || true

exit 0
