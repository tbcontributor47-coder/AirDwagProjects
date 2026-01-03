#!/bin/bash

# Configuration
APP_DIR="environment/app"
DATA_DIR="environment/data"
REPORT_DIR="environment/reports"
TESTS_DIR="tests"

# 1. Setup - create report dir if missing
mkdir -p $REPORT_DIR

# 2. Compile COBOL
echo "Compiling reconcile.cbl..."
cobc -x -o reconcile $APP_DIR/reconcile.cbl
if [ $? -ne 0 ]; then
    echo "Error: Compilation failed"
    exit 1
fi

# 3. Run Program
echo "Running reconciliation..."
# Ensure files are in place for the run
cp $DATA_DIR/input.dat .
./reconcile
RUN_STATUS=$?

# 4. Clean up and Move outcomes (optional, but good for structure)
if [ -f balanced_report.txt ]; then mv balanced_report.txt $REPORT_DIR/; fi

# 5. Logical Validation
python3 $TESTS_DIR/test_outputs.py
VALIDATION_STATUS=$?

# 6. Final Score Reporting (compatible with platform standards)
if [ $VALIDATION_STATUS -eq 0 ]; then
    echo "Task Status: Passed"
    echo "Reward: 1.0"
else
    echo "Task Status: Failed"
    echo "Reward: 0.0"
fi

exit $VALIDATION_STATUS
