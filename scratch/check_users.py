import sqlite3
conn = sqlite3.connect('hashvera.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT campus_id, phone FROM users").fetchall()
for row in rows:
    print(f"ID: {row['campus_id']}, Phone: {row['phone']}")
conn.close()
