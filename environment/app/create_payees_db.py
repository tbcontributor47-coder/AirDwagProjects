#!/usr/bin/env python3
"""
Create sample payees.db (duplicated here so Docker builds can create the DB inside the image).
This is intentionally a copy of the repository-level `create_payees_db.py` used for tests.
"""

import sqlite3
from pathlib import Path


def create_payees_db(db_path: str = "payees.db"):
    """Create and populate the payees database."""

    # Remove existing DB
    if Path(db_path).exists():
        Path(db_path).unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE payees (
            account_no TEXT PRIMARY KEY,
            payee_name TEXT NOT NULL,
            home_branch TEXT,
            address TEXT,
            national_id TEXT,
            fraud_flag INTEGER DEFAULT 0
        )
    ''')

    # Sample data - Active customers (valid patterns)
    active_customers = [
        ("12345678", "JOHN DOE", "MAIN BRANCH", "123 MAIN ST", "N12345678", 0),
        ("23456789", "JANE SMITH", "NORTH BRANCH", "456 ELM ST", "N23456789", 0),
        ("34567890", "BOB WILSON", "SOUTH BRANCH", "789 OAK AVE", "N34567890", 0),
        ("45678901", "ALICE BROWN", "EAST BRANCH", "321 PINE RD", "N45678901", 0),
        ("56789012", "CHARLIE DAVIS", "WEST BRANCH", "654 MAPLE DR", "N56789012", 0),
        ("67890123", "DAVID EVANS", "MAIN BRANCH", "987 BIRCH LN", "N67890123", 0),
        ("78901234", "EVE FOSTER", "CENTRAL BRANCH", "147 CEDAR CT", "N78901234", 0),
        ("89012345", "FRANK GARCIA", "DOWNTOWN BRANCH", "258 SPRUCE WAY", "N89012345", 0),
        ("90123456", "GRACE HARRIS", "UPTOWN BRANCH", "369 WILLOW BLVD", "N90123456", 0),
        ("23456781", "HENRY IRWIN", "METRO BRANCH", "741 ASPEN PL", "N23456781", 0),
        # Add test file accounts (20 digits)
        ("12345678901234567890", "JOHN SMITH", "MAIN BRANCH", "123 MAIN ST", "N12345678901234567890", 0),
        ("98765432109876543210", "JANE DOE", "MAIN BRANCH", "456 OAK AVE", "N98765432109876543210", 0),
        ("11223344556677889900", "BOB JOHNSON", "MAIN BRANCH", "789 PINE RD", "N11223344556677889900", 0),
        ("55667788990011223344", "ALICE WILLIAMS", "MAIN BRANCH", "321 ELM ST", "N55667788990011223344", 0),
        ("99887766554433221100", "CHARLIE BROWN", "MAIN BRANCH", "654 MAPLE DR", "N99887766554433221100", 0),
    ]

    # Retired customers with grandfathered patterns (would be invalid for new customers)
    retired_customers = [
        ("00001234", "RETIRED CUSTOMER A", "OLD BRANCH", "111 LEGACY ST", "R00001234", 0),
        ("00012345", "RETIRED CUSTOMER B", "OLD BRANCH", "222 LEGACY ST", "R00012345", 0),
        ("00101234", "RETIRED CUSTOMER C", "OLD BRANCH", "333 LEGACY ST", "R00101234", 0),
        ("01001234", "RETIRED CUSTOMER D", "OLD BRANCH", "444 LEGACY ST", "R01001234", 0),
        ("01011234", "RETIRED CUSTOMER E", "OLD BRANCH", "555 LEGACY ST", "R01011234", 0),
        ("11001234", "RETIRED CUSTOMER F", "OLD BRANCH", "666 LEGACY ST", "R11001234", 0),
        ("12345670", "RETIRED CUSTOMER G", "OLD BRANCH", "777 LEGACY ST", "R12345670", 0),
        ("23456700", "RETIRED CUSTOMER H", "OLD BRANCH", "888 LEGACY ST", "R23456700", 0),
    ]

    # Fraud-flagged accounts (active patterns, but flagged)
    fraud_accounts = [
        ("98765432", "SUSPICIOUS PERSON A", "COMPLIANCE BRANCH", "999 RISK AVE", "F98765432", 1),
        ("87654321", "SUSPICIOUS PERSON B", "COMPLIANCE BRANCH", "888 ALERT ST", "F87654321", 1),
        ("76543210", "SUSPICIOUS PERSON C", "COMPLIANCE BRANCH", "777 CAUTION RD", "F76543210", 1),
    ]

    # Insert all records
    all_records = active_customers + retired_customers + fraud_accounts
    cursor.executemany('''
        INSERT INTO payees (account_no, payee_name, home_branch, address, national_id, fraud_flag)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', all_records)

    # Create clearing_accounts table and insert sample clearing accounts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clearing_accounts (
            account_no TEXT PRIMARY KEY
        )
    ''')
    clearing_list = [
        ("12345678901234567890",),
        ("98765432109876543210",),
        ("11111111112222222222",),
    ]
    cursor.executemany('INSERT OR IGNORE INTO clearing_accounts (account_no) VALUES (?)', clearing_list)

    conn.commit()
    conn.close()

    print(f"Created {db_path} with {len(all_records)} payee records:")
    print(f"  - {len(active_customers)} active customers (valid patterns)")
    print(f"  - {len(retired_customers)} retired customers (grandfathered patterns)")
    print(f"  - {len(fraud_accounts)} fraud-flagged accounts")
    print(f"  - {len(clearing_list)} clearing accounts inserted into clearing_accounts table")


if __name__ == "__main__":
    create_payees_db()
