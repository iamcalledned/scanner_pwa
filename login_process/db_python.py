import sqlite3
from config import Config
import os
from dotenv import load_dotenv

def drop_tables(cursor):
    tables = ["threads", "conversations", "user_data", "verifier_store"]
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table};")
            print(f"Dropped table {table}")
        except sqlite3.Error as err:
            print(f"Error: {err}")

def create_tables(cursor):
    user_data = """
        CREATE TABLE user_data (
            userID INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            name TEXT,
            setup_date TEXT,
            last_login_date TEXT,
            current_session_id TEXT
        );
    """
 
    conversations = """
        CREATE TABLE conversations (
            ConversationID INTEGER PRIMARY KEY AUTOINCREMENT,
            userID INTEGER NOT NULL,
            threadID TEXT NOT NULL,
            RunID TEXT NOT NULL,
            Message TEXT NOT NULL,
            Timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            MessageType TEXT NOT NULL,
            IPAddress TEXT,
            Status TEXT DEFAULT 'active',
            FOREIGN KEY (userID) REFERENCES user_data(userID)
        );
    """

    threads = """
        CREATE TABLE threads (
            threadID TEXT PRIMARY KEY,
            userID INTEGER NOT NULL,
            IsActive INTEGER NOT NULL,
            CreatedTime TEXT NOT NULL,
            FOREIGN KEY (userID) REFERENCES user_data(userID)
        );
    """

    verifier_store = """
        CREATE TABLE verifier_store (
            state TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            client_ip TEXT,
            login_timestamp TEXT,
            return_to TEXT
        );
    """


    table_creation_queries = [user_data, conversations, threads, verifier_store]

    for query in table_creation_queries:
        try:
            cursor.execute(query)
            print("Table created successfully")
        except sqlite3.Error as err:
            print(f"Error: {err}")

def main():
    db_path = Config.DB_PATH  # Update Config to include DB_PATH for SQLite file location

    connection = None
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        drop_tables(cursor)
        create_tables(cursor)
        connection.commit()
        print("Database setup completed successfully.")
    except sqlite3.Error as err:
        print(f"Database Error: {err}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    main()
