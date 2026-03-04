"""
insert_messverlauf.py
──────────────────────────────────────────────────────────────────────────────
Füllt die messungen-Tabelle mit realistischen Verläufen für alle Messgeräte
aller vorhandenen Übungen. Ideal zum Testen der Diagramme im Live-Tab.

Ausführen aus dem backend/-Verzeichnis:
    python insert_messverlauf.py

Optionen (oben in der Datei anpassen):
    PUNKTE_PRO_GERAET  – Anzahl der Messpunkte je Gerät
    INTERVALL_SEKUNDEN – zeitlicher Abstand zwischen den Punkten
    UEBERSCHREIBEN     – True = vorhandene Messungen löschen und neu erzeugen
"""

from database import get_db
from datetime import datetime, timedelta
import random
import math

# ── Konfiguration ──────────────────────────────────────────────────────────
PUNKTE_PRO_GERAET  = 120     # Anzahl Messpunkte pro Gerät
INTERVALL_SEKUNDEN = 10      # Sekunden zwischen zwei Messpunkten
UEBERSCHREIBEN     = True    # Vorhandene Messungen ersetzen?
# ──────────────────────────────────────────────────────────────────────────

db = get_db()

# Alle Übungen holen
uebungen = db.execute("SELECT * FROM uebungen").fetchall()
if not uebungen:
    print("❌ Keine Übungen gefunden. Zuerst insert_testuebungen.py ausführen!")
    exit()

print(f"Gefundene Übungen: {len(uebungen)}")

gesamt_eingefuegt = 0

for uebung in uebungen:
    uid   = uebung["id"]
    uname = uebung["name"]

    # Messgeräte dieser Übung holen
    geraete = db.execute(
        "SELECT * FROM geraete WHERE uebung_id = ? AND typ = 'messgeraet'", (uid,)
    ).fetchall()

    if not geraete:
        print(f"  ⚠ Übung '{uname}': Keine Messgeräte – übersprungen")
        continue

    print(f"\n── Übung '{uname}' (id={uid}) – {len(geraete)} Messgeräte ──")

    if UEBERSCHREIBEN:
        for g in geraete:
            db.execute("DELETE FROM messungen WHERE geraet_id = ? AND uebung_id = ?", (g["id"], uid))
        print(f"  ✓ Alte Messungen gelöscht")

    # Startzeitpunkt: entweder start_zeit der Übung oder jetzt minus Gesamtdauer
    gesamtdauer = PUNKTE_PRO_GERAET * INTERVALL_SEKUNDEN
    if uebung["start_zeit"]:
        try:
            start = datetime.fromisoformat(str(uebung["start_zeit"]))
        except:
            start = datetime.now() - timedelta(seconds=gesamtdauer)
    else:
        start = datetime.now() - timedelta(seconds=gesamtdauer)

    for geraet in geraete:
        gid        = geraet["id"]
        basisDosis = float(geraet["gesamtdosis"] or 0)

        # Startdosis = ca. 10–30% der Enddosis (simuliert Anstieg während Übung)
        startDosis = basisDosis * random.uniform(0.05, 0.25)

        # Strahlungstyp bestimmt den Verlaufsstil
        # (zufällig: Anstieg, Plateau mit Spitzen, wellenförmig)
        verlauf = random.choice(["anstieg", "welle", "spitzen"])

        print(f"  Gerät '{geraet['name']}' (id={gid}) – Verlauf: {verlauf}, Zieldosis: {basisDosis:.1f} mSv")

        for i in range(PUNKTE_PRO_GERAET):
            t    = start + timedelta(seconds=i * INTERVALL_SEKUNDEN)
            frac = i / max(PUNKTE_PRO_GERAET - 1, 1)  # 0.0 → 1.0

            # Gesamtdosis: monoton steigend von startDosis zu basisDosis
            dosis = startDosis + (basisDosis - startDosis) * frac
            dosis += random.gauss(0, basisDosis * 0.02)
            dosis = max(0, round(dosis, 2))

            # Dosisrate (cps) je nach Verlaufstyp
            if verlauf == "anstieg":
                # Linearer Anstieg mit leichtem Rauschen
                basis_rate = (basisDosis / max(PUNKTE_PRO_GERAET * INTERVALL_SEKUNDEN / 3600, 0.001)) * (0.5 + frac)
                cps = basis_rate * random.uniform(0.85, 1.15)

            elif verlauf == "welle":
                # Sinuswelle – simuliert periodische Schwankungen
                basis_rate = basisDosis / max(PUNKTE_PRO_GERAET * INTERVALL_SEKUNDEN / 3600, 0.001)
                cps = basis_rate * (0.6 + 0.4 * math.sin(frac * math.pi * 4)) * random.uniform(0.9, 1.1)

            else:  # spitzen
                # Flacher Verlauf mit gelegentlichen Spitzen
                basis_rate = (basisDosis / max(PUNKTE_PRO_GERAET * INTERVALL_SEKUNDEN / 3600, 0.001)) * 0.4
                if random.random() < 0.08:  # 8% Chance für Spitze
                    cps = basis_rate * random.uniform(3, 6)
                else:
                    cps = basis_rate * random.uniform(0.8, 1.2)

            cps = max(0, round(cps, 3))

            db.execute(
                "INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp) VALUES (?, ?, ?, ?, ?)",
                (gid, uid, cps, dosis, t.strftime("%Y-%m-%d %H:%M:%S"))
            )
            gesamt_eingefuegt += 1

db.commit()

print(f"""
╔══════════════════════════════════════════════════════════╗
║  Messverlauf erfolgreich eingefügt!                      ║
╠══════════════════════════════════════════════════════════╣
║  Übungen verarbeitet : {len(uebungen):<4}                             ║
║  Messpunkte gesamt   : {gesamt_eingefuegt:<6}                           ║
║  Intervall           : {INTERVALL_SEKUNDEN} Sekunden pro Punkt          ║
╚══════════════════════════════════════════════════════════╝

→ Jetzt im Browser den Tab "Live-Messung" öffnen.
""")