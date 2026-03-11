"""
mqtt_backend.py
──────────────────────────────────────────────────────────────────────────────
MQTT-Bridge für Radsim – verbindet Strahlungsquellen (ESP32 Quelle) und
Messgeräte/Zähler (ESP32 Zähler) mit der radsim.db Datenbank.

┌─────────────────────────────────────────────────────────────────────────┐
│  QUELLE  (typ = 'quelle')                                               │
│  Server → Quelle   sources/cmd/<mac>                                    │
│    {                                                                    │
│      "alpha":  1.20,    ← Strahlungsintensität Alpha  (float, mSv/h)   │
│      "beta":   0.00,    ← Strahlungsintensität Beta   (float, mSv/h)   │
│      "gamma":  3.50,    ← Strahlungsintensität Gamma  (float, mSv/h)   │
│      "status": "aktiv"  ← Statusvariable                               │
│    }                                                                    │
│  Quelle → Server   (kein Empfang / keine Subscription)                  │
├─────────────────────────────────────────────────────────────────────────┤
│  ZÄHLER  (typ = 'messgeraet')                                           │
│  Server → Zähler   devices/cmd/<mac>                                    │
│    {                                                                    │
│      "offset": 0.0,     ← Offset-Variable                              │
│      "reset":  false,   ← Reset-Variable (bool)                        │
│      "status": "aktiv"  ← Statusvariable                               │
│    }                                                                    │
│  Zähler → Server   devices/data                                         │
│    {                                                                    │
│      "mac":   "AA:BB:CC:DD:EE:FF",                                     │
│      "cps":   12.5,     ← Zählrate (Impulse/s)                         │
│      "dosis": 3.7       ← kumulierte Gesamtdosis (mSv)                 │
│    }                                                                    │
└─────────────────────────────────────────────────────────────────────────┘

Voraussetzungen:
    pip install paho-mqtt

Starten:
    python mqtt_backend.py
"""

import json
import sqlite3
import paho.mqtt.client as mqtt
from datetime import datetime

# ── Konfiguration ──────────────────────────────────────────────────────────
MQTT_BROKER          = "localhost"       # IP/Hostname des MQTT-Brokers
MQTT_PORT            = 1883
MQTT_TOPIC_ZAEHLER_IN = "devices/data"  # Zähler → Server (Messdaten)
# Server → Zähler:   devices/cmd/<mac>
# Server → Quelle:   sources/cmd/<mac>
DB_FILE              = "radsim.db"
# ──────────────────────────────────────────────────────────────────────────


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def geraet_by_mac(c, mac: str):
    """Gerät anhand MAC-Adresse aus DB holen."""
    return c.execute(
        "SELECT * FROM geraete WHERE mac_adresse = ?", (mac,)
    ).fetchone()


