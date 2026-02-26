from database import get_db
import random

db = get_db()

# -----------------------------------------------
# Messgeräte (20 Stück)
# -----------------------------------------------
messgeraete = [
    ("Geigerzähler Alpha-1",  "192.168.1.10"),
    ("Geigerzähler Alpha-2",  "192.168.1.11"),
    ("Geigerzähler Bravo-1",  "192.168.1.12"),
    ("Geigerzähler Bravo-2",  "192.168.1.13"),
    ("Dosimeter Station 1",   "192.168.1.14"),
    ("Dosimeter Station 2",   "192.168.1.15"),
    ("Dosimeter Station 3",   "192.168.1.16"),
    ("Dosimeter Station 4",   "192.168.1.17"),
    ("Messgerät Nord",        "192.168.1.18"),
    ("Messgerät Süd",         "192.168.1.19"),
    ("Messgerät Ost",         "192.168.1.20"),
    ("Messgerät West",        "192.168.1.21"),
    ("Feldmessgerät A",       "192.168.1.22"),
    ("Feldmessgerät B",       "192.168.1.23"),
    ("Feldmessgerät C",       "192.168.1.24"),
    ("Kontrollpunkt 1",       "192.168.1.25"),
    ("Kontrollpunkt 2",       "192.168.1.26"),
    ("Kontrollpunkt 3",       "192.168.1.27"),
    ("Personendosimeter P1",  "192.168.1.28"),
    ("Personendosimeter P2",  "192.168.1.29"),
]

# Gesamtdosen variieren stark – von harmlos bis kritisch
gesamtdosen = [
    2.1, 8.5, 15.3, 22.7, 35.0,
    48.9, 67.4, 89.2, 112.5, 145.8,
    178.3, 210.6, 5.0, 31.2, 55.7,
    93.1, 130.4, 165.9, 199.2, 240.0
]

for i, (name, ip) in enumerate(messgeraete):
    db.execute(
        "INSERT INTO geraete (name, typ, gesamtdosis, mcu_adresse) VALUES (?, ?, ?, ?)",
        (name, "messgeraet", gesamtdosen[i], ip)
    )

print("✓ 20 Messgeräte eingefügt")

# -----------------------------------------------
# Strahlungsquellen (20 Stück)
# -----------------------------------------------
quellen = [
    ("Quelle Alpha-1",   0.50, 0.00, 0.00, "192.168.2.10"),
    ("Quelle Alpha-2",   1.20, 0.00, 0.00, "192.168.2.11"),
    ("Quelle Beta-1",    0.00, 0.80, 0.00, "192.168.2.12"),
    ("Quelle Beta-2",    0.00, 2.50, 0.00, "192.168.2.13"),
    ("Quelle Gamma-1",   0.00, 0.00, 1.50, "192.168.2.14"),
    ("Quelle Gamma-2",   0.00, 0.00, 3.20, "192.168.2.15"),
    ("Quelle AB-Mix",    0.30, 0.70, 0.00, "192.168.2.16"),
    ("Quelle AG-Mix",    0.60, 0.00, 1.10, "192.168.2.17"),
    ("Quelle BG-Mix",    0.00, 1.40, 2.00, "192.168.2.18"),
    ("Quelle ABC-Mix",   0.40, 0.90, 1.80, "192.168.2.19"),
    ("Strahler Nord-1",  2.00, 0.00, 0.00, "192.168.2.20"),
    ("Strahler Nord-2",  0.00, 3.50, 0.00, "192.168.2.21"),
    ("Strahler Süd-1",   0.00, 0.00, 4.00, "192.168.2.22"),
    ("Strahler Süd-2",   1.00, 1.00, 1.00, "192.168.2.23"),
    ("Simulator S1",     0.10, 0.00, 0.00, "192.168.2.24"),
    ("Simulator S2",     0.00, 0.20, 0.00, "192.168.2.25"),
    ("Simulator S3",     0.00, 0.00, 0.50, "192.168.2.26"),
    ("Simulator S4",     5.00, 0.00, 0.00, "192.168.2.27"),
    ("Hochstrahler H1",  0.00, 8.00, 5.00, "192.168.2.28"),
    ("Hochstrahler H2",  3.00, 4.00, 6.00, "192.168.2.29"),
]

for name, alpha, beta, gamma, ip in quellen:
    db.execute(
        "INSERT INTO geraete (name, typ, staerke_alpha, staerke_beta, staerke_gamma, mcu_adresse) VALUES (?, ?, ?, ?, ?, ?)",
        (name, "quelle", alpha, beta, gamma, ip)
    )

print("✓ 20 Strahlungsquellen eingefügt")

db.commit()
print("\n✓ Alle Testdaten erfolgreich eingefügt!")
print("  Tipp: Datei nach dem Test löschen.")

# create_user.py
from werkzeug.security import generate_password_hash
from database import get_db

def create_user(username, password, rolle="teilnehmer"):
    db = get_db()
    db.execute(
        "INSERT INTO users (username, password_hash, rolle) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), rolle)
    )
    db.commit()
    print(f"User '{username}' erstellt")

create_user("admin", "admin123", "admin")
create_user("uebungsleiter", "leiter123", "uebungsleiter")