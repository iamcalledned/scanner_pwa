"""
Migration: add `return_to` column to verifier_store if it doesn't exist.

Usage:
    python migrations/add_return_to_column.py /path/to/your/sqlite.db

This script is idempotent and safe to run multiple times.
"""
import sys
import sqlite3

def ensure_column(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(verifier_store)")
        cols = [row[1] for row in cur.fetchall()]
        if 'return_to' in cols:
            print('Column return_to already exists; nothing to do.')
            return
        # Add the column
        cur.execute("ALTER TABLE verifier_store ADD COLUMN return_to TEXT")
        conn.commit()
        print('Added return_to column to verifier_store')
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python add_return_to_column.py /path/to/db.sqlite')
        sys.exit(1)
    ensure_column(sys.argv[1])
