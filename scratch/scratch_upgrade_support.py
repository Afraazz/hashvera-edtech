import sqlite3
import os

DB_PATH = "hashvera.db"

def upgrade_support():
    conn = sqlite3.connect(DB_PATH)
    try:
        # Add priority column if it doesn't exist
        conn.execute("ALTER TABLE support_tickets ADD COLUMN priority TEXT DEFAULT 'Medium'")
        print("Added priority column.")
    except sqlite3.OperationalError:
        print("Priority column already exists.")
    
    try:
        # Add is_archived column if it doesn't exist
        conn.execute("ALTER TABLE support_tickets ADD COLUMN is_archived INTEGER DEFAULT 0")
        print("Added is_archived column.")
    except sqlite3.OperationalError:
        print("is_archived column already exists.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade_support()
