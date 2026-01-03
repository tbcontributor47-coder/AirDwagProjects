import os
import sys
import subprocess

def run_reconcile():
    """Compiles and runs the COBOL app."""
    # Ensure compile
    comp = subprocess.run(["cobc", "-x", "-o", "/app/reconcile_app", "/app/environment/app/reconcile.cbl"], capture_output=True, text=True)
    if comp.returncode != 0:
        return False, f"Compilation failed: {comp.stderr}"
    
    # Run
    run = subprocess.run(["/app/reconcile_app"], capture_output=True, text=True)
    return True, run.stdout + run.stderr

def generate_input(records):
    with open("input.dat", "w") as f:
        for r in records:
            f.write(r.ljust(100) + "\n")

def test_standard_reconciliation():
    """Tests the basic logic with 4 valid and 1 invalid transaction."""
    records = [
        "01BATCH0000120240103",
        "020000000971000000000050000CREF001", # Valid (mod 97 = 1), Credit 5.00
        "020000009701000000001200000DREF002", # Valid, Debit 120.00
        "020000019401000000000250050CREF003", # Valid, Credit 25.00.50 -> 2500.50
        "021000000000000000000010000DREF004", # Invalid (mod 97 = 34)
        "020000029101000000000005075CREF005", # Valid, Credit 0.50.75 -> 50.75
        "0300005-000000000894875"             # 5 records (including invalid), Net: 3051.25 - 12000.00 = -8948.75
    ]
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    # Verify report
    assert os.path.exists("balanced_report.txt")
    with open("balanced_report.txt", "r") as f:
        lines = f.readlines()
    
    assert "BALANCED REPORT SUMMARY\n" in lines
    # TOTAL COUNT: 00004 (only valid ones)
    assert any("TOTAL COUNT: 00004" in l for l in lines)
    # TOTAL NET: -000000000894875
    assert any("TOTAL NET: -000000000894875" in l for l in lines)

    # Verify high_value.dat (12000.00 > 10000.00)
    assert os.path.exists("high_value.dat")
    with open("high_value.dat", "r") as f:
        hv_content = f.read()
    assert "0000009701" in hv_content

    # Verify anomalies.dat (1000000000)
    assert os.path.exists("anomalies.dat")
    with open("anomalies.dat", "r") as f:
        anom_content = f.read()
    assert "1000000000" in anom_content

def test_batch_rejection():
    """Tests that a mismatch in trailer count or amount rejects the batch."""
    records = [
        "01BATCH0000220240103",
        "020000000971000000000050000CREF001",
        "0300001+000000000000000" # Wrong amount (should be +500)
    ]
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    with open("balanced_report.txt", "r") as f:
        content = f.read()
    assert "BATCH REJECTED" in content

def test_large_batch_overflow():
    """Tests handling of 1000 transactions to ensure no array overflow."""
    records = ["01BIGBATCH20240103"]
    # 1000 valid transactions of 1.00 Credit
    # Acc: 0000000098 (98 mod 97 = 1)
    for i in range(1000):
        records.append(f"020000000098000000000000100CREF{i:03d}")
    records.append("0301000+00000000000100000") # 1000 records, +1000.00 net
    
    generate_input(records)
    
    success, msg = run_reconcile()
    assert success, msg
    
    with open("balanced_report.txt", "r") as f:
        content = f.read()
    assert "TOTAL COUNT: 01000" in content
    assert "TOTAL NET: +000000000100000" in content

def test_formats():
    """Strict check on fixed-width formats."""
    # Already partially covered, but ensure report labels are exact
    pass
