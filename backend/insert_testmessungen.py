from database import get_db
import random
from datetime import datetime, timedelta

db = get_db()

# Alle Messgeräte aus der DB holen
messgeraete = db.execute(
    "SELECT id FROM geraete WHERE typ = 'messgeraet'"
).fetchall()

if not messgeraete:
    print("❌ Keine Messgeräte gefunden – zuerst insert_testdaten.py ausführen!")
    exit()

# Aktive Übung holen falls vorhanden
uebung = db.execute(
    "SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1"
).fetchone()
uebung_id = uebung["id"] if uebung else None

# Pro Messgerät: 10 historische Messungen + 1 aktueller Wert
# Die aktuellen Werte decken alle Farbstufen ab
aktuelle_dosen = [
    5.2,   # grün
    12.8,  # grün
    18.9,  # grün
    25.4,  # gelb
    38.7,  # gelb
    45.1,  # gelb
    62.3,  # orange
    78.9,  # orange
    95.5,  # orange
    115.2, # rot
    138.6, # rot
    158.3, # rot
    172.1, # rot
    185.7, # rot
    201.4, # lila
    218.9, # lila
    225.3, # lila
    233.1, # lila
    241.8, # lila
    248.5, # lila
]

now = datetime.now()

for i, geraet in enumerate(messgeraete):
    gid         = geraet["id"]
    aktuell     = aktuelle_dosen[i % len(aktuelle_dosen)]

    # 10 historische Messungen mit leicht variierenden Werten
    for j in range(10):
        timestamp = now - timedelta(seconds=(10 - j) * 2)
        variation = aktuell + random.uniform(-aktuell * 0.1, aktuell * 0.1)
        variation = max(0, round(variation, 2))

        db.execute(
            "INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp) VALUES (?, ?, ?, ?, ?)",
            (gid, uebung_id, round(variation * 12, 1), variation, timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        )

    # Aktuellste Messung – dieser Wert wird vom Watcher als erstes gepickt
    db.execute(
        "INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp) VALUES (?, ?, ?, ?, ?)",
        (gid, uebung_id, round(aktuell * 12, 1), aktuell, now.strftime("%Y-%m-%d %H:%M:%S"))
    )

    print(f"  Gerät {gid}: {aktuell} mSv/h (aktuell) + 10 historische Werte")

db.commit()
print(f"\n✓ Messungen für {len(messgeraete)} Geräte eingefügt!")
print("  Der Watcher zeigt die Werte innerhalb von ~1 Sekunde auf der Website.")
print("  Tipp: Datei nach dem Test löschen.")