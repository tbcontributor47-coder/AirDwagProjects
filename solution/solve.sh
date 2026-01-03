#!/bin/bash
set -eu

# Apply the fixed solution to the target application path
cat <<'EOF' > reconcile.py
#!/usr/bin/env python3
import json
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime
import time

def main():
    if len(sys.argv) < 2:
        print("Usage: python reconcile.py <input_json_path>")
        sys.exit(1)
    
    start_time = time.time()
    
    try:
        with open(sys.argv[1], 'r') as f:
            ledger = json.load(f)
    except Exception:
        sys.exit(1)
    
    exchange_rates = ledger.get('exchange_rates', {})
    transactions = ledger.get('transactions', [])
    
    # FIXED: O(N) duplicate detection using a set of hashes/tuples
    unique_transactions = []
    seen = set()
    duplicates = 0
    
    for tx in transactions:
        # Canonical key: id, amount, currency, timestamp
        tx_key = (tx['id'], tx['amount'], tx['currency'], tx['timestamp'])
        if tx_key in seen:
            duplicates += 1
        else:
            seen.add(tx_key)
            unique_transactions.append(tx)
    
    # Process transactions
    account_balances = {}
    for tx in unique_transactions:
        account_id = tx['account_id']
        amount = Decimal(tx['amount'])
        currency = tx['currency']
        
        # FIXED: Use ROUND_HALF_EVEN for banker's rounding
        if currency != 'USD':
            rate = Decimal(str(exchange_rates.get(currency, 1.0)))
            amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        else:
            amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        
        if account_id not in account_balances:
            account_balances[account_id] = Decimal('0')
        account_balances[account_id] += amount
    
    # FIXED: Sort accounts by account_id (ASCII order)
    sorted_accounts_ids = sorted(account_balances.keys())
    accounts = []
    for account_id in sorted_accounts_ids:
        balance = account_balances[account_id]
        # FIXED: Format exactly 2 decimal places with sign
        balance_str = "{:.2f}".format(balance)
        accounts.append({
            'account_id': account_id,
            'balance_usd': balance_str
        })
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    # Final Result
    result = {
        'accounts': accounts,
        'duplicate_count': duplicates,
        'processing_time_ms': elapsed_ms,
        'total_transactions': len(unique_transactions)
    }
    
    # FIXED: Ensure keys are sorted in output
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
EOF

chmod +x reconcile.py
