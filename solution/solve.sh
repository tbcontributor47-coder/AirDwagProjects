#!/usr/bin/env bash
set -euo pipefail

# Oracle solution for EFT file validation
# Harbor copies this folder to /oracle at runtime and expects this script.

# Write the Python validator implementation
cat > /app/validate_eft.py <<'PYTHON'
#!/usr/bin/env python3
"""
EFT Payment File Validator - Oracle Solution
Validates fixed-width EFT payment files for duplicate detection, format compliance, and account validation.
"""

import sys
import json
import sqlite3
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
from decimal import Decimal, InvalidOperation


class EFTValidator:
    def __init__(self, schema_path: str, index_db: str, clearing_accounts_path: str, retention_days: int = 5):
        self.schema = self._load_schema(schema_path)
        self.db_path = index_db
        self.retention_days = retention_days
        self.clearing_accounts = self._load_clearing_accounts(clearing_accounts_path)
        self._init_database()
    
    def _load_schema(self, path: str) -> Dict[str, Any]:
        """Load field schema from JSON file."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def _load_clearing_accounts(self, path: str) -> set:
        """Load valid clearing account numbers."""
        accounts = set()
        if Path(path).exists():
            with open(path, 'r') as f:
                accounts = {line.strip() for line in f if line.strip()}
        return accounts
    
    def _init_database(self):
        """Initialize SQLite database for file index."""
        conn = sqlite3.connect(self.db_path)
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
        conn.commit()
        conn.close()
    
    def _normalize_content(self, content: str) -> str:
        """Normalize file content for consistent hashing."""
        # Strip trailing spaces from each line and normalize line endings
        lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        normalized = '\n'.join(line.rstrip() for line in lines if line.strip())
        return normalized
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of normalized content."""
        normalized = self._normalize_content(content)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def check_duplicate(self, file_hash: str) -> bool:
        """Check if file hash exists within retention window."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
        
        cursor.execute('''
            SELECT COUNT(*) FROM file_index 
            WHERE file_hash = ? AND timestamp >= ?
        ''', (file_hash, cutoff_date))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def record_file(self, file_hash: str, filename: str, record_count: int):
        """Record file metadata in the index."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        try:
            cursor.execute('''
                INSERT INTO file_index (file_hash, filename, timestamp, record_count)
                VALUES (?, ?, ?, ?)
            ''', (file_hash, filename, timestamp, record_count))
            conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate entry (same hash at same second) - ignore
            pass
        finally:
            conn.close()
    
    def parse_record(self, line: str, line_num: int) -> Tuple[Dict[str, Any], List[str]]:
        """Parse a single fixed-width record and return parsed data and errors."""
        errors = []
        record = {}
        
        # Check record length
        if len(line) < self.schema['record_length']:
            errors.append(f"Line {line_num}: Record too short (expected {self.schema['record_length']} chars, got {len(line)})")
            return record, errors
        
        # Parse each field
        for field in self.schema['fields']:
            name = field['name']
            start = field['start']
            length = field['length']
            field_type = field['type']
            required = field.get('required', True)
            
            # Extract field value
            value = line[start:start + length].strip()
            record[name] = value
            
            # Validate required fields
            if required and not value:
                errors.append(f"Line {line_num}: Field '{name}' is required but empty")
                continue
            
            # Skip validation if not required and empty
            if not required and not value:
                continue
            
            # Type-specific validation
            if field_type == 'string':
                # Check pattern if specified
                if 'pattern' in field:
                    if not re.match(field['pattern'], value):
                        errors.append(f"Line {line_num}: Field '{name}' does not match pattern {field['pattern']}")
            
            elif field_type == 'decimal':
                try:
                    amount = Decimal(value)
                    if amount <= 0:
                        errors.append(f"Line {line_num}: Field '{name}' must be > 0")
                    # Check decimal places
                    if abs(amount.as_tuple().exponent) > 2:
                        errors.append(f"Line {line_num}: Field '{name}' has more than 2 decimal places")
                except (InvalidOperation, ValueError):
                    errors.append(f"Line {line_num}: Field '{name}' is not a valid decimal")
            
            elif field_type == 'date':
                date_format = field.get('format', '%Y-%m-%d')
                try:
                    datetime.strptime(value, date_format)
                except ValueError:
                    errors.append(f"Line {line_num}: Field '{name}' is not a valid date (expected {date_format})")
        
        return record, errors
    
    def validate_accounts(self, record: Dict[str, Any], line_num: int) -> List[str]:
        """Validate account numbers."""
        errors = []
        
        # Validate clearing account
        clearing_account = record.get('clearing_account', '').strip()
        if clearing_account and self.clearing_accounts:
            if clearing_account not in self.clearing_accounts:
                errors.append(f"Line {line_num}: Invalid clearing account '{clearing_account}'")
        
        return errors
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Validate entire EFT file and return report."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Compute hash and check for duplicates
        file_hash = self._compute_hash(content)
        is_duplicate = self.check_duplicate(file_hash)
        
        # Parse and validate records
        lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        lines = [line for line in lines if line.strip()]  # Remove empty lines
        
        all_errors = []
        all_warnings = []
        records_processed = 0
        
        for idx, line in enumerate(lines, start=1):
            record, errors = self.parse_record(line, idx)
            if errors:
                all_errors.extend(errors)
            else:
                # Additional account validation
                account_errors = self.validate_accounts(record, idx)
                if account_errors:
                    all_errors.extend(account_errors)
                else:
                    records_processed += 1
        
        # Record file in index if not duplicate
        if not is_duplicate:
            self.record_file(file_hash, Path(file_path).name, records_processed)
        
        # Build report
        report = {
            "duplicate": is_duplicate,
            "n_errors": len(all_errors),
            "n_warnings": len(all_warnings),
            "errors": all_errors,
            "warnings": all_warnings,
            "file_hash": file_hash,
            "records_processed": records_processed
        }
        
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate EFT payment files')
    parser.add_argument('--file', required=True, help='Path to EFT file to validate')
    parser.add_argument('--schema', default='schema.json', help='Path to schema JSON')
    parser.add_argument('--index', default='.eft_index.db', help='Path to SQLite index database')
    parser.add_argument('--clearing-accounts', default='clearing_accounts.txt', help='Path to clearing accounts file')
    parser.add_argument('--retention-days', type=int, default=5, help='Duplicate detection retention window (days)')
    
    args = parser.parse_args()
    
    # Validate file exists
    if not Path(args.file).exists():
        print(json.dumps({"error": f"File not found: {args.file}"}), file=sys.stderr)
        sys.exit(1)
    
    # Run validation
    validator = EFTValidator(
        schema_path=args.schema,
        index_db=args.index,
        clearing_accounts_path=args.clearing_accounts,
        retention_days=args.retention_days
    )
    
    report = validator.validate_file(args.file)
    
    # Output report as JSON
    print(json.dumps(report, indent=2))
    
    # Exit with appropriate code
    if report['duplicate'] or report['n_errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
PYTHON

chmod +x /app/validate_eft.py

# If a requirements.txt exists in this solution directory, install it (idempotent)
if [ -f ./requirements.txt ]; then
    echo "Found requirements.txt; installing..."
    python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
    python3 -m pip install --no-cache-dir -r ./requirements.txt || echo "Warning: some requirements failed to install"
fi

# Execute with arguments passed to solve.sh
exec python3 /app/validate_eft.py "$@"
