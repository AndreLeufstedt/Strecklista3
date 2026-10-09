#!/usr/bin/env python3
"""
Reset script for Strecklistan 3.
Restores the application to a clean factory state:
- Removes existing streck.db (and WAL/SHM files)
- Creates a fresh streck.db with empty tables
- Ensures default categories ('Öl', 'Ickeöl') and default settings
- Cleans upload directories
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'streck.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'app', 'schema.sql')
UPLOADS_DIR = os.path.join(BASE_DIR, 'app', 'static', 'uploads')

def reset():
    print("Resetting Strecklistan 3 to factory state...")

    # 1. Remove database files
    for suffix in ['', '-shm', '-wal']:
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)
            print(f"[OK] Removed {os.path.basename(p)}")

    # 2. Re-create empty database with schema.sql
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.cursor().executescript(f.read())
    conn.commit()

    # 3. Add default categories and settings
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO categories (name) VALUES ('Öl')")
    cur.execute("INSERT OR IGNORE INTO categories (name) VALUES ('Ickeöl')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('user_timeout', '15')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('confirm_timeout', '3')")
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('guest_surcharge', '3.0')")
    conn.commit()
    conn.close()
    print("[OK] Initialized fresh database with empty tables and default configurations")

    # 4. Clean uploads folder while preserving directory structure
    for subfolder in ['users', 'products']:
        folder_path = os.path.join(UPLOADS_DIR, subfolder)
        if os.path.exists(folder_path):
            for fname in os.listdir(folder_path):
                fpath = os.path.join(folder_path, fname)
                if os.path.isfile(fpath) and fname != '.gitkeep':
                    os.remove(fpath)
        else:
            os.makedirs(folder_path, exist_ok=True)
        gitkeep = os.path.join(folder_path, '.gitkeep')
        if not os.path.exists(gitkeep):
            open(gitkeep, 'w').close()
    print("[OK] Cleaned upload directories")

    print("\nFactory reset complete! The system is now completely empty.")

if __name__ == '__main__':
    reset()
