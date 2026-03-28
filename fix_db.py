import sqlite3
import os

db_path = 'instance/terminus.db'
if not os.path.exists('instance'):
    os.makedirs('instance')

conn = sqlite3.connect(db_path)
conn.execute('''
    CREATE TABLE IF NOT EXISTS property_manager_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        timestamp DATETIME
    )
''')
conn.close()
print("Table created successfully!")