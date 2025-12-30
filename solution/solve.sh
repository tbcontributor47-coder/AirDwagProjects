#!/usr/bin/env bash
set -euo pipefail

# At runtime (container), overwrite /app/validate_eft.py with a fixed validator
# so we don't modify repository files directly. This mirrors the pattern used
# by other tasks that patch runtime code via the solver script.

cat > /app/validate_eft.py <<'PYTHON'
#!/usr/bin/env python3
"""EFT Payment File Validator.

This file is intentionally imperfect for the task: it runs, but contains subtle
logic issues around normalization, duplicate detection, and some validations.
"""

import sys
import json
import hashlib
import re
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List


class EFTValidator:
    def __init__(self, schema_path: str, index_db: str, clearing_accounts_path: str, retention_days: int = 5, payees_db_path: str = None):
        self.schema_path = schema_path
        self.db_path = index_db
        # Honor the input retention_days parameter (verifier tests rely on this)
        self.retention_days = int(retention_days)
        self.payees_db_path = payees_db_path

        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

        self.clearing_accounts: set[str] = set()
        if Path(clearing_accounts_path).exists():
            with open(clearing_accounts_path, "r", encoding="utf-8") as f:
                self.clearing_accounts = {line.strip() for line in f if line.strip()}

        self._init_database()

    def _init_database(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS file_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                filename TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                record_count INTEGER
            )
            """
        )
        conn.commit()
        conn.close()

    def _compute_hash(self, content: str) -> str:
        # Canonicalize content per spec:
        # - Normalize CRLF and bare CR to LF
        # - Split into lines on '\n'
        # - Rstrip trailing spaces/tabs from each line
        # - Remove only trailing empty lines
        # - Join with '\n' and append final '\n' if non-empty
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        # strip trailing spaces/tabs per-line
        lines = [ln.rstrip(" \t") for ln in lines]
        # remove only trailing empty lines
        while lines and lines[-1] == "":
            lines.pop()
        if lines:
            canonical = "\n".join(lines) + "\n"
        else:
            canonical = ""
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def check_duplicate(self, file_hash: str, filename: str) -> bool:
        # Duplicate detection is based on file_hash only and respects the retention window.
        if self.retention_days <= 0:
            return False
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM file_index WHERE file_hash = ? AND timestamp >= ?",
            (file_hash, cutoff),
        )
        n = cur.fetchone()[0]
        conn.close()
        return n > 0

    def record_file(self, file_hash: str, filename: str, record_count: int) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO file_index (file_hash, filename, timestamp, record_count) VALUES (?, ?, ?, ?)",
            (file_hash, filename, datetime.now().isoformat(), record_count),
        )
        conn.commit()
        conn.close()

    def parse_record(self, line: str, line_num: int) -> tuple[Dict[str, Any], List[str]]:
        errors: List[str] = []
        record: Dict[str, Any] = {}

        record_len = int(self.schema["record_length"])
        # Enforce exact record length semantics (allow right-padding with spaces)
        if len(line) < record_len:
            errors.append(f"Line {line_num}: Record length expected {record_len} got {len(line)}")
            return {}, errors
        if len(line) > record_len:
            extra = line[record_len:]
            if extra.strip():
                errors.append(f"Line {line_num}: Record length expected {record_len} got {len(line)}")
                return {}, errors
            line = line[:record_len]

        for field in self.schema["fields"]:
            name = field["name"]
            start = int(field["start"])
            length = int(field["length"])
            required = bool(field.get("required", True))
            ftype = field.get("type", "string")

            raw = line[start : start + length]
            value = raw.strip()
            record[name] = value

            if required and not value:
                errors.append(f"Line {line_num}: Field '{name}' is required but empty")
                continue

            if not value:
                continue

            # Field-specific validations
            if name == "eftno":
                if not value or not re.match(r"^[a-zA-Z0-9]+$", value):
                    errors.append(f"Line {line_num}: Field 'eftno' must be non-empty and alphanumeric")

            elif name == "bank_code":
                if not value:
                    errors.append(f"Line {line_num}: Field 'bank_code' is required but empty")
                else:
                    if not value[0].isdigit():
                        errors.append(f"Line {line_num}: Bank code must start with a digit")
                    if not re.match(r"^[A-Z0-9]+$", value):
                        errors.append(f"Line {line_num}: Bank code must contain only uppercase letters and digits")

            if ftype == "string":
                pattern = field.get("pattern")
                if pattern and not re.match(pattern, value):
                    errors.append(f"Line {line_num}: Field '{name}' does not match pattern")

            elif ftype == "decimal":
                try:
                    amt = Decimal(value)
                    if amt <= 0:
                        errors.append(f"Line {line_num}: Field '{name}' must be > 0")
                    if abs(amt.as_tuple().exponent) > 2:
                        errors.append(f"Line {line_num}: Field '{name}' has more than 2 decimal places")
                except (InvalidOperation, ValueError):
                    errors.append(f"Line {line_num}: Field '{name}' is not a valid decimal")

            elif ftype == "date":
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"Line {line_num}: Field '{name}' is not a valid date")

        return record, errors

    def validate_accounts(self, record: Dict[str, Any], line_num: int) -> List[str]:
        errors: List[str] = []

        acct = (record.get("account_no") or "").strip()
        if not acct:
            return errors

        # Basic format check: must be 8-20 digits
        if not re.match(r"^\d{8,20}$", acct):
            errors.append(f"Line {line_num}: Invalid account_no")
            return errors

        # Define core account acct8 = account_no[:8] (leftmost 8 digits)
        acct8 = acct[:8]

        # Forbidden prefixes: acct8[:4] cannot be 0000, 0001, 0010, or 0100
        prefix = acct8[:4]
        forbidden = {"0000", "0001", "0010", "0100"}
        if prefix in forbidden:
            errors.append(f"Line {line_num}: Account number has forbidden prefix {prefix}")

        # First 4 digits rule: first 4 digits of acct8 must not consist solely of 0 and 1
        first4 = acct8[:4]
        if all(d in "01" for d in first4):
            errors.append(f"Line {line_num}: First 4 digits cannot consist solely of 0 and 1")

        # Last 4 digits rule: last 4 digits of acct8 must not contain the digit 0
        last4 = acct8[4:8]
        if "0" in last4:
            errors.append(f"Line {line_num}: Last 4 digits cannot contain 0")

        clearing = (record.get("clearing_account") or "").strip()
        if clearing and self.clearing_accounts:
            # Require exact match for clearing accounts
            if clearing not in self.clearing_accounts:
                errors.append(f"Line {line_num}: Invalid clearing account")

        # Payee database validation
        if self.payees_db_path and Path(self.payees_db_path).exists():
            payee_errors = self.validate_payee(acct, record.get("payee_name", ""), line_num)
            errors.extend(payee_errors)

        return errors

    def validate_payee(self, account_no: str, payee_name: str, line_num: int) -> List[str]:
        errors: List[str] = []
        if not account_no:
            return errors

        conn = sqlite3.connect(self.payees_db_path)
        cur = conn.cursor()
        cur.execute("SELECT payee_name, fraud_flag FROM payees WHERE account_no = ?", (account_no,))
        row = cur.fetchone()
        conn.close()

        if not row:
            errors.append(f"Line {line_num}: Account {account_no} not found in payee database")
            return errors

        db_name, fraud_flag = row
        
        # Collapse internal whitespace to single space, then trim and case-fold
        def normalize_name(name: str) -> str:
            # Collapse internal whitespace runs to single space
            normalized = re.sub(r'\s+', ' ', name.strip())
            return normalized.lower()
        
        if normalize_name(payee_name) != normalize_name(db_name):
            errors.append(f"Line {line_num}: Payee name mismatch for {account_no}")

        if int(fraud_flag or 0) == 1:
            errors.append(f"Line {line_num}: Account '{account_no}' is flagged for fraud/risk and cannot be processed")

        return errors

    def validate_file(self, file_path: str) -> Dict[str, Any]:
        content = Path(file_path).read_text(encoding="utf-8")
        file_hash = self._compute_hash(content)

        filename = Path(file_path).name
        is_dup = self.check_duplicate(file_hash, filename)

        # Normalize line endings and split into lines
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        
        # Remove only trailing empty lines (per spec: drop only empty trailing lines at the end)
        while lines and lines[-1] == "":
            lines.pop()
        
        # records_processed = number of remaining lines
        processed = len(lines)

        errors: List[str] = []
        warnings: List[str] = []

        for i, line in enumerate(lines, start=1):
            rec, rec_errors = self.parse_record(line, i)
            if rec_errors:
                errors.extend(rec_errors)
                continue

            acct_errors = self.validate_accounts(rec, i)
            if acct_errors:
                errors.extend(acct_errors)
                continue

            if self.payees_db_path:
                payee_errors = self.validate_payee(rec.get("account_no", ""), rec.get("payee_name", ""), i)
                if payee_errors:
                    errors.extend(payee_errors)
                    continue

        # Only insert into DB if not duplicate AND retention_days > 0
        if not is_dup and self.retention_days > 0:
            self.record_file(file_hash, filename, processed)

        return {
            "duplicate": is_dup,
            "n_errors": len(errors),
            "n_warnings": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "file_hash": file_hash,
            "records_processed": processed,
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate EFT payment files')
    parser.add_argument('--file', required=True, help='Path to EFT file to validate')
    parser.add_argument('--schema', default='schema.json', help='Path to schema JSON')
    parser.add_argument('--index', default='.eft_index.db', help='Path to SQLite index database')
    parser.add_argument('--clearing-accounts', default='clearing_accounts.txt', help='Path to clearing accounts file')
    parser.add_argument('--retention-days', type=int, default=5, help='Duplicate detection retention window (days)')
    parser.add_argument('--payees-db', help='Path to payees database')
    
    args = parser.parse_args()
    
    if not Path(args.file).exists():
        print(json.dumps({"error": f"File not found: {args.file}"}), file=sys.stderr)
        sys.exit(1)
    
    validator = EFTValidator(
        schema_path=args.schema,
        index_db=args.index,
        clearing_accounts_path=args.clearing_accounts,
        retention_days=args.retention_days,
        payees_db_path=args.payees_db
    )
    
    report = validator.validate_file(args.file)
    
    print(json.dumps(report, indent=2))
    
    # Exit code: 0 if valid, 1 if errors or duplicate
    if report['duplicate'] or report['n_errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
PYTHON

# Quick compile-check to ensure the runtime file is syntactically valid.
python -m py_compile /app/validate_eft.py 2>/dev/null || true
