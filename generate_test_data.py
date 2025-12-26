#!/usr/bin/env python3
"""Generate properly formatted fixed-width EFT records"""

def format_record(eftno, payee_name, account_no, bank_name, bank_code, amount, 
                  address, clearance_date, last_transaction, clearing_account):
    """Format a single EFT record with exact field positions."""
    record = ""
    record += eftno.ljust(12)[:12]  # 0-11 (12 chars)
    record += payee_name.ljust(40)[:40]  # 12-51 (40 chars)
    record += account_no.ljust(20)[:20]  # 52-71 (20 chars)
    record += bank_name.ljust(30)[:30]  # 72-101 (30 chars)
    record += bank_code.ljust(12)[:12]  # 102-113 (12 chars)
    record += amount.rjust(12)[:12]  # 114-125 (12 chars)
    record += address.ljust(60)[:60]  # 126-185 (60 chars)
    record += clearance_date.ljust(10)[:10]  # 186-195 (10 chars)
    record += last_transaction.ljust(80)[:80]  # 196-275 (80 chars)
    record += clearing_account.ljust(20)[:20]  # 276-295 (20 chars)
    return record

# Valid payment file
valid_records = [
    format_record("EFT001", "John Smith", "12345678901234567890", "Bank of America",
                  "BA123456", "1500.50", "123 Main Street, New York, NY 10001",
                  "2025-12-30", "2024-11-15 Payment for Invoice #45678",
                  "12345678901234567890"),
    format_record("EFT002", "Jane Doe", "98765432109876543210", "Chase Bank",
                  "CH789012", "2750.00", "456 Oak Avenue, Los Angeles, CA 90001",
                  "2025-12-31", "2024-10-20 Premium Payment Q4 2024",
                  "12345678901234567890"),
    format_record("EFT003", "Bob Johnson", "11223344556677889900", "Wells Fargo",
                  "WF345678", "500.75", "789 Pine Road, Chicago, IL 60601",
                  "2026-01-05", "2024-12-01 Claim Settlement #12345",
                  "12345678901234567890"),
]

# Write valid payment file
with open('tests/data/valid_payment.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(valid_records))

print(f"Generated valid_payment.txt ({len(valid_records)} records)")
print(f"Record length: {len(valid_records[0])} characters")

# Duplicate payment file
duplicate_records = [
    format_record("EFT004", "Alice Williams", "55667788990011223344", "Citibank",
                  "CT901234", "3200.25", "321 Elm Street, Houston, TX 77001",
                  "2026-01-10", "2024-11-25 Monthly Premium Payment",
                  "98765432109876543210"),
    format_record("EFT005", "Charlie Brown", "99887766554433221100", "US Bank",
                  "US567890", "1000.00", "654 Maple Drive, Phoenix, AZ 85001",
                  "2026-01-15", "2024-12-10 Annual Policy Payment",
                  "98765432109876543210"),
]

with open('tests/data/duplicate_payment.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(duplicate_records))

print(f"Generated duplicate_payment.txt ({len(duplicate_records)} records)")

# Invalid payment file
invalid_records = [
    "SHORT",  # Too short
    format_record("EFT007", "Invalid Amount User", "12345678901234567890", "Bank of Test",
                  "BT123456", "INVALID_AMT", "789 Test Road, Test City, TS 12345",
                  "2026-01-20", "2024-12-15 Test Transaction",
                  "12345678901234567890"),
    format_record("EFT008", "Bad Date Format", "11223344556677889900", "Test Bank",
                  "TB789012", "750.50", "99 Error Street, Error Town, ET 99999",
                  "12/31/2025", "2024-11-30 Payment with bad date format",
                  "12345678901234567890"),
    format_record("EFT009", "Invalid Account", "123ABC", "Bad Bank",
                  "BB111111", "250.00", "111 Wrong Ave, Wrong City, WC 11111",
                  "2026-02-01", "2024-12-01 Account has letters instead of numbers",
                  "12345678901234567890"),
    format_record("EFT010", "Wrong Clearing", "99887766554433221100", "Good Bank",
                  "GB222222", "1500.00", "222 Right Street, Right City, RC 22222",
                  "2026-02-05", "2024-12-05 Valid but wrong clearing account",
                  "99999999999999999999"),
]

with open('tests/data/invalid_payment.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(invalid_records))

print(f"Generated invalid_payment.txt ({len(invalid_records)} records)")
