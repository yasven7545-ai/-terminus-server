import sqlite3

con = sqlite3.connect("vendor_visits.db")
cur = con.cursor()

cur.executescript("""
DROP TABLE IF EXISTS vendor_visits;

CREATE TABLE vendor_visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT,
  vendor TEXT,
  category TEXT,
  in_time TEXT,
  out_time TEXT,
  status TEXT,
  phone TEXT,
  photo TEXT,
  id_photo TEXT,
  signature TEXT
);
""")

con.commit()
con.close()

print("DB ready")
