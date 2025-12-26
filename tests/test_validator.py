#!/usr/bin/env python3
"""Verifier tests for the EFT validator CLI.

Important:
- Tests must invoke the CLI (no importing from `solution/`).
- Tests check stdout JSON + exit codes + key edge cases.
"""

import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest


CLI_DEFAULT = "/app/validate_eft.py"


def _cli_path() -> str:
    return os.environ.get("EFT_VALIDATOR_CLI", CLI_DEFAULT)


@pytest.fixture
def test_env(tmp_path):
    base_dir = Path(__file__).parent.parent
    schema_src = base_dir / 'schema.json'
    clearing_src = base_dir / 'clearing_accounts.txt'

    schema_dest = tmp_path / 'schema.json'
    clearing_dest = tmp_path / 'clearing_accounts.txt'
    db_path = tmp_path / '.eft_index.db'

    shutil.copy(schema_src, schema_dest)
    shutil.copy(clearing_src, clearing_dest)

    return {
        'schema': str(schema_dest),
        'clearing': str(clearing_dest),
        'db': str(db_path),
        'tmp_path': tmp_path
    }


def _run_cli(file_path, schema, clearing, db, extra_args=None):
    cli = _cli_path()
    cmd = [sys.executable, cli, '--file', str(file_path), '--schema', schema, '--clearing-accounts', clearing, '--index', db]
    if extra_args:
        cmd.extend(extra_args)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    return proc.returncode, out, err


