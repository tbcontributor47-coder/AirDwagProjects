import subprocess
import os
import sys
import shutil
import datetime
import pytest
import time

# --- Helper Functions ---

def generate_insurance_file(filename, policies, date_str=None, batch_name="BATCH001", state="NY", corrupt_trl_count=None, corrupt_trl_prem=None, corrupt_trl_tax=None, corrupt_trl_due=None, header_type="H", trailer_type="T", omit_trailer=False):
    """Generates an insurance.dat file for testing."""
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

# --- Path Configuration ---
def get_source_path():
    """Finds the absolute path to validate.cbl."""
    paths_to_check = [
        # Check relative to this script
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "environment", "app", "validate.cbl"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validate.cbl"),
        # Check standard Docker/CI locations
        "/app/validate.cbl",
        "/app/environment/app/validate.cbl",
        "/tmp/project/validate.cbl",
        # Check relative to current working directory
        os.path.abspath("validate.cbl"),
        os.path.abspath("../validate.cbl"),
        os.path.abspath("environment/app/validate.cbl"),
        os.path.abspath("../environment/app/validate.cbl")
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            print(f"Found COBOL source at: {path}", file=sys.stderr)
            return path
            
    print(f"ERROR: Could not find validate.cbl. Checked: {paths_to_check}", file=sys.stderr)
    # Return "validate.cbl" as last resort so cobc error is clear
    return "validate.cbl"

def compile_cobol():
    """Compiles the COBOL validator."""
    source_path = get_source_path()
    subprocess.run(["cobc", "-x", "-O2", "-o", "validator_cobol", source_path], check=True)

def compile_cobol_baseline():
    """Compiles the COBOL validator from the immutable baseline for performance benchmarking."""
    # Use the pristine baseline COBOL from the Docker image, not the agent's modified version
    # This prevents gaming the benchmark by intentionally slowing down COBOL
    baseline_path = "/baseline/validate.cbl"
    if not os.path.exists(baseline_path):
        baseline_path = "/app/validate.cbl"
    
    if not os.path.exists(baseline_path):
        # Fallback for local testing
        baseline_path = get_source_path()
    subprocess.run(["cobc", "-x", "-O2", "-o", "validator_cobol_baseline", baseline_path], check=True)

def run_validator(binary="./validator_cobol", stdin_file="insurance.dat"):
    """Runs the specified validator (COBOL or Java)."""
    if binary.endswith(".jar"):
        cmd = ["java", "-jar", binary]
    else:
        cmd = [binary]
    
    with open(stdin_file, 'rb') as f:
        result = subprocess.run(cmd, input=f.read(), capture_output=True)
    
    # Decode bytes to strings for compatibility with test assertions
    class Result:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout.decode('utf-8') if isinstance(stdout, bytes) else stdout
            self.stderr = stderr.decode('utf-8') if isinstance(stderr, bytes) else stderr
    
    return Result(result.returncode, result.stdout, result.stderr)

def build_java():
    """Builds the Java validator."""
    paths_to_check = [
        # Relative to test file location
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "environment", "app", "target", "validator.jar"),
        # Oracle/Docker environment
        "/app/target/validator.jar",
        # Relative to CWD
        "target/validator.jar",
        os.path.abspath("target/validator.jar")
    ]
    
    for jar_path in paths_to_check:
        if os.path.exists(jar_path):
            return jar_path
    
    return None

# --- COBOL Tests ---

def test_insurance_valid():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'Valid User', 'prem': 100.00, 'tax': 10.00, 'due': 110.00, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_date_error():
    compile_cobol()
    generate_insurance_file("insurance.dat", [], date_str="19990101")
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "DATE_ERR"

def test_format_error_account():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_account_non_digits():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': "987A543210", 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FORMAT_ERR"

def test_banned_country():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'RU', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BANNED_ERR"

def test_banned_country_kp():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'KP', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BANNED_ERR"

def test_age_error():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 15}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "AGE_ERR"

def test_fiscal_error_prem_cap():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100000.01, 'tax': 10000.00, 'due': 110000.01, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_tax_calculation_rounding():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.05, 'tax': 10.01, 'due': 110.06, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_tax_calculation_risk2():
    # 5% tax
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 1000.00, 'tax': 50.00, 'due': 1050.00, 'risk': '2', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_tax_calculation_risk1():
    # 0% tax
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 1000.00, 'tax': 0.00, 'due': 1000.00, 'risk': '1', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip() == "VALID"

def test_checksum_failure():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "CHECKSUM_ERR"

def test_fiscal_error_due_mismatch():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 10.00, 'due': 999.99, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "FISCAL_ERR"

def test_error_priority_age_vs_tax():
    # Age (4) vs Tax (7). Should report AGE_ERR.
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.00, 'tax': 99.99, 'due': 199.99, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 10}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "AGE_ERR"

def test_batch_sum_mismatch():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_prem=999.99)
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "BATCH_SUM_ERR"

def test_trailer_count_error():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], corrupt_trl_count=99999)
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "COUNT_ERR"

