import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'push_subs.sqlite3')

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT UNIQUE,
        subscription_json TEXT,
        created_at INTEGER
    )
    ''')
    conn.commit()
    conn.close()


def save_subscription(subscription_json):
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO subscriptions (endpoint, subscription_json, created_at) VALUES (?, ?, strftime("%s","now"))',
                (subscription_json.get('endpoint'), json.dumps(subscription_json)))
    conn.commit()
    conn.close()


def list_subscriptions():
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT subscription_json FROM subscriptions')
    rows = [json.loads(r[0]) for r in cur.fetchall()]
    conn.close()
    return rows


def remove_subscription(endpoint):
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM subscriptions WHERE endpoint = ?', (endpoint,))
    conn.commit()
    conn.close()
