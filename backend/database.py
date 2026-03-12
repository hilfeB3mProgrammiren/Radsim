import sqlite3
import os
from flask import g

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "radsim.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

def get_db():
    """Gibt die DB-Verbindung für den aktuellen Request-Kontext zurück.
    Wird pro Request nur einmal geöffnet und am Ende automatisch geschlossen."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")   # parallele Reads während Write erlauben
        g.db.execute("PRAGMA busy_timeout=5000")  # 5 s warten statt sofort fehlschlagen
    return g.db

def close_db(e=None):
    """Schließt die DB-Verbindung am Ende jedes Requests."""
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    db.commit()
    db.close()
    print(f"Datenbank initialisiert: {DB_PATH}")
