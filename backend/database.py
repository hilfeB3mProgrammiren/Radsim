import sqlite3
import os

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "radsim.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    db.commit()
    print(f"Datenbank initialisiert: {DB_PATH}")