# COBOL Buggy Task

You are given a small COBOL program in the container at `/app/main.cob`. It contains an intentional bug.

Your job is to fix the program so that the verifier test (which compiles and runs it) produces the exact required output.

## What you must do

- Fix `/app/main.cob` so that running `/app/run_cobol.sh` prints exactly:

```
COBOL: Hello, world
```

...followed by a single newline (`\n`), and exits with code `0`.

## How the verifier works

- The verifier runs the script `/tests/test.sh`.
- `/tests/test.sh` runs `pytest /tests/test_outputs.py`.
- `test_outputs.py` invokes `/bin/bash /app/run_cobol.sh`.
- The baseline container is intentionally buggy, so tests should fail until the fix is applied.

Reward file
- The verifier writes the reward to `/logs/verifier/reward.txt` (1 for pass, 0 for fail) and always exits 0.

## Determinism requirements

- The environment sets `LANG=C.UTF-8` and `LC_ALL=C.UTF-8`.
- Your fix must not depend on time, randomness, network, or external files.

## Toolchain

- GnuCOBOL (`cobc`) is installed in the container.
- The runner `/app/run_cobol.sh` recompiles `/app/main.cob` and runs it.
