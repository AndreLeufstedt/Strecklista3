#!/usr/bin/env python3
"""
Migration script for Strecklistan 3.
Transfers data from the legacy SQLite database (legacy_db/streck.db)
into the new schema.

Strict constraint:
This script ONLY runs if the destination database is completely empty
(0 users, 0 products, 0 transactions).
"""

import os
import sys
import shutil
import sqlite3
import argparse

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_SOURCE = os.path.join(BASE_DIR, 'legacy_db', 'streck.db')
DEFAULT_DEST = os.path.join(BASE_DIR, 'streck.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'app', 'schema.sql')
UPLOADS_USER_DIR = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'users')

def check_destination_is_empty(dest_path):
    """Verify that destination database contains zero user data."""
    if not os.path.exists(dest_path):
        return True, []

    conn = sqlite3.connect(dest_path)
    cur = conn.cursor()
    details = []

    for table in ['users', 'products', 'transactions']:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = cur.fetchone()[0]
            if cnt > 0:
                details.append(f"{cnt} {table}")
        except sqlite3.OperationalError:
            pass

    conn.close()
    if details:
        return False, details
    return True, []

def migrate(source_path, dest_path):
    if not os.path.exists(source_path):
        print(f"ERROR: Legacy database not found: {source_path}", file=sys.stderr)
        print("Please place your old streck.db inside the legacy_db/ directory and try again.", file=sys.stderr)
        sys.exit(1)

    # Enforce strict empty-database requirement
    is_empty, existing_details = check_destination_is_empty(dest_path)
    if not is_empty:
        print("ERROR: Destination database is not empty!", file=sys.stderr)
        print(f"Found existing records: {', '.join(existing_details)}.", file=sys.stderr)
        print("Migration can ONLY be executed when the new database is completely empty.", file=sys.stderr)
        print("To reset the database to an empty factory state first, run:", file=sys.stderr)
        print("    make reset", file=sys.stderr)
        sys.exit(1)

    print(f"Starting migration:\n  Source: {source_path}\n  Destination: {dest_path}\n")

    # 1. Initialize destination schema
    dest_conn = sqlite3.connect(dest_path)
    dest_conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        dest_conn.cursor().executescript(f.read())
    dest_conn.commit()

    # 2. Open source database
    src_conn = sqlite3.connect(source_path)
    src_conn.row_factory = sqlite3.Row
    src_cur = src_conn.cursor()
    dest_cur = dest_conn.cursor()

    # 3. Migrate categories
    src_cur.execute("SELECT id, name FROM categories")
    categories = src_cur.fetchall()
    for cat in categories:
        dest_cur.execute(
            "INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)",
            [cat['id'], cat['name']]
        )
    print(f"[OK] Migrated {len(categories)} categories")

    # 4. Migrate users
    src_cur.execute("SELECT id, barcode, enabled, name, image, notes FROM users")
    users = src_cur.fetchall()
    for u in users:
        dest_cur.execute(
            """INSERT INTO users (id, barcode, name, enabled, hidden, image, notes)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            [u['id'], u['barcode'], u['name'], u['enabled'], u['image'], u['notes']]
        )
    print(f"[OK] Migrated {len(users)} users")

    # 5. Migrate products
    src_cur.execute("SELECT id, barcode, name, price, category, image, notes FROM products")
    products = src_cur.fetchall()
    for p in products:
        dest_cur.execute(
            """INSERT INTO products (id, barcode, name, price, category_id, enabled, hidden, image, notes)
               VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?)""",
            [p['id'], p['barcode'], p['name'], p['price'], p['category'], p['image'], p['notes']]
        )
    print(f"[OK] Migrated {len(products)} products")

    # 6. Migrate transactions
    src_cur.execute("SELECT id, added, user, product, price, notes FROM transactions ORDER BY id ASC")
    transactions = src_cur.fetchall()
    migrated_tx_count = 0
    for t in transactions:
        tx_type = 'PURCHASE'
        if t['notes'] == 'paid' or (t['price'] < 0 and t['product'] is None):
            tx_type = 'PAYMENT'
        elif t['price'] < 0:
            tx_type = 'REFUND'

        dest_cur.execute(
            """INSERT INTO transactions (id, created_at, user_id, product_id, price, type, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [t['id'], t['added'], t['user'], t['product'], t['price'], tx_type, t['notes']]
        )
        migrated_tx_count += 1

    # 7. Initialize default settings if missing
    dest_cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('user_timeout', '15')")
    dest_cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('confirm_timeout', '3')")
    dest_cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('guest_surcharge', '3.0')")

    # 8. Copy user pictures if available in legacy_db/pictures
    legacy_pics = os.path.join(BASE_DIR, 'legacy_db', 'pictures')
    if os.path.exists(legacy_pics):
        os.makedirs(UPLOADS_USER_DIR, exist_ok=True)
        for fname in os.listdir(legacy_pics):
            fpath = os.path.join(legacy_pics, fname)
            if os.path.isfile(fpath) and not fname.startswith('.'):
                shutil.copy2(fpath, os.path.join(UPLOADS_USER_DIR, fname))
        print("[OK] Copied pictures from legacy_db/pictures")

    dest_conn.commit()
    print(f"[OK] Migrated {migrated_tx_count} transactions")

    # 9. Verify all user balances match exactly
    print("\n--- Balance Verification ---")
    mismatches = 0
    for u in users:
        src_cur.execute("SELECT COALESCE(SUM(price), 0.0) as debt FROM transactions WHERE user = ?", [u['id']])
        old_debt = round(float(src_cur.fetchone()['debt']), 2)

        dest_cur.execute("SELECT COALESCE(SUM(price), 0.0) as debt FROM transactions WHERE user_id = ?", [u['id']])
        new_debt = round(float(dest_cur.fetchone()['debt']), 2)

        if abs(old_debt - new_debt) > 0.001:
            print(f"[FAIL] Mismatch for {u['name']}: Old={old_debt}, New={new_debt}")
            mismatches += 1

    if mismatches == 0:
        print(f"[OK] All {len(users)} user balances matched exactly to the cent.")
    else:
        print(f"[WARNING] Found {mismatches} balance discrepancies.")

    src_conn.close()
    dest_conn.close()
    print("\nMigration completed successfully.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Migrate legacy streck.db to Strecklistan 3")
    parser.add_argument('--source', default=DEFAULT_SOURCE, help="Path to legacy streck.db (default: legacy_db/streck.db)")
    parser.add_argument('--dest', default=DEFAULT_DEST, help="Path to destination streck.db (default: streck.db)")
    args = parser.parse_args()

    migrate(args.source, args.dest)
