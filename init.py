import sqlite3

conn = sqlite3.connect('maintenance.db')
cursor = conn.cursor()

# Assets Table
cursor.execute('''CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    location TEXT,
    lastService TEXT,
    nextDueDate TEXT
)''')

# Schedules Table
cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
    ppm_id TEXT PRIMARY KEY,
    assetId TEXT,
    date TEXT,
    completed INTEGER DEFAULT 0,
    assigned INTEGER DEFAULT 0,
    assignedTo TEXT,
    assignedDate TEXT,
    completedDate TEXT,
    status TEXT DEFAULT 'Pending'
)''')

conn.commit()
conn.close()
print("Database initialized successfully.")