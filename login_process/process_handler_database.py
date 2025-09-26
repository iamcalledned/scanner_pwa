#process_handler_database.py
import os
import asyncio
import aiosqlite
import datetime
import base64
import hashlib
from config import Config

# Define the SQLite database path
DB_PATH = Config.DB_PATH

async def create_db_pool():
    return await aiosqlite.connect(DB_PATH)

# Save the code_verifier and state in the database
async def save_code_verifier(pool, state: str, code_verifier: str, client_ip: str, login_timestamp):
    # default return_to is None; can be provided by caller to redirect after callback
    async with pool.execute("INSERT INTO verifier_store (state, code_verifier, client_ip, login_timestamp, return_to) VALUES (?, ?, ?, ?, ?)", 
                            (state, code_verifier, client_ip, login_timestamp, None)):
        await pool.commit()


async def save_code_verifier_with_return(pool, state: str, code_verifier: str, client_ip: str, login_timestamp, return_to: str = None):
    async with pool.execute("INSERT INTO verifier_store (state, code_verifier, client_ip, login_timestamp, return_to) VALUES (?, ?, ?, ?, ?)",
                            (state, code_verifier, client_ip, login_timestamp, return_to)):
        await pool.commit()

# Retrieve the code_verifier using the state
async def get_code_verifier(pool, state: str) -> str:
    async with pool.execute("SELECT code_verifier FROM verifier_store WHERE state = ?", (state,)) as cursor:
        result = await cursor.fetchone()
        return result[0] if result else None


async def get_verifier(pool, state: str) -> dict:
    """Return the verifier row for a given state as a dict or None."""
    async with pool.execute("SELECT code_verifier, return_to FROM verifier_store WHERE state = ?", (state,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return {"code_verifier": row[0], "return_to": row[1]}

# Delete the code verifier
async def delete_code_verifier(pool, state: str):
    async with pool.execute("DELETE FROM verifier_store WHERE state = ?", (state,)):
        await pool.commit()

# Generate code verifier and challenge
async def generate_code_verifier_and_challenge():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').replace('=', '').replace('+', '-').replace('/', '_')
    return code_verifier, code_challenge

# Get all data from DB
async def get_data_from_db(session_id, pool):
    # The original code queried a `login` table which doesn't exist in this schema.
    # Use user_data.current_session_id to find the user associated with this session id.
    async with pool.execute("SELECT user_id, username, email, name, setup_date, last_login_date, current_session_id FROM user_data WHERE current_session_id = ?", (session_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return {}
        # Convert sqlite row to dict-like structure
        keys = ["user_id", "username", "email", "name", "setup_date", "last_login_date", "current_session_id"]
        return {k: row[idx] for idx, k in enumerate(keys)}

# Save user info to user_data
async def save_user_info_to_userdata(pool, session):
    async with pool.execute("SELECT username FROM user_data WHERE username = ?", (session['username'],)) as cursor:
        username = await cursor.fetchone()

    if username:
        # Update last_login_date and current_session_id
        await pool.execute("UPDATE user_data SET last_login_date = datetime('now'), current_session_id = ? WHERE username = ?", 
                           (session['session_id'], session['username']))
    else:
        # Insert new user
        await pool.execute("INSERT INTO user_data (username, email, name, setup_date, last_login_date, current_session_id) VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)", 
                           (session['username'], session['email'], session['name'], session['session_id']))
    await pool.commit()

# Create tables
async def create_tables(pool):
    async with pool.execute("""
        CREATE TABLE IF NOT EXISTS user_data (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            name TEXT,
            setup_date TEXT,
            last_login_date TEXT,
            current_session_id TEXT
        );
    """):
        pass
    async with pool.execute("""
        CREATE TABLE IF NOT EXISTS verifier_store (
            state TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            client_ip TEXT,
            login_timestamp TEXT
        );
    """):
        pass
    await pool.commit()

# Insert user
async def insert_user(pool, username):
    async with pool.execute("SELECT user_id FROM user_data WHERE username = ?", (username,)) as cursor:
        existing_user = await cursor.fetchone()

    current_ts = datetime.datetime.now().isoformat()

    if existing_user:
        # Update last_login_date for existing user
        await pool.execute("UPDATE user_data SET last_login_date = ? WHERE username = ?", (current_ts, username))
        await pool.commit()
        return existing_user[0]  # Return the existing user's ID

    # Insert new user
    await pool.execute("INSERT INTO user_data (username, setup_date, last_login_date) VALUES (?, ?, ?)", 
                       (username, current_ts, current_ts))
    await pool.commit()
    return (await pool.execute("SELECT last_insert_rowid()")).fetchone()[0]

# Delete old verifiers
async def delete_old_verifiers(pool):
    one_hour_ago = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    await pool.execute("DELETE FROM verifier_store WHERE login_timestamp < ?", (one_hour_ago,))
    await pool.commit()
