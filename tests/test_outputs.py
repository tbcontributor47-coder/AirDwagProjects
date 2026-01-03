import os
import subprocess

def run_reconcile():
    """Compiles and runs the COBOL app."""
    # Source is in /app/environment/app/reconcile.cbl
    # We compile to /app/reconcile_app
    source = "/app/environment/app/reconcile.cbl"
    if not os.path.exists(source):
        # Fallback for local testing
        source = "environment/app/reconcile.cbl"
    
    print(f"Compiling {source}...")
    comp = subprocess.run(["cobc", "-x", "-o", "/app/reconcile_app", source], capture_output=True, text=True)
    if comp.returncode != 0:
        return False, f"Compilation failed: {comp.stderr}"
    
    # Run
    # Program expects "input.dat" in CWD.
    if not os.path.exists("input.dat"):
        # Create a dummy if not exists just to avoid crash, but tests should provide it
        generate_input(["01DUMMY"])
        
    print("Running /app/reconcile_app...")
    run = subprocess.run(["/app/reconcile_app"], capture_output=True, text=True)
    return True, run.stdout + run.stderr

def generate_input(records):
    """Generates a 100-char fixed-width input.dat."""
    with open("input.dat", "w") as f:
        for r in records:
            f.write(r.ljust(100) + "\n")

def check_fixed_width(filename, expected_lines=None):
    """Checks if a file exists and has 100-char wide lines."""
    assert os.path.exists(filename), f"{filename} missing"
    with open(filename, "r") as f:
        lines = f.readlines()
    
    if expected_lines is not None:
        assert len(lines) == expected_lines, f"{filename} expected {expected_lines} lines, got {len(lines)}"
    
    for i, line in enumerate(lines, 1):
        clean = line.replace("\r", "").replace("\n", "")
        # The specification requires EXACTLY 100 characters.
        # Note: Agents using LINE SEQUENTIAL must ensure they preserve trailing spaces if applicable,
        # otherwise they should use ORGANIZATION IS SEQUENTIAL.
        assert len(clean) == 100, f"{filename} line {i} is {len(clean)} chars, must be exactly 100"
    return lines

def test_standard_reconciliation():
    """Tests the basic logic with 4 valid and 1 invalid transaction."""
    records = [
        "01BATCH0000120240103",
        "020000000971000000000050000CREF001", # Valid (mod 97 = 1), Credit 5.00
        "020000009701000000001200000DREF002", # Valid, Debit 120.00
        "020000019401000000000250050CREF003", # Valid, Credit 2500.50
        "021000000000000000000010000DREF004", # Invalid (mod 97 = 34)
        "020000029101000000000005075CREF005", # Valid, Credit 50.75
        "0300005-000000000894875"             # 5 records, Net: -8948.75
    ]
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    # 1. Balanced Report: Exactly 3 lines, fixed width
    lines = check_fixed_width("balanced_report.txt", expected_lines=3)
    assert "BALANCED REPORT SUMMARY" in lines[0]
    assert "TOTAL COUNT: 00004" in lines[1]
    assert "TOTAL NET: -000000000894875" in lines[2]

    # 2. High Value: Only TRANS 002 (12000.00 > 10000.00)
    hv_lines = check_fixed_width("high_value.dat", expected_lines=1)
    assert "0000009701" in hv_lines[0]
    assert "DREF002" in hv_lines[0]

    # 3. Anomalies: Only TRANS 004 (invalid checksum)
    anom_lines = check_fixed_width("anomalies.dat", expected_lines=1)
    assert "1000000000" in anom_lines[0]
    assert "DREF004" in anom_lines[0]
    
    # 4. Exclusivity checks
    # Invalid transaction should NOT be in high_value
    assert "1000000000" not in "".join(hv_lines)
    # Valid transaction should NOT be in anomalies
    assert "0000009701" not in "".join(anom_lines)

def test_batch_rejection():
    """Tests that a mismatch in trailer count or amount rejects the batch."""
    records = [
        "01BATCH0000220240103",
        "020000000971000000000050000CREF001",
        "0300001+000000000000000" # Wrong amount
    ]
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    lines = check_fixed_width("balanced_report.txt", expected_lines=1)
    assert "BATCH REJECTED" in lines[0]

def test_batch_rejection_count_mismatch():
    """Tests that a mismatch in trailer count (RE-COUNT) rejects the batch."""
    records = [
        "01BATCH0000220240103",
        "020000000971000000000050000CREF001",
        "0300099+000000000000500" # Count 99 instead of 1
    ]
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    lines = check_fixed_width("balanced_report.txt", expected_lines=1)
    assert "BATCH REJECTED" in lines[0]

def test_large_batch_overflow():
    """Tests handling of 1000 transactions to ensure no array overflow."""
    records = ["01BIGBATCH20240103"]
    # 1000 valid transactions of 1.00 Credit
    for i in range(1000):
        records.append(f"020000000098000000000000100CREF{i:03d}")
    records.append("0301000+000000000100000") # 1000 records, +1000.00 net
    
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    lines = check_fixed_width("balanced_report.txt", expected_lines=3)
    assert "TOTAL COUNT: 01000" in lines[1]
    assert "TOTAL NET: +000000000100000" in lines[2]

def test_input_format_validation():
    """Ensures our own test input generator is correct."""
    records = ["01TEST", "02DATA"]
    generate_input(records)
    with open("input.dat", "r") as f:
        for line in f:
            assert len(line.rstrip("\r\n")) == 100
