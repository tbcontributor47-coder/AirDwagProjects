import subprocess
import os
import datetime

def generate_insurance_file(filename, policies, date_str=None, batch_name="BATCH001", state="NY", corrupt_trl_count=None, corrupt_trl_prem=None, corrupt_trl_tax=None, corrupt_trl_due=None):
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
    
    header = f"H{date_str}{batch_name.ljust(10)}{state[:2]}\n"
    
    total_prem = 0
    total_tax = 0
    total_due = 0
    count = len(policies)
    
    policy_lines = ""
    for p in policies:
        pol_no = f"{p['no']:010d}"
        holder = p['holder'].ljust(20)[:20]
        prem_int = int(round(p['prem'] * 100))
        tax_int = int(round(p['tax'] * 100))
        due_int = int(round(p['due'] * 100))
        risk = p['risk']
        country = p['country'].ljust(2)[:2]
        acc = f"{p['acc']:010d}"
        age = f"{p['age']:03d}"
        
        policy_lines += f"P{pol_no}{holder}{prem_int:08d}{tax_int:08d}{due_int:08d}{risk}{country}{acc}{age}\n"
        
        total_prem += p['prem']
        total_tax += p['tax']
        total_due += p['due']

    trl_count = corrupt_trl_count if corrupt_trl_count is not None else count
    trl_prem = int(round((corrupt_trl_prem if corrupt_trl_prem is not None else total_prem) * 100))
    trl_tax = int(round((corrupt_trl_tax if corrupt_trl_tax is not None else total_tax) * 100))
    trl_due = int(round((corrupt_trl_due if corrupt_trl_due is not None else total_due) * 100))
    
    trailer = f"T{trl_count:05d}{trl_prem:012d}{trl_tax:012d}{trl_due:012d}\n"
    
    with open(filename, 'w') as f:
        f.write(header + policy_lines + trailer)

def compile_validator():
    source_path = "/app/validate.cbl"
    if not os.path.exists(source_path):
        source_path = "validate.cbl"
    subprocess.run(["cobc", "-x", "-o", "validator", source_path], check=True)

def test_insurance_valid():
    """Test valid insurance batch."""
    compile_validator()
    # Use a policy with valid checksum (123456786 -> 36%10=6, check digit 6)
    # Prem 100.00 -> Tax 10% = 10.00 + 0.005 = 10.005 -> 10.00 (Truncated)
    p = {'no': 123456786, 'holder': 'Valid User', 'prem': 100.00, 'tax': 10.00, 'due': 110.00, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_date_error():
    compile_validator()
    generate_insurance_file("insurance.dat", [], date_str="19990101")
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "DATE_ERR"

def test_format_error_account():
    # Account must start with 9
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"



def test_banned_country():
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'RU', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "BANNED_ERR"

def test_age_error():
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 15}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "AGE_ERR"

def test_fiscal_error_prem_cap():
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100000.01, 'tax': 10000.00, 'due': 110000.01, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_tax_calculation_rounding():
    # 100.05 * 0.10 = 10.005 -> 10.01
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.05, 'tax': 10.01, 'due': 110.06, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_tax_calculation_risk2():
    # 5% tax
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 1000.00, 'tax': 50.00, 'due': 1050.00, 'risk': '2', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_checksum_failure():
    compile_validator()
    # 1+2+3+4+5+6+7+8+1 = 37. 37 % 10 = 7. If we put 1 at end, it should fail.
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    # 0+1+2+3+4+5+6+7+8 = 36. 36 % 10 = 6. Since 10th digit is 1, it should fail.
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "CHECKSUM_ERR"

def test_batch_sum_mismatch():
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_prem=999.99)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "BATCH_SUM_ERR"

def test_trailer_count_error():
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_count=99999)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.returncode == 1
    assert res.stdout.strip() == "COUNT_ERR"

def test_error_priority():
    # Priority: FORMAT_ERR > CHECKSUM_ERR
    compile_validator()
    # Invalid Checksum (ends in 1 -> 36%10=6 != 1) AND Account starts with 8 (FORMAT_ERR)
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_fiscal_error_mismatch():
    compile_validator()
    # Total Due != Prem + Tax (111.00 != 100+10)
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 10.00, 'due': 111.00, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_tax_calculation_risk1():
    # Risk 1 -> 0% Tax
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 0.00, 'due': 100.00, 'risk': '1', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_account_length():
    # Manually create a file with an 9-digit account number padded with space (or just space at end)
    # Requirement: "Exactly 10 digits". 
    # "987654321 " has 9 digits + 1 space.
    compile_validator()
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    header = f"H{date_str}BATCH001  NY\n"
    # P + 123456786 + Valid User... (20) + 00010000 + 00001000 + 00001100 + 3 + US + 987654321  (space at end) + 030
    pol_line = "P123456786Valid User          0001000000001000000110003US987654321 030\n"
    trailer = "T000010000001000000000001000000011000\n"
    
    with open("insurance.dat", 'w') as f:
        f.write(header + pol_line + trailer)
    
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"



def test_cobol_formatting():
    source_path = "/app/validate.cbl"
    if not os.path.exists(source_path):
        source_path = "validate.cbl"
    assert os.path.exists(source_path)
    with open(source_path, "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if len(line) > 6:
            indicator = line[6]
            assert indicator in (' ', '*', '-', '/'), f"Line {i}: format error"
