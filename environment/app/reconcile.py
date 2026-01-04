#!/usr/bin/env python3
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
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
    
    unique_transactions = []
    duplicates = 0
    for tx in transactions:
        is_duplicate = False
        for utx in unique_transactions:
            # BUG 2: Missing timestamp in duplicate check
            if (tx['id'] == utx['id'] and 
                tx['amount'] == utx['amount'] and 
                tx['currency'] == utx['currency']):
                is_duplicate = True
                duplicates += 1
                break
        if not is_duplicate:
            unique_transactions.append(tx)
    
    # Process transactions
    account_balances = {}
    for tx in unique_transactions:
        account_id = tx['account_id']
        amount = Decimal(tx['amount'])
        currency = tx['currency']
        
        if currency != 'USD':
            rate = Decimal(str(exchange_rates.get(currency, 1.0)))
            amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if account_id not in account_balances:
            account_balances[account_id] = Decimal('0')
        account_balances[account_id] += amount
    
    accounts = []
    for account_id, balance in account_balances.items():
        balance_str = str(balance.quantize(Decimal('0.01')))
        accounts.append({
            'account_id': account_id,
            'balance_usd': balance_str
        })
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    result = {
        'total_transactions': len(unique_transactions),
        'duplicate_count': duplicates,
        'accounts': accounts,
        'processing_time_ms': elapsed_ms
    }
    
    print(json.dumps(result))

if __name__ == '__main__':
    main()
