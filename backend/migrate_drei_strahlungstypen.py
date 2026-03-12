"""
migrate_drei_strahlungstypen.py
──────────────────────────────────────────────────────────────────────────────
Erweitert die DB um alle fehlenden Felder für die drei Strahlungstypen.

Neue Spalten in `messungen`:
  cps_alpha   REAL  – Aktuelle Dosisrate Alpha  (mSv/h)
  cps_beta    REAL  – Aktuelle Dosisrate Beta   (mSv/h)
  cps_gamma   REAL  – Aktuelle Dosisrate Gamma  (mSv/h)  [war: cps]
  dosis_alpha REAL  – Kum. Alpha-Dosis          (mSv)
  dosis_beta  REAL  – Kum. Beta-Dosis           (mSv)
  (dosis bleibt als kum. Gamma-Dosis erhalten)

Neue Spalten in `geraete`:
  gesamtdosis_alpha  REAL  – Gesamt-Alpha-Dosis (mSv)
  gesamtdosis_beta   REAL  – Gesamt-Beta-Dosis  (mSv)
  (gesamtdosis bleibt als Gesamt-Gamma-Dosis)

Ausführen (einmalig):
    python migrate_drei_strahlungstypen.py
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
    print(f"[DB] Öffne: {db_path}")
    geaendert = 0

    # Neue Spalten in `messungen`
    messungen_migrations = [
        ("cps_alpha",   "REAL DEFAULT 0.0", "Messgerät – Alpha-Dosisrate (mSv/h)"),
        ("cps_beta",    "REAL DEFAULT 0.0", "Messgerät – Beta-Dosisrate  (mSv/h)"),
        ("cps_gamma",   "REAL DEFAULT 0.0", "Messgerät – Gamma-Dosisrate (mSv/h)"),
        ("dosis_alpha", "REAL DEFAULT 0.0", "Messgerät – kum. Alpha-Dosis (mSv)"),
        ("dosis_beta",  "REAL DEFAULT 0.0", "Messgerät – kum. Beta-Dosis  (mSv)"),
    ]

    print("\n[messungen]")
    for col, definition, beschreibung in messungen_migrations:
        if column_exists(c, "messungen", col):
            print(f"  ✓ '{col}' existiert bereits – übersprungen")
        else:
            c.execute(f"ALTER TABLE messungen ADD COLUMN {col} {definition}")
            print(f"  + '{col}' hinzugefügt  ({beschreibung})")
            geaendert += 1

    # Neue Spalten in `geraete`
    geraete_migrations = [
        ("gesamtdosis_alpha", "REAL DEFAULT 0.0", "Messgerät – kum. Alpha-Gesamtdosis (mSv)"),
        ("gesamtdosis_beta",  "REAL DEFAULT 0.0", "Messgerät – kum. Beta-Gesamtdosis  (mSv)"),
    ]

    print("\n[geraete]")
    for col, definition, beschreibung in geraete_migrations:
        if column_exists(c, "geraete", col):
            print(f"  ✓ '{col}' existiert bereits – übersprungen")
        else:
            c.execute(f"ALTER TABLE geraete ADD COLUMN {col} {definition}")
            print(f"  + '{col}' hinzugefügt  ({beschreibung})")
            geaendert += 1

    conn.commit()
    conn.close()

    print(f"\n[OK] {geaendert} Spalte(n) erfolgreich hinzugefügt." if geaendert
          else "\n[OK] Keine Änderungen nötig – DB ist bereits aktuell.")


if __name__ == "__main__":
    migrate(DB_FILE)