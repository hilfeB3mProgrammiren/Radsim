"""
mqtt_bridge.py
──────────────────────────────────────────────────────────────────────────────
MQTT-Bridge für Radsim – verbindet echte Messgeräte (ESP32 etc.) mit der
radsim.db Datenbank und dem Flask/SocketIO-Dashboard.

Erwartet vom Gerät (Topic: devices/data):
{
    "mac":   "AA:BB:CC:DD:EE:FF",
    "cps":   12.5,              ← Zählrate (Impulse/s) – entspricht aktueller Dosisrate
    "dosis": 3.7                ← kumulierte Gesamtdosis in mSv (optional, default 0)
}

Antwortet an Gerät (Topic: devices/response/<mac>):
{
    "geraet_id":    3,
    "gesamtdosis":  3.7,
    "server_time":  "2025-03-04T08:00:00"
}

Voraussetzungen:
    pip install paho-mqtt

Starten:
    python mqtt_bridge.py
"""

import json
import sqlite3
import paho.mqtt.client as mqtt
from datetime import datetime

# ── Konfiguration ──────────────────────────────────────────────────────────
MQTT_BROKER   = "localhost"       # IP/Hostname des MQTT-Brokers
MQTT_PORT     = 1883
MQTT_TOPIC_IN = "devices/data"    # Topic auf dem Geräte senden
DB_FILE       = "radsim.db"       # Pfad zur radsim.db (relativ oder absolut)
# ──────────────────────────────────────────────────────────────────────────


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def geraet_by_mac(c, mac):
    """Gibt das Gerät mit dieser MAC-Adresse zurück, oder None."""
    return c.execute(
        "SELECT * FROM geraete WHERE mac_adresse = ?", (mac,)
    ).fetchone()


def aktive_uebung_id(c):
    """Gibt die ID der aktuell aktiven Übung zurück, oder None."""
    row = c.execute(
        "SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Verbunden mit Broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC_IN)
        print(f"[MQTT] Abonniert: {MQTT_TOPIC_IN}")
    else:
        print(f"[MQTT] Verbindung fehlgeschlagen (rc={rc})")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())

        mac   = data.get("mac", "").strip().upper()
        cps   = float(data.get("cps",   0.0))
        dosis = float(data.get("dosis", 0.0))

        if not mac:
            print("[WARN] Nachricht ohne MAC ignoriert")
            return

        conn = get_db()
        c    = conn.cursor()

        # ── Gerät in DB suchen ──────────────────────────────────────
        geraet = geraet_by_mac(c, mac)

        if not geraet:
            # Gerät noch nicht bekannt → automatisch als Messgerät anlegen
            uebung_id = aktive_uebung_id(c)
            c.execute(
                """INSERT INTO geraete
                   (name, typ, mac_adresse, status, gesamtdosis, uebung_id)
                   VALUES (?, 'messgeraet', ?, 'aktiv', ?, ?)""",
                (f"Gerät {mac[-8:]}", mac, dosis, uebung_id)
            )
            conn.commit()
            geraet = geraet_by_mac(c, mac)
            print(f"[DB] Neues Gerät registriert: {mac} (id={geraet['id']})")
        else:
            # Bekanntes Gerät: Gesamtdosis aktualisieren falls der neue Wert größer ist
            # (Gerät sendet kumulierten Wert – wir überschreiben nicht mit kleinerem Wert)
            neue_dosis = max(float(geraet["gesamtdosis"] or 0), dosis)
            c.execute(
                "UPDATE geraete SET gesamtdosis = ?, letzter_kontakt = CURRENT_TIMESTAMP WHERE id = ?",
                (neue_dosis, geraet["id"])
            )

        geraet_id = geraet["id"]
        uebung_id = geraet["uebung_id"]

        # ── Messung speichern ───────────────────────────────────────
        c.execute(
            """INSERT INTO messungen (geraet_id, uebung_id, cps, dosis, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (geraet_id, uebung_id, cps, dosis, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

        # ── Aktuelle Gesamtdosis aus DB lesen (nach Update) ─────────
        aktuell = c.execute(
            "SELECT gesamtdosis FROM geraete WHERE id = ?", (geraet_id,)
        ).fetchone()
        gesamtdosis_aktuell = float(aktuell["gesamtdosis"] or 0)

        conn.close()

        # ── Antwort ans Gerät ───────────────────────────────────────
        response = {
            "geraet_id":   geraet_id,
            "gesamtdosis": gesamtdosis_aktuell,
            "server_time": datetime.now().isoformat()
        }
        client.publish(
            f"devices/response/{mac}",
            json.dumps(response),
            qos=1
        )

        print(f"[OK] {mac} → cps={cps}, dosis={dosis} mSv (geraet_id={geraet_id})")

    except json.JSONDecodeError:
        print(f"[WARN] Ungültiges JSON: {msg.payload}")
    except Exception as e:
        print(f"[FEHLER] {e}")


# ── Client starten ─────────────────────────────────────────────────────────
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"[MQTT] Verbinde mit {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
client.loop_forever()