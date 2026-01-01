import subprocess
import os
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

def compile_cobol():
    """Compiles the COBOL validator."""
    source_path = "../environment/app/validate.cbl"
    if not os.path.exists(source_path):
        # Fallback for different CWD
        source_path = "environment/app/validate.cbl"
        if not os.path.exists(source_path):
             source_path = "validate.cbl" # last resort
             
    subprocess.run(["cobc", "-x", "-O2", "-o", "validator_cobol", source_path], check=True)

def build_java():
    """Builds the Java validator."""
    # Assuming mvn is handling the build of the uber jar
    # We should run this from the project root usually, but here we can try
    # to run mvn package if jar doesn't exist.
    # ideally the test environment already built it via test.sh, but we can verify.
    pass

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

def test_checksum_failure():
    compile_cobol()
    p = {'no': 123456781, 'holder': 'X', 'prem': 100.0, 'tax': 10.0, 'due': 110.0, 'risk': '3', 'country': 'US', 'acc': 9876543210, 'age': 30}
    generate_insurance_file("insurance.dat", [p])
    res = subprocess.run(["./validator_cobol"], capture_output=True, text=True)
    assert res.returncode == 1
    assert res.stdout.strip() == "CHECKSUM_ERR"

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

# --- Performance Benchmark ---

def test_performance_benchmark():
    """Confirms Java implementation is within 1.5x of COBOL execution time on 500k records."""
    # 1. Generate 500k records
    print("\nGenerating benchmark data...")
    header = "H20231001BENCHMARK NY\n"
    policy_fmt = "P{:010d}{:<20}{:08d}{:08d}{:08d}{}{:2}{:010d}{:03d}\n"
    trailer_fmt = "T{:05d}{:012d}{:012d}{:012d}\n"
    
    with open("benchmark.dat", "w") as f:
        f.write(header)
        for i in range(500000):
            # Valid-ish
            f.write(policy_fmt.format(100000000+i, "Bench User", 10000, 1000, 11000, "3", "US", 9000000000+i, 30))
        f.write(trailer_fmt.format(500000, 5000000000, 500000000, 5500000000))
        
    compile_cobol()
    
    # 2. Measure COBOL
    print("Running COBOL Benchmark...")
    start = time.time()
    subprocess.run(["./validator_cobol"], stdin=open("benchmark.dat"), stdout=subprocess.DEVNULL)
    cobol_time = time.time() - start
    print(f"COBOL Time: {cobol_time:.4f}s")
    
    # 3. Measure Java (must exist)
    jar_path = "../environment/app/target/validator.jar"
    # Fallback path if we are in environment/app
    if not os.path.exists(jar_path):
         jar_path = "target/validator.jar"
    
    if not os.path.exists(jar_path):
        pytest.fail("Java validator JAR not found. Build failed or skipped.")
        
    print("Running Java Benchmark...")
    start = time.time()
    subprocess.run(["java", "-jar", jar_path], stdin=open("benchmark.dat"), stdout=subprocess.DEVNULL)
    java_time = time.time() - start
    print(f"Java Time: {java_time:.4f}s")
    
    # 4. Assert
    limit = cobol_time * 1.5
    assert java_time <= limit, f"Java ({java_time:.4f}s) is too slow (> {limit:.4f}s, COBOL was {cobol_time:.4f}s)"

