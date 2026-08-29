import sqlite3
import os

db_path = "hashvera.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    # try common locations
    possible = ["hashvera/data/hashvera.db", "data/hashvera.db"]
    for p in possible:
        if os.path.exists(p):
            db_path = p
            break

print(f"Checking DB: {db_path}")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

count = cur.execute("SELECT COUNT(*) as cnt FROM blocks").fetchone()['cnt']
print(f"Total Blocks: {count}")

active = cur.execute("SELECT COUNT(*) as cnt FROM blocks WHERE record_status != 'Archived'").fetchone()['cnt']
print(f"Active Blocks: {active}")

last_5 = cur.execute("SELECT block_index, student_name, record_status FROM blocks ORDER BY block_index DESC LIMIT 5").fetchall()
for row in last_5:
    print(f"Block {row['block_index']}: {row['student_name']} ({row['record_status']})")

conn.close()
