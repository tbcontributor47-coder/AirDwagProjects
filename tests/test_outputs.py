import subprocess
import os
import datetime

def generate_site_file(filename, details_data, date_str=None, header_pat="HHHHHHHHHH", trailer_pat="TTTTTTTTTT", corrupt_count=None, corrupt_total=None, corrupt_comp=None, corrupt_pend=None):
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        
    header = f"{date_str}{header_pat}\n"
    
    total_val = 0
    total_comp = 0
    total_pend = 0
    count = len(details_data)
    
    details_str = ""
    for d in details_data:
        owner = d['owner'].ljust(20)[:20]
        acc = d['acc'].ljust(20)[:20]
        sno = f"{d['sno']:05d}"
        loc = d['loc'].ljust(30)[:30]
        det = d['det'].ljust(50)[:50]
        agree = d['agree']
        phone = d['phone'].ljust(15)[:15]
        val_int = int(round(d['val'] * 100))
        val_str = f"{val_int:011d}"
        
        details_str += f"{owner}{acc}{sno}{loc}{det}{agree}{phone}{val_str}\n"
        
        total_val += d['val']
        if agree == 'Y':
            total_comp += d['val']
        else:
            total_pend += d['val']
            
    final_count = corrupt_count if corrupt_count is not None else count
    final_total = corrupt_total if corrupt_total is not None else total_val
    final_comp = corrupt_comp if corrupt_comp is not None else total_comp
    final_pend = corrupt_pend if corrupt_pend is not None else total_pend
    
    trailer = f"{final_count:05d}{int(round(final_total*100)):011d}{int(round(final_comp*100)):011d}{int(round(final_pend*100)):011d}{trailer_pat}\n"
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        f.write(header + details_str + trailer)

def test_real_estate_merge():
    """Test full 5-file merge with valid data."""
    # 1. Setup 5 valid files
    for i in range(1, 6):
        data = [{'owner': f'USER{i}', 'acc': f'ACC{i}', 'sno': i, 'loc': f'LOC{i}', 'det': f'DET{i}', 'agree': 'Y' if i % 2 == 0 else 'N', 'phone': '555', 'val': 123.45 * i}]
        generate_site_file(f"data/site{i}.dat", data)

    # 2. Compile
    compile_cmd = ["cobc", "-x", "-o", "merge_app", "/app/merge.cbl"]
    try:
        subprocess.run(compile_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        assert False, f"Compilation failed: {e.stderr.decode()}"

    # 3. Run
    try:
        res = subprocess.run(["./merge_app"], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        assert False, f"Execution failed: {e.stderr}"

    # 4. Verify Output
    assert os.path.exists("all_sites.dat"), "all_sites.dat not generated"
    with open("all_sites.dat", "r") as f:
        lines = f.readlines()
    assert len(lines) == 5, f"Expected 5 records in merge file, got {len(lines)}"

def test_date_validation_failure():
    """Header date must be today."""
    for i in range(1, 6):
        generate_site_file(f"data/site{i}.dat", [])
    # Corrupt site1 with old date
    generate_site_file("data/site1.dat", [], date_str="19990101")
    
    res = subprocess.run(["./merge_app"], capture_output=True)
    assert res.returncode != 0
    assert b"INVALID HEADER" in res.stdout or b"INVALID HEADER" in res.stderr

def test_trailer_sum_failure():
    """Trailer total value must match details."""
    for i in range(1, 6):
         generate_site_file(f"data/site{i}.dat", [{'owner': 'X', 'acc': 'Y', 'sno': 1, 'loc': 'Z', 'det': 'W', 'agree': 'Y', 'phone': '1', 'val': 1.0}])
    # Corrupt site3 trailer sum
    generate_site_file("data/site3.dat", [{'owner': 'X', 'acc': 'Y', 'sno': 1, 'loc': 'Z', 'det': 'W', 'agree': 'Y', 'phone': '1', 'val': 1.0}], corrupt_total=999.99)
    
    res = subprocess.run(["./merge_app"], capture_output=True)
    assert res.returncode != 0
    assert b"TRAILER MISMATCH" in res.stdout or b"TRAILER MISMATCH" in res.stderr

def test_cobol_formatting():
    source_path = "/app/merge.cbl"
    assert os.path.exists(source_path)
    with open(source_path, "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if not line.strip(): continue
        if len(line) > 6:
            indicator = line[6]
            assert indicator in (' ', '*', '-', '/'), f"Line {i}: format error"
