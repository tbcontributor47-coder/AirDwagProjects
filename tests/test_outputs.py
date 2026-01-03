import os
import sys

def validate():
    print("Starting deep logic validation...")
    
    # 1. Check if balanced_report.txt exists
    report_path = "environment/reports/balanced_report.txt"
    if not os.path.exists(report_path):
        # Fallback to current dir if not moved
        report_path = "balanced_report.txt"
        
    if not os.path.exists(report_path):
        print("Error: balanced_report.txt not found")
        return False
        
    with open(report_path, 'r') as f:
        content = f.read()
        print(f"Report Content:\n{content}")
        
        # Expected values based on input.dat:
        # Valid: 0000000971 (C 500.00), 0000009701 (D 12000.00), 0000019401 (C 2500.50), 0000029101 (C 50.75)
        # Invalid: 1000000000 (mod 97 == 34)
        # Total valid credits: 500.00 + 2500.50 + 50.75 = 3051.25
        # Total valid debits: 12000.00
        # Net = Credits - Debits = 3051.25 - 12000.00 = -8948.75
        
        if "TOTAL COUNT: 00004" not in content:
            print("Error: Incorrect valid transaction count in report")
            return False
        if "-000000000894875" not in content and "-8948.75" not in content:
             # Check for different possible formats
             print("Error: Net balance mismatch in report")
             return False

    # 2. Check high_value.dat
    hv_path = "high_value.dat"
    if not os.path.exists(hv_path):
        print("Error: high_value.dat not found")
        return False
    
    with open(hv_path, 'r') as f:
        lines = f.readlines()
        if len(lines) != 1:
            print(f"Error: Expected 1 high-value transaction, found {len(lines)}")
            return False
        if "0000009701" not in lines[0]:
            print("Error: Incorrect transaction in high_value.dat")
            return False

    # 3. Check anomalies.dat
    anom_path = "anomalies.dat"
    if not os.path.exists(anom_path):
        print("Error: anomalies.dat not found")
        return False
        
    with open(anom_path, 'r') as f:
        content = f.read()
        if "1000000000" not in content:
            print("Error: Invalid account 1000000000 not found in anomalies.dat")
            return False

    print("Success: All logic checks passed!")
    return True

if __name__ == "__main__":
    if validate():
        sys.exit(0)
    else:
        sys.exit(1)
