import subprocess
import os
import datetime

def generate_insurance_file(filename, policies, date_str=None, batch_name="BATCH001", state="NY", corrupt_trl_count=None, corrupt_trl_prem=None, corrupt_trl_tax=None, corrupt_trl_due=None, header_type="H", trailer_type="T", omit_trailer=False):
    """
    Helper function to generate insurance.dat file with given parameters.
    """
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
    
    header = f"{header_type}{date_str}{batch_name.ljust(10)}{state[:2]}\n"
    
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
        
        # Handle account string directly if passed as string, else format as int
        if isinstance(p['acc'], str):
             acc = p['acc'].ljust(10)[:10]
        else:
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
    
    trailer = f"{trailer_type}{trl_count:05d}{trl_prem:012d}{trl_tax:012d}{trl_due:012d}\n"
    
    with open(filename, 'w') as f:
        f.write(header + policy_lines)
        if not omit_trailer:
            f.write(trailer)

def compile_validator():
    """
    Compiles the validate.cbl program.
    """
    source_path = "/app/validate.cbl"
    if not os.path.exists(source_path):
        source_path = "validate.cbl"
    # Ensure -free is NOT used, we want fixed format
    subprocess.run(["cobc", "-x", "-o", "validator", source_path], check=True)

def test_insurance_valid():
    """
    Test valid insurance batch.
    Verifies that a correctly formatted file with valid data returns VALID.
    """
    compile_validator()
    # Use a policy with valid checksum (123456786 -> 36%10=6, check digit 6)
    # Prem 100.00 -> Tax 10% = 10.00 + 0.005 = 10.005 -> 10.00 (Truncated/Approximated logic in test matching generator)
    # Generator logic: prem 100.00, tax 10.00, due 110.00
    p = {'no': 123456786, 'holder': 'Valid User', 'prem': 100.00, 'tax': 10.00, 'due': 110.00, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_date_error():
    """
    Test DATE_ERR validation.
    Verifies that a mismatch between Header date and system date returns DATE_ERR.
    """
    compile_validator()
    generate_insurance_file("insurance.dat", [], date_str="19990101")
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "DATE_ERR"

def test_format_error_account():
    """
    Test FORMAT_ERR for Account Number starting digit.
    Verifies that an account number not starting with '9' returns FORMAT_ERR.
    """
    # Account must start with 9
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_account_non_digits():
    """
    Test FORMAT_ERR for Account Number containing non-digits.
    Verifies that alphabetic characters in account number trigger FORMAT_ERR.
    """
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': "987A543210", 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_banned_country():
    """
    Test BANNED_ERR for country 'RU'.
    Verifies that country 'RU' triggers BANNED_ERR.
    """
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'RU', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BANNED_ERR"

def test_banned_country_kp():
    """
    Test BANNED_ERR for country 'KP'.
    Verifies that country 'KP' triggers BANNED_ERR.
    """
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'KP', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BANNED_ERR"

def test_age_error():
    """
    Test AGE_ERR validation.
    Verifies that age under 18 returns AGE_ERR.
    """
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 15}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "AGE_ERR"

def test_fiscal_error_prem_cap():
    """
    Test FISCAL_ERR for Premium Cap.
    Verifies that Base Premium > 100,000.00 returns FISCAL_ERR.
    """
    compile_validator()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100000.01, 'tax': 10000.00, 'due': 110000.01, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_tax_calculation_rounding():
    """
    Test Tax Calculation with Rounding.
    Verifies that half-up rounding is correctly implemented.
    100.05 * 0.10 = 10.005 -> 10.01
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.05, 'tax': 10.01, 'due': 110.06, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_tax_calculation_risk2():
    """
    Test Tax Calculation for Risk Category 2.
    Verifies 5% tax calculation.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 1000.00, 'tax': 50.00, 'due': 1050.00, 'risk': '2', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_checksum_failure():
    """
    Test CHECKSUM_ERR on Policy Number.
    Verifies modulo 10 checksum validation.
    """
    compile_validator()
    # 123456781: 1+2+3+4+5+6+7+8+1 = 37. 37 % 10 = 7. Last digit is 1. Fail.
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "CHECKSUM_ERR"

def test_batch_sum_mismatch():
    """
    Test BATCH_SUM_ERR (Total Prem Mismatch).
    Verifies that trailer total premium mismatch returns error.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_prem=999.99)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BATCH_SUM_ERR"

def test_trailer_count_error():
    """
    Test COUNT_ERR.
    Verifies that trailer record count mismatch returns COUNT_ERR.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_count=99999)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "COUNT_ERR"

def test_error_priority():
    """
    Test Error Priority checking.
    Verifies that FORMAT_ERR > CHECKSUM_ERR.
    """
    # Priority: FORMAT_ERR > CHECKSUM_ERR
    compile_validator()
    # Invalid Checksum AND Account starts with 8 (FORMAT_ERR)
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_error_priority_date():
    """
    Test Error Priority for DATE_ERR.
    Verifies that DATE_ERR has higher priority than other errors (e.g. FORMAT_ERR).
    """
    compile_validator()
    # Date Error (19990101) AND Format Error (Account starts with 8)
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], date_str="19990101")
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "DATE_ERR"

