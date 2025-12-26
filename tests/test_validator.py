#!/usr/bin/env python3
"""
Unit tests for EFT validator
"""

import pytest
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta


# Import the validator - adjust path as needed
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'solution'))
from validate_eft import EFTValidator


@pytest.fixture
def test_env(tmp_path):
    """Create temporary test environment."""
    # Copy schema and clearing accounts
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


def test_valid_file_validation(test_env):
    """Test validation of a valid EFT file."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    test_file = Path(__file__).parent / 'data' / 'valid_payment.txt'
    report = validator.validate_file(str(test_file))
    
    assert report['duplicate'] is False
    assert report['n_errors'] == 0
    assert report['records_processed'] == 3
    assert len(report['file_hash']) == 64  # SHA-256 hex length


def test_duplicate_detection(test_env):
    """Test duplicate file detection."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    test_file = Path(__file__).parent / 'data' / 'duplicate_payment.txt'
    
    # First submission - should not be duplicate
    report1 = validator.validate_file(str(test_file))
    assert report1['duplicate'] is False
    
    # Second submission - should be duplicate
    report2 = validator.validate_file(str(test_file))
    assert report2['duplicate'] is True


def test_invalid_file_validation(test_env):
    """Test validation catches format errors."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    test_file = Path(__file__).parent / 'data' / 'invalid_payment.txt'
    report = validator.validate_file(str(test_file))
    
    assert report['n_errors'] > 0
    # Should catch multiple errors: short line, invalid amount, bad date, invalid account, wrong clearing account


def test_hash_computation(test_env):
    """Test that hash computation is consistent."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    content1 = "Line 1  \nLine 2\r\nLine 3\r"
    content2 = "Line 1\nLine 2\nLine 3"
    
    hash1 = validator._compute_hash(content1)
    hash2 = validator._compute_hash(content2)
    
    # After normalization, hashes should match
    assert hash1 == hash2


def test_retention_window(test_env):
    """Test that duplicate detection respects retention window."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    # Manually insert old record
    conn = sqlite3.connect(test_env['db'])
    cursor = conn.cursor()
    
    old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
    test_hash = "old_test_hash_12345"
    
    cursor.execute('''
        INSERT INTO file_index (file_hash, filename, timestamp, record_count)
        VALUES (?, ?, ?, ?)
    ''', (test_hash, "old_file.txt", old_timestamp, 1))
    conn.commit()
    conn.close()
    
    # Should not be detected as duplicate (outside retention window)
    is_dup = validator.check_duplicate(test_hash)
    assert is_dup is False


def test_clearing_account_validation(test_env):
    """Test clearing account validation."""
    validator = EFTValidator(
        schema_path=test_env['schema'],
        index_db=test_env['db'],
        clearing_accounts_path=test_env['clearing'],
        retention_days=5
    )
    
    # Valid clearing account
    record_valid = {'clearing_account': '12345678901234567890'}
    errors_valid = validator.validate_accounts(record_valid, 1)
    assert len(errors_valid) == 0
    
    # Invalid clearing account
    record_invalid = {'clearing_account': '99999999999999999999'}
    errors_invalid = validator.validate_accounts(record_invalid, 1)
    assert len(errors_invalid) > 0
    assert 'clearing account' in errors_invalid[0].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
