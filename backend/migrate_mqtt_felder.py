"""
migrate_mqtt_felder.py
──────────────────────────────────────────────────────────────────────────────
Ergänzt die radsim.db um die Felder, die das neue mqtt_backend.py benötigt.

Neue Felder in `geraete`:
  ┌──────────────────┬─────────┬──────────────────────────────────────────┐
  │ Feld             │ Typ     │ Beschreibung                             │
  ├──────────────────┼─────────┼──────────────────────────────────────────┤
  │ mqtt_offset      │ REAL    │ Zähler: Offset-Variable (default 0.0)    │
  │ mqtt_reset       │ INTEGER │ Zähler: Reset-Flag 0/1   (default 0)     │
  │ mqtt_status      │ TEXT    │ Beide:  letzter gesendeter MQTT-Status   │
  └──────────────────┴─────────┴──────────────────────────────────────────┘

`status`  bleibt für den allgemeinen Gerätestatus (aktiv/inaktiv/fehler).
`mqtt_status` ist der Status, der per MQTT an das Gerät gesendet wurde –
kann abweichen bis das Gerät bestätigt hat.

Ausführen (einmalig):
    python migrate_mqtt_felder.py
──────────────────────────────────────────────────────────────────────────────
"""

import sqlite3
import os

DB_FILE = "radsim.db"

def column_exists(c, table: str, column: str) -> bool:
    cols = [row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols

def migrate(db_path: str):
    if not os.path.exists(db_path):
        print(f"[FEHLER] Datenbankdatei nicht gefunden: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    c    = conn.cursor()

    migrations = [
        # (Spaltenname, SQL-Definition, Beschreibung)
        ("mqtt_offset", "REAL    DEFAULT 0.0",   "Zähler – Offset-Variable"),
        ("mqtt_reset",  "INTEGER DEFAULT 0",      "Zähler – Reset-Flag (0=nein, 1=ja)"),
        ("mqtt_status", "TEXT    DEFAULT 'aktiv'","Zuletzt gesendeter MQTT-Status"),
    ]

    print(f"[DB] Öffne: {db_path}")
    geaendert = 0

    for col, definition, beschreibung in migrations:
        if column_exists(c, "geraete", col):
            print(f"  ✓ '{col}' existiert bereits – übersprungen")
        else:
            c.execute(f"ALTER TABLE geraete ADD COLUMN {col} {definition}")
            print(f"  + '{col}' hinzugefügt  ({beschreibung})")
            geaendert += 1

    conn.commit()
    conn.close()

    if geaendert:
        print(f"\n[OK] {geaendert} Spalte(n) erfolgreich hinzugefügt.")
    else:
        print(f"\n[OK] Keine Änderungen nötig – DB ist bereits aktuell.")


if __name__ == "__main__":
    migrate(DB_FILE)