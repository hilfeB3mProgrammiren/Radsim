"""
insert_testuebungen.py
Fügt 3 Testübungen mit je mehreren Geräten in die Datenbank ein.
Ausführen aus dem backend/-Verzeichnis:  python insert_testuebungen.py
"""

from database import get_db
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

db = get_db()
now = datetime.now()

# -----------------------------------------------
# Übungen
# -----------------------------------------------
uebungen = [
    ("Übung Alpha 2025",    "aktiv",        now - timedelta(hours=2),  None),
    ("Übung Bravo 2025",    "abgeschlossen", now - timedelta(days=3),  now - timedelta(days=2, hours=18)),
    ("Notfallsimulation C", "vorbereitung",  None,                     None),
]

uebung_ids = []
for name, status, start, ende in uebungen:
    cur = db.execute(
        "INSERT INTO uebungen (name, status, start_zeit, end_zeit) VALUES (?, ?, ?, ?)",
        (name, status, start, ende)
    )
    uebung_ids.append(cur.lastrowid)
    print(f"  Übung '{name}' ({status}) → id {cur.lastrowid}")

db.commit()
print(f"\n✓ {len(uebung_ids)} Übungen angelegt\n")

# -----------------------------------------------
# Messgeräte pro Übung
# -----------------------------------------------
messgeraete_sets = {
    uebung_ids[0]: [  # Aktive Übung
        ("Geigerzähler Frontlinie-1", "AA:BB:CC:01:01:01", "aktiv",   98.0,  5.2),
        ("Geigerzähler Frontlinie-2", "AA:BB:CC:01:01:02", "aktiv",   85.5, 38.7),
        ("Dosimeter Alpha-Team",      "AA:BB:CC:01:01:03", "aktiv",   72.0, 115.2),
        ("Feldmessgerät Ost",         "AA:BB:CC:01:01:04", "aktiv",   91.0,  62.3),
        ("Personendosimeter P-01",    "AA:BB:CC:01:01:05", "fehler",  12.0, 201.4),
    ],
    uebung_ids[1]: [  # Abgeschlossene Übung
        ("Geigerzähler Bravo-Nord",   "AA:BB:CC:02:01:01", "inaktiv", 45.0,  22.7),
        ("Geigerzähler Bravo-Süd",    "AA:BB:CC:02:01:02", "inaktiv", 50.0,  89.2),
        ("Kontrollpunkt K-1",         "AA:BB:CC:02:01:03", "inaktiv", 80.0, 145.8),
    ],
    uebung_ids[2]: [  # Vorbereitung
        ("Testgerät Vorbereitung-1",  "AA:BB:CC:03:01:01", "inaktiv", 100.0,  0.0),
        ("Testgerät Vorbereitung-2",  "AA:BB:CC:03:01:02", "inaktiv", 100.0,  0.0),
    ],
}

geraet_ids = []
for uebung_id, geraete in messgeraete_sets.items():
    for name, mac, status, akku, dosis in geraete:
        cur = db.execute(
            """INSERT INTO geraete (uebung_id, name, typ, gesamtdosis, mac_adresse, status, akku)
               VALUES (?, ?, 'messgeraet', ?, ?, ?, ?)""",
            (uebung_id, name, dosis, mac, status, akku)
        )
        geraet_ids.append((cur.lastrowid, uebung_id, dosis))
        print(f"  Messgerät '{name}' → id {cur.lastrowid} (Übung {uebung_id})")

db.commit()

# -----------------------------------------------
# Strahlungsquellen pro Übung
# -----------------------------------------------
quellen_sets = {
    uebung_ids[0]: [
        ("Quelle Gamma-Haupt",   0.00, 0.00, 3.50, "AA:BB:CC:01:02:01", "aktiv",  95.0),
        ("Quelle Alpha-Flank",   1.20, 0.00, 0.00, "AA:BB:CC:01:02:02", "aktiv",  88.0),
        ("Quelle Mix-Zentrum",   0.40, 0.90, 1.80, "AA:BB:CC:01:02:03", "fehler", 23.0),
    ],
    uebung_ids[1]: [
        ("Quelle Bravo-Main",    0.00, 2.50, 0.00, "AA:BB:CC:02:02:01", "inaktiv", 0.0),
        ("Quelle Bravo-Side",    0.60, 0.00, 1.10, "AA:BB:CC:02:02:02", "inaktiv", 0.0),
    ],
    uebung_ids[2]: [
        ("Simulator Vorbereitung", 0.10, 0.20, 0.50, "AA:BB:CC:03:02:01", "inaktiv", 100.0),
    ],
}