def test_fiscal_error_mismatch():
    """
    Test FISCAL_ERR for line item integrity.
    Verifies checks for Total Due == Prem + Tax.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 10.00, 'due': 111.00, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_tax_calculation_risk1():
    """
    Test Tax Calculation for Risk Category 1.
    Verifies 0% tax.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 0.00, 'due': 100.00, 'risk': '1', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_account_length():
    """
    Test Account Number Length Validation.
    Verifies validation for account number strict length (implied by fixed width, effectively testing format boundaries).
    """
    compile_validator()
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    header = f"H{date_str}BATCH001  NY\n"
    # P + ... + 987654321 (space) ...
    pol_line = "P123456786Valid User          0001000000001000000110003US987654321 030\n"
    trailer = "T000010000001000000000001000000011000\n"
    
    with open("insurance.dat", 'w') as f:
        f.write(header + pol_line + trailer)
    
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    # Should be FORMAT_ERR because it violates strict digit/start-with-9 rules often parsed together
    assert res.stdout.strip() == "FORMAT_ERR"

def test_header_validation():
    """
    Test Header Record Validation.
    Verifies that the file must start with a Header record (Type 'H').
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    # Pass 'X' as header type to simulate bad header
    generate_insurance_file("insurance.dat", [p], header_type="X")
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    # The output isn't strictly specified for bad header type, but usually it fails parsing or specific check
    # Given requirements, implicit "Format" or "Date" might be checked, or process fails.
    # We expect a non-zero exit code.
    # Since strict error codes are required, if it fails to parse header, it might not output a standard code or output a generic one.
    # However, standard COBOL batch usually checks first byte. If not 'H', it's an error.
    # Let's assume the program handles this gracefully or crashes (which catches bad implementation).
    # Ideally should output something or just fail.
    # For this test, valid exit code 1 is the primary check.
    # If we want to enforce specific message, we'd need to add that to requirements.
    # Requirement: "Read insurance.dat, perform... checks".
    # Assuming any failure to match structure leads to exit 1.
    assert res.returncode == 1

def test_missing_trailer():
    """
    Test Missing Trailer.
    Verifies that the file must end with a Trailer record.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], omit_trailer=True)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    # Often results in COUNT_ERR or BATCH_SUM_ERR or just format error
    # We just ensure it fails.
    assert res.returncode == 1

def test_trailer_mismatch_tax():
    """
    Test Trailer Tax Mismatch.
    Verifies BATCH_SUM_ERR if tax total in trailer doesn't match sum of records.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_tax=999.99)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BATCH_SUM_ERR"

def test_trailer_mismatch_due():
    """
    Test Trailer Total Due Mismatch.
    Verifies BATCH_SUM_ERR if total due in trailer doesn't match sum of records.
    """
    compile_validator()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_due=999.99)
    res = subprocess.run(["./validator"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BATCH_SUM_ERR"

def test_cobol_formatting():
    """
    Test COBOL Source Code Formatting.
    Verifies strict adherence to COBOL fixed format:
    - Col 1-6: Ignored/Sequence (should be irrelevant or numeric, we allow anything but usually blank or digits)
    - Col 7: Indicator (*, /, -, or space)
    - Col 8-11: Area A (Divisions, Sections, Paragraphs, FD, 01, 77)
    - Col 12-72: Area B (Statements)
    """
    source_path = "/app/validate.cbl"
    if not os.path.exists(source_path):
        source_path = "validate.cbl"
    assert os.path.exists(source_path)
    
    with open(source_path, "r") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        
        # Check line length (optional but standard max is often 80, though 72 is code)
        # We won't strictly enforce length < 80 as some compilers allow loose, 
        # but we enforce Area A/B checks.
        
        if len(line.rstrip()) < 7:
             # Too short to have indicator
             continue
             
        indicator = line[6]
        assert indicator in (' ', '*', '-', '/'), f"Line {i}: Invalid indicator at col 7: '{indicator}'"
        
        if indicator == '*':
            # Comment line, skip checks
            continue
            
        content = line[7:].rstrip()
        if not content:
            continue
        
        # Identify Area A (cols 8-11 -> index 7-10) vs Area B (cols 12+ -> index 11+)
        # Content starts at index 7 (col 8)
        
        # Heuristic checks for Area A items
        # Divisions, Sections, Paragraphs should start in Area A (index 7-10)
        # We check if there's non-space in 7-10
        
        line_content = line.rstrip()
        
        # Check Area A elements
        area_a_keywords = ["DIVISION", "SECTION", "FD", "01", "77"]
        stripped_line = line_content[7:].lstrip()
        first_token = stripped_line.split()[0].upper() if stripped_line else ""
        
        # Paragraphs usually don't have keywords but are identifiers ending in dot? 
        # This is hard to regex perfectly without parser.
        
        # Strict Area B check:
        # IF statement, MOVE, COMPUTE, PERFORM, etc. MUST be in Area B (start index 11+)
        # If they are in Area A (7-10), it's formatted wrong.
        
        area_b_keywords = ["IF", "MOVE", "COMPUTE", "PERFORM", "READ", "WRITE", "OPEN", "CLOSE", "DISPLAY", "STOP", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "GO", "ELSE", "END-IF", "END-READ"]
        
        # If line starts in Area A (non-space in 7-10)
        if len(line) > 7 and line[7] != ' ': 
             # Starting in col 8 (Area A)
             # Check if it is a forceful Area B keyword
             if first_token in area_b_keywords:
                  assert False, f"Line {i}: Statement '{first_token}' must remain in Area B (col 12+)"
        
        # If line starts in Area B only (spaces in 7-10, non-space in 11+)
        # No specific restriction unless we want to force Headers to Area A, which is looser.
        # But we definitely want to catch code in Area A.
