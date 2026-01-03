# Multi-Ledger Currency Reconciliation Engine

## Background
You are maintaining a financial reconciliation system that processes transaction ledgers from multiple sources. The system must detect discrepancies, normalize currencies, and generate a canonical report.

## The Bug
The current implementation has critical bugs preventing accurate reconciliation:
- Currency conversions are producing incorrect results
- Transaction ordering is inconsistent
- The output format doesn't match the specification
- Performance degrades catastrophically with large datasets

## Your Task
Fix the buggy script `/app/reconcile.py` so it:

1. **Reads a JSON ledger** from a file path (first CLI argument)
2. **Canonicalizes all transactions** to USD using provided exchange rates
3. **Detects duplicate transactions** (same `id`, `amount`, `currency`, `timestamp`)
4. **Standardizes timestamps** to ISO-8601 format (UTC, with 'Z' suffix)
5. **Computes the net balance** per account with exactly 2 decimal places
6. **Outputs valid JSON** to stdout with:
   - `total_transactions`: count of unique transactions
   - `duplicate_count`: number of duplicates found
   - `accounts`: array of objects sorted by `account_id` (ascending, case-sensitive)
     - Each account object: `{"account_id": str, "balance_usd": str}`
     - Balance format: "-1234.56" or "0.00" (always 2 decimals, no leading zeros except for 0.00)
   - `processing_time_ms`: integer milliseconds taken
   - All keys in the root JSON object and account objects must be in alphabetical order.

## Input Format
```json
{
  "exchange_rates": {"EUR": 1.18, "GBP": 1.38, "JPY": 0.0091},
  "transactions": [
    {
      "id": "tx001",
      "account_id": "ACC123",
      "amount": "100.50",
      "currency": "USD",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## Output Format (Exact)
```json
{
  "accounts": [
    {"account_id": "ACC123", "balance_usd": "100.50"}
  ],
  "duplicate_count": 0,
  "processing_time_ms": 45,
  "total_transactions": 1
}
```

## Critical Requirements
- **Rounding**: Use banker's rounding (round half to even) for all currency conversions. In Python, this is `ROUND_HALF_EVEN`.
- **Sorting**: Accounts must be sorted by `account_id` using standard ASCII string comparison (case-sensitive).
- **Deduplication**: Transactions with identical `id`, `amount`, `currency`, AND `timestamp` are duplicates. Keep the first occurrence.
- **Performance**: Must process 10,000 transactions in under 2 seconds.
- **Precision**: All USD amounts must have exactly 2 decimal places in the string representation.
- **JSON Serialization**: Use `json.dumps` with `sort_keys=True` to ensure consistent key ordering.

## CLI Usage
```bash
python3 /app/reconcile.py <input_json_path>
```

## Notes
- The term "standardize" refers to timestamp formatting only.
- "Canonicalize" means convert to USD.
- "Normalize" is NOT used in this specification.
- Empty ledgers should output `{"accounts": [], "duplicate_count": 0, "processing_time_ms": <time>, "total_transactions": 0}`.
- If an exchange rate for a currency is missing, the program should treat the rate as 1.0 (though the test data aims to provide all rates).