def _load_schema(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _make_fixed_width_line(schema: dict, overrides: dict | None = None) -> str:
    """Generate a single fixed-width record matching schema.json."""
    record_length = int(schema["record_length"])
    buf = [" "] * record_length

    data = {
        "eftno": "EFT000000001",
        "payee_name": "JOHN DOE",
        "account_no": "12345678",
        "bank_name": "ABC BANK",
        "bank_code": "1BANKCODE1",
        "amount": "100.00",
        "address": "1 MAIN ST",
        "clearance_date": "2025-12-31",
        "last_transaction_details": "REF",
        "clearing_account": "12345678901234567890",
    }
    if overrides:
        data.update(overrides)

    for f in schema["fields"]:
        name = f["name"]
        start = int(f["start"])
        length = int(f["length"])
        value = str(data.get(name, ""))
        value = value[:length]
        padded = value.ljust(length)
        buf[start : start + length] = list(padded)

    return "".join(buf)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_valid_file_validation(test_env):
    test_file = Path(__file__).parent / 'data' / 'valid_payment.txt'

    rc, out, err = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc == 0
    report = json.loads(out)
    assert set(report.keys()) >= {
        "duplicate",
        "n_errors",
        "n_warnings",
        "errors",
        "warnings",
        "file_hash",
        "records_processed",
    }
    assert report['duplicate'] is False
    assert report['n_errors'] == 0
    assert report['records_processed'] == 3
    assert len(report['file_hash']) == 64


def test_duplicate_detection(test_env):
    test_file = Path(__file__).parent / 'data' / 'duplicate_payment.txt'

    rc1, out1, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc1 == 0
    rep1 = json.loads(out1)
    assert rep1['duplicate'] is False

    rc2, out2, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    # second run should return non-zero due to duplicate
    assert rc2 != 0
    rep2 = json.loads(out2)
    assert rep2['duplicate'] is True


def test_duplicate_detection_across_filenames(test_env):
    """Same content under a different filename must still count as duplicate."""
    schema = _load_schema(test_env["schema"])
    line = _make_fixed_width_line(schema)

    f1 = Path(test_env["tmp_path"]) / "a.txt"
    f2 = Path(test_env["tmp_path"]) / "b.txt"
    _write_text(f1, line + "\n")
    _write_text(f2, line + "\n")

    rc1, out1, _ = _run_cli(f1, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc1 == 0
    assert json.loads(out1)["duplicate"] is False

    rc2, out2, _ = _run_cli(f2, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc2 != 0
    assert json.loads(out2)["duplicate"] is True


def test_invalid_file_validation(test_env):
    test_file = Path(__file__).parent / 'data' / 'invalid_payment.txt'
    rc, out, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    # validator should exit non-zero when errors are present
    assert rc != 0
    rep = json.loads(out)
    assert rep['n_errors'] > 0


def test_errors_include_line_numbers_and_multiple_issues(test_env):
    """Errors should include line numbers and be specific per record."""
    schema = _load_schema(test_env["schema"])
    bad_line = _make_fixed_width_line(
        schema,
        {
            "account_no": "12",  # too short
            "amount": "0.001",  # too many decimals
            "clearance_date": "2025-13-40",  # invalid date
            "clearing_account": "99999999999999999999",  # invalid
        },
    )
    f = Path(test_env["tmp_path"]) / "bad.txt"
    _write_text(f, bad_line + "\n")

    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc != 0
    rep = json.loads(out)
    assert rep["n_errors"] >= 1
    # Must include a line-number prefix
    assert any("Line 1" in e for e in rep.get("errors", []))


def test_retention_window(test_env):
    # create DB and insert an old record
    db = test_env['db']
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT NOT NULL,
            filename TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            record_count INTEGER,
            UNIQUE(file_hash, timestamp)
        )
    ''')
    old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
    test_hash = 'old_test_hash_12345'
    cursor.execute('INSERT INTO file_index (file_hash, filename, timestamp, record_count) VALUES (?, ?, ?, ?)', (test_hash, 'old.txt', old_timestamp, 1))
    conn.commit()
    conn.close()

    # call CLI check_duplicate via running validator on a different file; the old hash should not trigger duplicate
    test_file = Path(__file__).parent / 'data' / 'valid_payment.txt'
    rc, out, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], db)
    assert rc == 0
    rep = json.loads(out)
    assert rep['duplicate'] is False


def test_retention_days_flag_affects_duplicate_detection(test_env):
    """--retention-days must be honored by the CLI."""
    test_file = Path(__file__).parent / 'data' / 'duplicate_payment.txt'

    rc1, out1, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--retention-days', '5'])
    assert rc1 == 0
    assert json.loads(out1)["duplicate"] is False

    # With a 0-day window, a prior run moments ago should not count.
    rc2, out2, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--retention-days', '0'])
    rep2 = json.loads(out2)
    assert rep2["duplicate"] is False


def test_hash_normalization_crlf_and_trailing_spaces(test_env):
    """Same logical lines with different line endings/trailing spaces should hash the same."""
    schema = _load_schema(test_env["schema"])
    line = _make_fixed_width_line(schema, {"eftno": "EFTNORM00001"})
    # one version has trailing spaces, CRLF, and extra blank lines
    f1 = Path(test_env["tmp_path"]) / "norm1.txt"
    f2 = Path(test_env["tmp_path"]) / "norm2.txt"
    _write_text(f1, (line + "   \r\n\r\n"))
    _write_text(f2, (line + "\n"))

    rc1, out1, _ = _run_cli(f1, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc1 == 0
    assert json.loads(out1)["duplicate"] is False

    rc2, out2, _ = _run_cli(f2, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc2 != 0
    assert json.loads(out2)["duplicate"] is True


def test_clearing_account_requires_exact_match_not_substring(test_env):
    """clearing_account must match an allowed account exactly (no substring matching)."""
    schema = _load_schema(test_env["schema"])

    # Override clearing accounts to create a substring trap
    clearing_path = Path(test_env["tmp_path"]) / "clearing_accounts.txt"
    _write_text(clearing_path, "1234567890\n")

    line = _make_fixed_width_line(schema, {"clearing_account": "2345"})
    f = Path(test_env["tmp_path"]) / "sub.txt"
    _write_text(f, line + "\n")

    rc, out, _ = _run_cli(f, test_env['schema'], str(clearing_path), test_env['db'])
    assert rc != 0
    rep = json.loads(out)
    assert rep["n_errors"] >= 1


def test_randomized_record_not_hardcoded(test_env):
    """A small randomized valid record should validate (guards against hardcoding)."""
    schema = _load_schema(test_env["schema"])
    rnd = random.Random(1337)

    eftno = f"EFT{rnd.randint(10000000, 99999999)}".ljust(12, "0")[:12]
    acct = str(rnd.randint(10**7, 10**12)).zfill(8)[:8]
    amount = f"{rnd.randint(1, 9999)}.{rnd.randint(0, 99):02d}"

    line = _make_fixed_width_line(schema, {"eftno": eftno, "account_no": acct, "amount": amount})
    f = Path(test_env["tmp_path"]) / "rand.txt"
    _write_text(f, line + "\n")

    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc == 0
    rep = json.loads(out)
    assert rep["n_errors"] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-q'])


def test_exact_record_length_enforced(test_env):
    """Lines must be exactly the schema's `record_length` (no shorter or longer)."""
    schema = _load_schema(test_env["schema"])
    line = _make_fixed_width_line(schema)

    # valid (exact length) should pass
    f_valid = Path(test_env["tmp_path"]) / "valid_len.txt"
    _write_text(f_valid, line + "\n")
    rc, out, _ = _run_cli(f_valid, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc == 0

    # short line should fail
    f_short = Path(test_env["tmp_path"]) / "short.txt"
    _write_text(f_short, line[:-1] + "\n")
    rc_s, out_s, _ = _run_cli(f_short, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc_s != 0
    rep_s = json.loads(out_s)
    assert rep_s['n_errors'] >= 1

    # long line should fail
    f_long = Path(test_env["tmp_path"]) / "long.txt"
    _write_text(f_long, line + "X\n")
    rc_l, out_l, _ = _run_cli(f_long, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc_l != 0
    rep_l = json.loads(out_l)
    # expect an error mentioning length (either explicit or generic field errors)
    assert rep_l['n_errors'] >= 1


def test_required_fields_empty_are_reported(test_env):
    """Required fields left empty must produce an error with line number."""
    schema = _load_schema(test_env["schema"])
    bad_line = _make_fixed_width_line(schema, {"eftno": ""})
    f = Path(test_env["tmp_path"]) / "req_empty.txt"
    _write_text(f, bad_line + "\n")

    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc != 0
    rep = json.loads(out)
    assert rep['n_errors'] >= 1
    assert any("eftno" in e.lower() or "Field 'eftno'" in e for e in rep.get('errors', []))
    assert any("Line 1" in e for e in rep.get('errors', []))


def test_eftno_and_bank_code_alphanumeric_constraints(test_env):
    """eftno and bank_code should be alphanumeric; non-alnum values must error."""
    schema = _load_schema(test_env["schema"])
    # include punctuation in eftno and bank_code
    bad_line = _make_fixed_width_line(schema, {"eftno": "EFT#123!@#", "bank_code": "BANK CODE!"})
    f = Path(test_env["tmp_path"]) / "alnum.txt"
    _write_text(f, bad_line + "\n")

    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc != 0
    rep = json.loads(out)
    # Expect at least one error mentioning eftno or bank_code
    errors_text = "\n".join(rep.get('errors', []))
    assert ("eftno" in errors_text.lower()) or ("bank_code" in errors_text.lower()) or rep['n_errors'] >= 1


def test_account_forbidden_prefixes(test_env):
    """Account numbers with forbidden prefixes (0000, 0001, 0010, 0100) must error."""
    schema = _load_schema(test_env["schema"])
    
    forbidden = ["00001234", "00012345", "00101234", "01001234"]
    for acc in forbidden:
        line = _make_fixed_width_line(schema, {"account_no": acc})
        f = Path(test_env["tmp_path"]) / f"prefix_{acc}.txt"
        _write_text(f, line + "\n")
        
        rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
        assert rc != 0
        rep = json.loads(out)
        assert rep['n_errors'] >= 1


def test_account_first_four_only_zeros_and_ones(test_env):
    """First 4 digits consisting only of 0 and 1 must error."""
    schema = _load_schema(test_env["schema"])
    
    invalid = ["01011234", "11001234", "10101234", "00111234"]
    for acc in invalid:
        line = _make_fixed_width_line(schema, {"account_no": acc})
        f = Path(test_env["tmp_path"]) / f"first4_{acc}.txt"
        _write_text(f, line + "\n")
        
        rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
        assert rc != 0
        rep = json.loads(out)
        errors_text = "\n".join(rep.get('errors', []))
        assert "First 4 digits" in errors_text or "0 and 1" in errors_text


def test_account_last_four_cannot_have_zeros(test_env):
    """Last 4 digits containing 0 must error."""
    schema = _load_schema(test_env["schema"])
    
    invalid = ["12345670", "23456700", "34567000", "45678901"]
    for acc in invalid:
        line = _make_fixed_width_line(schema, {"account_no": acc})
        f = Path(test_env["tmp_path"]) / f"last4_{acc}.txt"
        _write_text(f, line + "\n")
        
        rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
        assert rc != 0
        rep = json.loads(out)
        errors_text = "\n".join(rep.get('errors', []))
        assert "Last 4 digits" in errors_text or "cannot contain 0" in errors_text


def test_bank_code_must_start_with_digit(test_env):
    """Bank code must start with a digit (0-9)."""
    schema = _load_schema(test_env["schema"])
    
    line = _make_fixed_width_line(schema, {"bank_code": "ABCD123456"})
    f = Path(test_env["tmp_path"]) / "bank_start.txt"
    _write_text(f, line + "\n")
    
    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc != 0
    rep = json.loads(out)
    errors_text = "\n".join(rep.get('errors', []))
    assert "must start with a digit" in errors_text or "Bank code" in errors_text


def test_bank_code_no_lowercase_or_special_chars(test_env):
    """Bank code cannot have lowercase or special characters."""
    schema = _load_schema(test_env["schema"])
    
    # lowercase
    line1 = _make_fixed_width_line(schema, {"bank_code": "1BankCode"})
    f1 = Path(test_env["tmp_path"]) / "bank_lower.txt"
    _write_text(f1, line1 + "\n")
    
    rc1, out1, _ = _run_cli(f1, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc1 != 0
    rep1 = json.loads(out1)
    errors_text1 = "\n".join(rep1.get('errors', []))
    assert "lowercase" in errors_text1 or "uppercase" in errors_text1
    
    # special chars
    line2 = _make_fixed_width_line(schema, {"bank_code": "1BANK-CODE"})
    f2 = Path(test_env["tmp_path"]) / "bank_special.txt"
    _write_text(f2, line2 + "\n")
    
    rc2, out2, _ = _run_cli(f2, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc2 != 0
    rep2 = json.loads(out2)
    errors_text2 = "\n".join(rep2.get('errors', []))
    assert "special" in errors_text2 or "uppercase" in errors_text2 or "digits" in errors_text2


def test_payee_database_unknown_account(test_env):
    """Accounts not in payees.db must error."""
    schema = _load_schema(test_env["schema"])
    
    # Use an account that's not in payees.db
    line = _make_fixed_width_line(schema, {"account_no": "99999999"})
    f = Path(test_env["tmp_path"]) / "unknown_acc.txt"
    _write_text(f, line + "\n")
    
    # Need to point to payees.db
    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--payees-db', 'payees.db'])
    assert rc != 0
    rep = json.loads(out)
    errors_text = "\n".join(rep.get('errors', []))
    assert "not found in payee database" in errors_text or "Account" in errors_text


def test_payee_fraud_flag_rejection(test_env):
    """Accounts with fraud_flag=1 must be rejected."""
    schema = _load_schema(test_env["schema"])
    
    # Use a fraud-flagged account from payees.db (98765432)
    line = _make_fixed_width_line(schema, {"account_no": "98765432", "payee_name": "SUSPICIOUS PERSON A"})
    f = Path(test_env["tmp_path"]) / "fraud_acc.txt"
    _write_text(f, line + "\n")
    
    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--payees-db', 'payees.db'])
    assert rc != 0
    rep = json.loads(out)
    errors_text = "\n".join(rep.get('errors', []))
    assert "fraud" in errors_text.lower() or "risk" in errors_text.lower()


def test_payee_name_mismatch(test_env):
    """Payee name in file should reasonably match registered name."""
    schema = _load_schema(test_env["schema"])
    
    # Use a valid account but wrong name
    line = _make_fixed_width_line(schema, {"account_no": "12345678", "payee_name": "TOTALLY DIFFERENT NAME"})
    f = Path(test_env["tmp_path"]) / "name_mismatch.txt"
    _write_text(f, line + "\n")
    
    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--payees-db', 'payees.db'])
    assert rc != 0
    rep = json.loads(out)
    errors_text = "\n".join(rep.get('errors', []))
    assert "name mismatch" in errors_text.lower() or "payee name" in errors_text.lower()


def test_valid_active_customer_account(test_env):
    """Valid active customer account should pass all checks."""
    schema = _load_schema(test_env["schema"])
    
    # Use a clean account from payees.db with valid pattern
    line = _make_fixed_width_line(schema, {"account_no": "12345678", "payee_name": "JOHN DOE", "bank_code": "1BANKCODE1"})
    f = Path(test_env["tmp_path"]) / "valid_active.txt"
    _write_text(f, line + "\n")
    
    rc, out, _ = _run_cli(f, test_env['schema'], test_env['clearing'], test_env['db'], extra_args=['--payees-db', 'payees.db'])
    assert rc == 0
    rep = json.loads(out)
    assert rep['n_errors'] == 0
    assert rep['records_processed'] == 1

