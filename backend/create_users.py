"""
*****************************************************************************
* Copyright (c) 2026, All rights reserved
* Internal Use Only
*
* FILE:        create_users.py
* PROJECT:     Radsim
* MODULE:      Benutzerverwaltung (Initialisierung)
*
* Description:
*   Dieses Skript legt initiale Benutzer in der radsim.db
*   Datenbank an. Es wird einmalig zur Einrichtung des Systems
*   ausgeführt und erstellt die vordefinierten Benutzerkonten
*   mit gehashten Passwörtern.
*
*   Angelegte Benutzer:
*   - admin        : Administratorzugang
*   - uebungsleiter: Zugang für den Übungsleiter
*
* Notes:
*   - Dieses Skript ist nur einmalig bei der Ersteinrichtung
*     auszuführen
*   - Passwörter werden mit werkzeug generate_password_hash
*     gehasht gespeichert
*   - Wird das Skript erneut ausgeführt, schlägt das INSERT
*     fehl, da der Benutzername als UNIQUE definiert ist
*
* Dependencies:
*   - SQLite3 / radsim.db
*   - werkzeug.security
*
* Revision History:
*   2026-03-18  DH   Initiale Version
*
*****************************************************************************
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "radsim.db")

def create_user(username, password, rolle="teilnehmer"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO users (username, password_hash, rolle) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), rolle)
    )
    conn.commit()
    conn.close()
    print(f"User '{username}' erstellt")

create_user("admin", "admin123", "admin")
create_user("uebungsleiter", "leiter123", "uebungsleiter")