def test_missing_trailer():
    compile_cobol()
    p = {'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p], omit_trailer=True)
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "COUNT_ERR"

def test_error_priority_checksum_vs_batch():
    # Checksum (8) vs Batch Sum (9). Should report CHECKSUM_ERR.
    compile_cobol()
    # Policy with inner checksum fail (123456781 -> 36%10=6!=1)
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    # And corrupt trailer to trigger BATCH_SUM_ERR
    generate_insurance_file("insurance.dat", [p], corrupt_trl_prem=999.99)
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "CHECKSUM_ERR"

# --- Java Correctness Validation ---

def test_java_correctness():
    """Validates Java implementation against THE ENTIRE TEST SUITE."""
    jar_path = build_java()
    if not jar_path:
        pytest.skip("Java JAR not found")
    
    # List of test cases: (policies, expected_out, date_str, kwargs)
    test_cases = [
        ([{'no': 123456786, 'holder': 'Valid', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}], "VALID", None, {}),
        ([], "DATE_ERR", "19990101", {}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 8876543210, 'age': 30}], "FORMAT_ERR", None, {}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'KP', 'acc': 9876543210, 'age': 30}], "BANNED_ERR", None, {}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 150}], "AGE_ERR", None, {}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100000.01, 'tax': 10000.00, 'due': 110000.01, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}], "FISCAL_ERR", None, {}),
        ([{'no': 123456786, 'holder': 'X', 'prem': 1000.0, 'tax': 0.0, 'due': 1000.0, 'risk': '1', 'country': 'US', 'acc': 9876543210, 'age': 30}], "VALID", None, {}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 50.0, 'due': 150.0, 'risk': '2', 'country': 'US', 'acc': 9876543210, 'age': 10}], "AGE_ERR", None, {}), # Age(4) vs Tax(7)
        ([{'no': 123456786, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}], "COUNT_ERR", None, {'corrupt_trl_count': 99}),
        ([{'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}], "CHECKSUM_ERR", None, {'corrupt_trl_prem': 999.99}), # Checksum(8) vs Batch(9)
    ]
    
    for policies, expected, d_str, kwargs in test_cases:
        generate_insurance_file("insurance.dat", policies, date_str=d_str, **kwargs)
        res = run_validator(jar_path)
        assert res.stdout.strip() == expected, f"Java failed for {expected}. Got {res.stdout.strip()}"

# --- Performance Benchmark ---

def test_performance_benchmark():
    """Confirms Java implementation is within 1.5x of COBOL execution time on 500k records."""
    # 1. Generate 500k records
    print("\nGenerating benchmark data...")
    header = f"H{datetime.datetime.now().strftime('%Y%m%d')}BENCHMARK NY\n"
    policy_fmt = "P{:010d}{:<20}{:08d}{:08d}{:08d}{}{:2}{:010d}{:03d}\n"
    trailer_fmt = "T{:05d}{:012d}{:012d}{:012d}\n"
    
    with open("benchmark.dat", "w") as f:
        f.write(header)
        for i in range(2000000):
            # Generate valid checksum: Use 9-digit base, calc 10th digit
            base_pol = 100000000 + i
            # Sum digits 1-9
            s = sum(int(d) for d in str(base_pol))
            check_digit = s % 10
            full_pol = base_pol * 10 + check_digit
            
            # Valid-ish record
            f.write(policy_fmt.format(full_pol, "Bench User", 10000, 1000, 11000, "3", "US", 9000000000+i, 30))
        f.write(trailer_fmt.format(2000000, 20000000000, 2000000000, 22000000000))
        
    # Compile from immutable baseline to prevent gaming the benchmark
    compile_cobol_baseline()
    
    # 2. Measure COBOL (using baseline)
    print("Running COBOL Benchmark...")
    shutil.copy("benchmark.dat", "insurance.dat")
    start = time.time()
    # Check return code to ensure COBOL actually ran and didn't crash
    proc = subprocess.run(["./validator_cobol_baseline"], stdin=open("benchmark.dat"), capture_output=True)
    if proc.returncode != 0:
        print(f"COBOL Failed! Stderr: {proc.stderr.decode()}", file=sys.stderr)
        pytest.fail(f"COBOL benchmark failed with RC {proc.returncode}")
    cobol_time = time.time() - start
    print(f"COBOL Time: {cobol_time:.4f}s")
    
    # 3. Measure Java (must exist)
    jar_path = build_java()
    if not jar_path:
        pytest.fail("Java validator JAR not found. Build failed or skipped.")
        
    print("Running Java Benchmark...")
    start = time.time()
    proc_java = subprocess.run(["java", "-jar", jar_path], stdin=open("benchmark.dat"), capture_output=True)
    if proc_java.returncode != 0:
         print(f"Java Failed! Stderr: {proc_java.stderr.decode()}", file=sys.stderr)
         pytest.fail(f"Java benchmark failed with RC {proc_java.returncode}")
    java_time = time.time() - start
    print(f"Java Time: {java_time:.4f}s")
    
    # 4. Assert
    # Limit = COBOL * 1.5 (Strict Mode: No JVM startup buffer)
    limit = cobol_time * 1.5
    assert java_time <= limit, f"Java ({java_time:.4f}s) is too slow (> {limit:.4f}s, COBOL was {cobol_time:.4f}s)"

