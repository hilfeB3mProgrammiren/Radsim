import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "radsim.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DB_PATH = "radsim.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    with open("schema.sql") as f:
        db.executescript(f.read())
    db.commit()
    print("Datenbank initialisiert")

def insert_testdaten():
    db = get_db()
    db.execute("INSERT INTO geraete (name, typ, strahlungsart, staerke, gesamtdosis, mcu_adresse) VALUES (?, ?, ?, ?, ?, ?)",
               ("Geigerzähler A", "messgeraet", None, 0.0, 15.6, "192.168.1.10"))
    db.execute("INSERT INTO geraete (name, typ, strahlungsart, staerke, gesamtdosis, mcu_adresse) VALUES (?, ?, ?, ?, ?, ?)",
               ("Strahlenquelle B", "quelle", "gamma", 50.0, 0.0, "192.168.1.11"))
    db.execute("INSERT INTO geraete (name, typ, strahlungsart, staerke, gesamtdosis, mcu_adresse) VALUES (?, ?, ?, ?, ?, ?)",
               ("Geigerzähler C", "messgeraet", None, 0.0, 10.0, "192.168.1.12"))
    db.commit()
    print("Testdaten eingefügt")