for uebung_id, quellen in quellen_sets.items():
    for name, alpha, beta, gamma, mac, status, akku in quellen:
        cur = db.execute(
            """INSERT INTO geraete (uebung_id, name, typ, staerke_alpha, staerke_beta, staerke_gamma,
               mac_adresse, status, akku)
               VALUES (?, ?, 'quelle', ?, ?, ?, ?, ?, ?)""",
            (uebung_id, name, alpha, beta, gamma, mac, status, akku)
        )
        print(f"  Quelle '{name}' → id {cur.lastrowid} (Übung {uebung_id})")

db.commit()

# -----------------------------------------------
# Geräte OHNE Übungszuordnung (für "Aus DB wählen"-Test)
# -----------------------------------------------
print("\n── Geräte ohne Übung (für DB-Auswahl-Test) ──")
ohne_uebung = [
    ("Reservegerät Reserve-1",  "messgeraet", "AA:BB:CC:99:01:01", "inaktiv", 100.0, 0.0,  0,    0,    0),
    ("Reservegerät Reserve-2",  "messgeraet", "AA:BB:CC:99:01:02", "inaktiv",  67.0, 12.5, 0,    0,    0),
    ("Altgerät Lager-A",        "messgeraet", "AA:BB:CC:99:01:03", "inaktiv",  34.0, 78.3, 0,    0,    0),
    ("Lagerquelle L-Alpha",     "quelle",     "AA:BB:CC:99:02:01", "inaktiv", 100.0, 0.0,  2.00, 0.00, 0.00),
    ("Lagerquelle L-Gamma",     "quelle",     "AA:BB:CC:99:02:02", "inaktiv", 100.0, 0.0,  0.00, 0.00, 4.50),
]

for name, typ, mac, status, akku, dosis, alpha, beta, gamma in ohne_uebung:
    cur = db.execute(
        """INSERT INTO geraete (uebung_id, name, typ, gesamtdosis, staerke_alpha, staerke_beta,
           staerke_gamma, mac_adresse, status, akku)
           VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, typ, dosis, alpha, beta, gamma, mac, status, akku)
    )
    print(f"  '{name}' ({typ}) → id {cur.lastrowid} (keine Übung)")

db.commit()

# -----------------------------------------------
# Testmessungen für aktive Übung
# -----------------------------------------------
print("\n── Testmessungen für aktive Übung ──")
aktive_geraete = [(gid, uid, dosis) for gid, uid, dosis in geraet_ids if uid == uebung_ids[0]]

for gid, uid, basisdosis in aktive_geraete:
    for j in range(12):
        ts = now - timedelta(seconds=(12 - j) * 5)
        variation = basisdosis + random.uniform(-basisdosis * 0.08, basisdosis * 0.08)
        variation = max(0, round(variation, 2))
        db.execute(
            "INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp) VALUES (?, ?, ?, ?, ?)",
            (gid, uid, round(variation * 10, 1), variation, ts.strftime("%Y-%m-%d %H:%M:%S"))
        )
    print(f"  12 Messungen für Gerät {gid} (Basis: {basisdosis} mSv)")

db.commit()

print(f"""
╔══════════════════════════════════════════════════════╗
║  Testdaten erfolgreich eingefügt!                    ║
╠══════════════════════════════════════════════════════╣
║  3 Übungen:                                          ║
║    • Übung Alpha 2025       → aktiv                  ║
║    • Übung Bravo 2025       → abgeschlossen          ║
║    • Notfallsimulation C    → vorbereitung           ║
║                                                      ║
║  Messgeräte: 10  |  Quellen: 6  |  Ohne Übung: 5    ║
║                                                      ║
║  Zum Testen von "Aus DB wählen":                     ║
║    3× Messgerät + 2× Quelle ohne uebung_id           ║
╚══════════════════════════════════════════════════════╝
""")