def aktive_uebung_id(c):
    """ID der aktuell aktiven Übung, oder None."""
    row = c.execute(
        "SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


# ── MQTT Callbacks ─────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}:{MQTT_PORT}")
        # Nur Zähler-Daten abonnieren – Quellen senden nichts an den Server
        client.subscribe(MQTT_TOPIC_ZAEHLER_IN)
        print(f"[MQTT] Abonniert: {MQTT_TOPIC_ZAEHLER_IN}  (Zähler → Server)")
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen (rc={rc})")


def on_message(client, userdata, msg):
    """Empfängt Messdaten vom Zähler (Messgerät)."""
    try:
        data  = json.loads(msg.payload.decode())
        mac   = data.get("mac", "").strip().upper()
        cps   = float(data.get("cps",   0.0))
        dosis = float(data.get("dosis", 0.0))

        if not mac:
            print("[WARN] Nachricht ohne MAC ignoriert")
            return

        conn = get_db()
        c    = conn.cursor()

        geraet = geraet_by_mac(c, mac)

        if not geraet:
            # Unbekanntes Gerät → automatisch als Messgerät registrieren
            uebung_id = aktive_uebung_id(c)
            c.execute(
                """INSERT INTO geraete
                   (name, typ, mac_adresse, status, gesamtdosis, uebung_id)
                   VALUES (?, 'messgeraet', ?, 'aktiv', ?, ?)""",
                (f"Zähler {mac[-8:]}", mac, dosis, uebung_id)
            )
            conn.commit()
            geraet = geraet_by_mac(c, mac)
            print(f"[DB] Neuer Zähler registriert: {mac} (id={geraet['id']})")

        geraet_id = geraet["id"]
        uebung_id = geraet["uebung_id"]

        # Messung speichern
        c.execute(
            """INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (geraet_id, uebung_id, cps, dosis,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

        # Gesamtdosis + letzter_kontakt aktualisieren
        c.execute(
            """UPDATE geraete
               SET gesamtdosis = ?, letzter_kontakt = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (dosis, geraet_id)
        )
        conn.commit()

        aktuell = c.execute(
            "SELECT gesamtdosis FROM geraete WHERE id = ?", (geraet_id,)
        ).fetchone()
        gesamtdosis_aktuell = float(aktuell["gesamtdosis"] or 0)
        conn.close()

        print(f"[ZÄHLER] {mac} → cps={cps}, dosis={dosis} mSv (id={geraet_id})")

    except json.JSONDecodeError:
        print(f"[WARN] Ungültiges JSON: {msg.payload}")
    except Exception as e:
        print(f"[FEHLER] on_message: {e}")


# ── Sende-Funktionen (Server-initiiert) ───────────────────────────────────

def send_quelle_cmd(client, mac: str,
                    alpha: float, beta: float, gamma: float,
                    status: str = "aktiv"):
    """
    Sendet Strahlungsparameter an eine Quelle.
    Topic: sources/cmd/<MAC>
    Payload:
        { "alpha": 1.20, "beta": 0.00, "gamma": 3.50, "status": "aktiv" }
    """
    payload = {
        "alpha":  round(float(alpha),  3),
        "beta":   round(float(beta),   3),
        "gamma":  round(float(gamma),  3),
        "status": status,
    }
    topic = f"sources/cmd/{mac.upper()}"
    client.publish(topic, json.dumps(payload), qos=1)
    print(f"[QUELLE→] {topic}  α={alpha} β={beta} γ={gamma} status={status}")


def send_zaehler_cmd(client, mac: str,
                     offset: float = 0.0,
                     reset: bool   = False,
                     status: str   = "aktiv"):
    """
    Sendet Steuerparameter an einen Zähler.
    Topic: devices/cmd/<MAC>
    Payload:
        { "offset": 0.0, "reset": false, "status": "aktiv" }
    """
    payload = {
        "offset": round(float(offset), 3),
        "reset":  bool(reset),
        "status": status,
    }
    topic = f"devices/cmd/{mac.upper()}"
    client.publish(topic, json.dumps(payload), qos=1)
    print(f"[ZÄHLER→] {topic}  offset={offset} reset={reset} status={status}")


# ── DB-Sync: alle bekannten Quellen mit aktuellen Werten pushen ────────────

def sync_quellen(client):
    """
    Liest alle Quellen aus der DB und schickt deren aktuelle
    Alpha/Beta/Gamma-Werte per MQTT an die jeweiligen Geräte.
    Nützlich beim Server-Start oder nach DB-Änderungen.
    """
    try:
        conn = get_db()
        quellen = conn.execute(
            """SELECT mac_adresse, staerke_alpha, staerke_beta, staerke_gamma, status
               FROM geraete
               WHERE typ = 'quelle' AND mac_adresse IS NOT NULL"""
        ).fetchall()
        conn.close()

        for q in quellen:
            if q["mac_adresse"]:
                send_quelle_cmd(
                    client,
                    mac    = q["mac_adresse"],
                    alpha  = q["staerke_alpha"] or 0.0,
                    beta   = q["staerke_beta"]  or 0.0,
                    gamma  = q["staerke_gamma"] or 0.0,
                    status = q["status"]        or "aktiv",
                )
        print(f"[SYNC] {len(quellen)} Quellen synchronisiert")
    except Exception as e:
        print(f"[FEHLER] sync_quellen: {e}")


def sync_zaehler(client):
    """
    Sendet Default-Steuerparameter (offset=0, reset=False, status) an alle
    bekannten Messgeräte beim Server-Start.
    """
    try:
        conn = get_db()
        zaehler = conn.execute(
            """SELECT mac_adresse, status
               FROM geraete
               WHERE typ = 'messgeraet' AND mac_adresse IS NOT NULL"""
        ).fetchall()
        conn.close()

        for z in zaehler:
            if z["mac_adresse"]:
                send_zaehler_cmd(
                    client,
                    mac    = z["mac_adresse"],
                    offset = 0.0,
                    reset  = False,
                    status = z["status"] or "aktiv",
                )
        print(f"[SYNC] {len(zaehler)} Zähler synchronisiert")
    except Exception as e:
        print(f"[FEHLER] sync_zaehler: {e}")


# ── Client starten ─────────────────────────────────────────────────────────

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] Verbinde mit {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    # Nach Verbindung alle bekannten Geräte mit aktuellen Werten versorgen
    client.on_connect_ext = None  # wird nach on_connect aufgerufen

    def on_connect_with_sync(c, userdata, flags, rc):
        on_connect(c, userdata, flags, rc)
        if rc == 0:
            sync_quellen(c)
            sync_zaehler(c)

    client.on_connect = on_connect_with_sync
    client.loop_forever()


if __name__ == "__main__":
    main()