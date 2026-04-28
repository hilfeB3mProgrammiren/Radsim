"""
*****************************************************************************
* Copyright (c) 2026, All rights reserved
* Internal Use Only
*
* FILE:        database.py
* PROJECT:     Radsim
* MODULE:      Datenbankverbindung
*
* Description:
*   Dieses Modul verwaltet die SQLite-Datenbankverbindung für
*   das Radsim-System. Es stellt Funktionen zur Verfügung, um
*   die Verbindung im Flask-Request-Kontext zu öffnen, zu
*   schließen und die Datenbank anhand des Schema-Files zu
*   initialisieren.
*
*   Hauptfunktionen:
*   - get_db()   : Gibt die Datenbankverbindung für den
*                  aktuellen Request zurück (lazy init)
*   - close_db() : Schließt die Verbindung am Ende des Requests
*   - init_db()  : Initialisiert die Datenbank anhand schema.sql
*
* Notes:
*   - Verbindung wird pro Request nur einmal geöffnet
*   - WAL-Modus aktiviert für parallele Lesezugriffe
*   - busy_timeout auf 5s gesetzt um Fehler bei gleichzeitigen
*     Schreibzugriffen zu vermeiden
*
* Dependencies:
*   - Flask (Application Context / g-Objekt)
*   - SQLite3
*   - schema.sql (Datenbankschema)
*
* Revision History:
*   2026-03-18  TV   Initiale Version
*
*****************************************************************************
"""
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