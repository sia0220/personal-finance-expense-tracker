import sqlite3

DB_NAME = "finance_tracker.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()

    with open("schema.sql", "r") as file:
        conn.executescript(file.read())
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def create_default_categories(user_id):
    default_categories = [
        "Food",
        "Transportation",
        "Bills",
        "School",
        "Entertainment",
        "Savings"
    ]

    conn = get_db_connection()

    for category in default_categories:
        conn.execute(
            """
            INSERT OR IGNORE INTO categories (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (user_id, category, 1)
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()