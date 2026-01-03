import json
import subprocess
import tempfile
import os
import time
import pytest
from pathlib import Path

def run_reconcile(ledger_data):
    """Helper to run reconcile.py with temporary input file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(ledger_data, f)
        temp_path = f.name
    
    try:
        # Assuming app is in /app inside the container
        cmd = ['python3', '/app/reconcile.py', temp_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip(), result.returncode, result.stderr
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def parse_output(output_str):
    """Parse and validate JSON output"""
    try:
        data = json.loads(output_str)
        return data
    except json.JSONDecodeError as e:
        pytest.fail(f"Output is not valid JSON: {output_str}")

def test_single_transaction_usd():
    """Test a basic single transaction in USD - the simplest case."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, err = run_reconcile(ledger)
    assert code == 0, f"Error: {err}"
    data = parse_output(output)
    assert data["total_transactions"] == 1
    assert data["duplicate_count"] == 0
    assert len(data["accounts"]) == 1
    assert data["accounts"][0]["account_id"] == "A001"
    assert data["accounts"][0]["balance_usd"] == "100.00"

def test_currency_conversion_eur():
    """Test currency conversion using provided rate (EUR to USD)."""
    ledger = {
        "exchange_rates": {"EUR": 1.20},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "EUR", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, err = run_reconcile(ledger)
    assert code == 0
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "120.00"

def test_bankers_rounding():
    """Test Banker's rounding (round half to even) - 10.125 -> 10.12, 10.135 -> 10.14."""
    ledger = {
        "exchange_rates": {"EUR": 1.0},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "10.125", "currency": "EUR", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "A002", "amount": "10.135", "currency": "EUR", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    balances = {acc["account_id"]: acc["balance_usd"] for acc in data["accounts"]}
    assert balances["A001"] == "10.12"
    assert balances["A002"] == "10.14"

def test_duplicate_detection():
    """Test deduplication requiring exact match of ID, amount, currency, AND timestamp."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T13:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["duplicate_count"] == 1
    assert data["total_transactions"] == 2

def test_account_sorting():
    """Test accounts are sorted by account_id using case-sensitive string comparison."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "B002", "amount": "10.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "A001", "amount": "20.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx3", "account_id": "C003", "amount": "30.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    account_ids = [acc["account_id"] for acc in data["accounts"]]
    assert account_ids == ["A001", "B002", "C003"]

def test_negative_balance():
    """Test handling of negative amounts and balances."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "-50.75", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "-50.75"

def test_empty_ledger():
    """Test graceful handling of empty ledgers."""
    ledger = {
        "exchange_rates": {},
        "transactions": []
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["total_transactions"] == 0
    assert data["duplicate_count"] == 0
    assert data["accounts"] == []
    assert "processing_time_ms" in data

def test_json_key_order():
    """Test that output JSON keys are in alphabetical order."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "10.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    # Check that keys are in alphabetical order in the raw output
    try:
        keys = list(json.loads(output).keys())
        assert keys == sorted(keys)
    except Exception as e:
        pytest.fail(f"Key ordering check failed: {e}")

def test_multiple_transactions_same_account():
    """Test aggregation of multiple transactions for the same account."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "A001", "amount": "50.50", "currency": "USD", "timestamp": "2024-01-01T13:00:00Z"},
            {"id": "tx3", "account_id": "A001", "amount": "-25.25", "currency": "USD", "timestamp": "2024-01-01T14:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "125.25"

def test_zero_balance_format():
    """Test that zero balance is formatted correctly as '0.00'."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "A001", "amount": "-100.00", "currency": "USD", "timestamp": "2024-01-01T13:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "0.00"

def test_mixed_currencies():
    """Test complex aggregation with multiple currencies and implied precision."""
    ledger = {
        "exchange_rates": {"EUR": 1.20, "GBP": 1.40, "JPY": 0.009},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "100.00", "currency": "EUR", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "A001", "amount": "50.00", "currency": "GBP", "timestamp": "2024-01-01T13:00:00Z"},
            {"id": "tx3", "account_id": "A001", "amount": "1000.00", "currency": "JPY", "timestamp": "2024-01-01T14:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "199.00"

def test_performance_large_dataset():
    """Test performance constraint - 5000 records must process in < 2 seconds."""
    transactions = []
    for i in range(5000):
        transactions.append({
            "id": f"tx{i}",
            "account_id": f"A{i % 100:03d}",
            "amount": "10.00",
            "currency": "USD",
            "timestamp": "2024-01-01T12:00:00Z"
        })
    
    ledger = {
        "exchange_rates": {},
        "transactions": transactions
    }
    
    start = time.time()
    output, code, _ = run_reconcile(ledger)
    elapsed = time.time() - start
    
    assert code == 0
    assert elapsed < 2.0
    data = parse_output(output)
    assert data["total_transactions"] == 5000

def test_decimal_precision_edge():
    """Test precision rounding to 2 decimal places using Banker's rounding on edge case."""
    ledger = {
        "exchange_rates": {"EUR": 1.18567},
        "transactions": [
            {"id": "tx1", "account_id": "A001", "amount": "99.99", "currency": "EUR", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    assert data["accounts"][0]["balance_usd"] == "118.55"

def test_case_sensitive_sorting_trap():
    """Test case-sensitive ASCII sorting (A < B < a)."""
    ledger = {
        "exchange_rates": {},
        "transactions": [
            {"id": "tx1", "account_id": "a001", "amount": "10.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx2", "account_id": "B002", "amount": "20.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": "tx3", "account_id": "A003", "amount": "30.00", "currency": "USD", "timestamp": "2024-01-01T12:00:00Z"}
        ]
    }
    output, code, _ = run_reconcile(ledger)
    data = parse_output(output)
    account_ids = [acc["account_id"] for acc in data["accounts"]]
    assert account_ids == ["A003", "B002", "a001"]
