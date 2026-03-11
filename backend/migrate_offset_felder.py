"""
migrate_offset_felder.py
──────────────────────────────────────────────────────────────────────────────
Ergänzt die radsim.db um Offset-Felder für Messgeräte (Zähler).

Neue Felder in `geraete`:
  ┌──────────────────────┬─────────┬─────────────────────────────────────────┐
  │ Feld                 │ Typ     │ Beschreibung                            │
  ├──────────────────────┼─────────┼─────────────────────────────────────────┤
  │ offset_alpha         │ REAL    │ Manueller Alpha-Offset  (mSv/h)         │
  │ offset_beta          │ REAL    │ Manueller Beta-Offset   (mSv/h)         │
  │ offset_gamma         │ REAL    │ Manueller Gamma-Offset  (mSv/h)         │
  │ offset_reset         │ INTEGER │ Reset-Flag: 1 = Dosis zurücksetzen      │
  └──────────────────────┴─────────┴─────────────────────────────────────────┘

Die Offset-Variablen nutzen dieselbe Einheit wie staerke_alpha/beta/gamma
der Quellen (mSv/h), sodass das Messgerät die Gesamtstrahlung direkt anpassen
kann ohne neue Einheitenumrechnung.

Ausführen (einmalig):
    python migrate_offset_felder.py
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
    c = conn.cursor()

    migrations = [
        # (Spaltenname, SQL-Definition, Beschreibung)
        ("offset_alpha", "REAL    DEFAULT 0.0", "Messgerät – manueller Alpha-Offset (mSv/h)"),
        ("offset_beta",  "REAL    DEFAULT 0.0", "Messgerät – manueller Beta-Offset  (mSv/h)"),
        ("offset_gamma", "REAL    DEFAULT 0.0", "Messgerät – manueller Gamma-Offset (mSv/h)"),
        ("offset_reset", "INTEGER DEFAULT 0",   "Messgerät – Reset-Flag (0=nein, 1=einmalig senden)"),
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