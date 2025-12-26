#!/usr/bin/env python3
"""Verifier-style tests for the EFT validator CLI.

These tests invoke the CLI (`/app/validate_eft.py` in verifier/runtime) via
subprocess instead of importing the oracle directly. When run locally, they
fall back to `solution/validate_eft.py` so maintainers can run tests.
"""

import json
import sqlite3
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest


def _cli_path():
    # Prefer runtime CLI location; fall back to solution for local runs
    if Path('/app/validate_eft.py').exists():
        return '/app/validate_eft.py'
    return str(Path(__file__).parent.parent / 'solution' / 'validate_eft.py')


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


def test_valid_file_validation(test_env):
    test_file = Path(__file__).parent / 'data' / 'valid_payment.txt'

    rc, out, err = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    assert rc == 0
    report = json.loads(out)
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


def test_invalid_file_validation(test_env):
    test_file = Path(__file__).parent / 'data' / 'invalid_payment.txt'
    rc, out, _ = _run_cli(test_file, test_env['schema'], test_env['clearing'], test_env['db'])
    # validator should exit non-zero when errors are present
    assert rc != 0
    rep = json.loads(out)
    assert rep['n_errors'] > 0


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


if __name__ == '__main__':
    pytest.main([__file__, '-q'])
