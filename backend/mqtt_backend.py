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
│      "offset_alpha": 0.0,   ← Alpha-Offset   (float, mSv/h)           │
│      "offset_beta":  0.0,   ← Beta-Offset    (float, mSv/h)           │
│      "offset_gamma": 0.0,   ← Gamma-Offset   (float, mSv/h)           │
│      "reset":  false,       ← Reset-Variable (bool)                    │
│      "status": "aktiv"      ← Statusvariable                           │
│    }                                                                    │
│  Zähler → Server   devices/data                                         │
│    {                                                                    │
│      "mac":   "AA:BB:CC:DD:EE:FF",                                     │
│      "cps":   12.5,     ← Zählrate (Impulse/s)                         │
│      "dosis": 3.7       ← kumulierte Gesamtdosis (mSv)                 │
│    }                                                                    │
└─────────────────────────────────────────────────────────────────────────┘

HTTP-API (für Website-Integration):
  POST /api/offset
    Body (JSON):
      {
        "geraet_id":    5,
        "offset_alpha": 0.5,
        "offset_beta":  0.0,
        "offset_gamma": 1.2,
        "reset":        false
      }
    → Speichert Werte in DB und sendet sofort per MQTT an das Gerät.
    Response: { "ok": true, "mac": "AA:...", "sent": {...} }

  GET /api/messgeraete
    → Gibt alle Messgeräte mit aktuellen Offset-Werten zurück.

  POST /api/reset/<geraet_id>
    → Setzt offset_reset=1 in DB und sendet Reset-Befehl per MQTT.
      Nach dem Senden wird offset_reset automatisch auf 0 zurückgesetzt.

Voraussetzungen:
    pip install paho-mqtt flask flask-cors

Starten:
    python mqtt_backend.py
──────────────────────────────────────────────────────────────────────────────
"""

import json
import sqlite3
import threading
import paho.mqtt.client as mqtt
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Konfiguration ──────────────────────────────────────────────────────────
MQTT_BROKER           = "localhost"      # IP/Hostname des MQTT-Brokers
MQTT_PORT             = 1883
MQTT_TOPIC_ZAEHLER_IN = "devices/data"  # Zähler → Server (Messdaten)
# Server → Zähler:   devices/cmd/<mac>
# Server → Quelle:   sources/cmd/<mac>
DB_FILE               = "radsim.db"
HTTP_HOST             = "0.0.0.0"
HTTP_PORT             = 5001            # Flask-HTTP-API-Port
# ──────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Website darf Cross-Origin anfragen

# Globaler MQTT-Client (wird in main() gesetzt, damit HTTP-Handler ihn nutzen können)
_mqtt_client: mqtt.Client | None = None


# ── Datenbank-Hilfsfunktionen ──────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def geraet_by_mac(c, mac: str):
    """Gerät anhand MAC-Adresse aus DB holen."""
    return c.execute(
        "SELECT * FROM geraete WHERE mac_adresse = ?", (mac,)
    ).fetchone()


def geraet_by_id(c, geraet_id: int):
    """Gerät anhand ID aus DB holen."""
    return c.execute(
        "SELECT * FROM geraete WHERE id = ?", (geraet_id,)
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

        # Falls offset_reset=1 gesetzt war: nach erfolgtem Kontakt zurücksetzen
        if geraet["offset_reset"]:
            c.execute(
                "UPDATE geraete SET offset_reset = 0 WHERE id = ?",
                (geraet_id,)
            )
            print(f"[DB] offset_reset für Gerät {geraet_id} zurückgesetzt")

        conn.commit()
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
                     offset_alpha: float = 0.0,
                     offset_beta:  float = 0.0,
                     offset_gamma: float = 0.0,
                     reset: bool         = False,
                     status: str         = "aktiv"):
    """
    Sendet Offset-Steuerparameter an einen Zähler.
    Topic: devices/cmd/<MAC>
    Payload:
        {
          "offset_alpha": 0.0,
          "offset_beta":  0.0,
          "offset_gamma": 0.0,
          "reset":        false,
          "status":       "aktiv"
        }
    """
    payload = {
        "offset_alpha": round(float(offset_alpha), 3),
        "offset_beta":  round(float(offset_beta),  3),
        "offset_gamma": round(float(offset_gamma), 3),
        "reset":        bool(reset),
        "status":       status,
    }
    topic = f"devices/cmd/{mac.upper()}"
    client.publish(topic, json.dumps(payload), qos=1)
    print(
        f"[ZÄHLER→] {topic}  "
        f"α_off={offset_alpha} β_off={offset_beta} γ_off={offset_gamma} "
        f"reset={reset} status={status}"
    )
    return payload


# ── DB-Sync: alle bekannten Quellen mit aktuellen Werten pushen ────────────

def sync_quellen(client):
    """
    Liest alle Quellen aus der DB und schickt deren aktuelle
    Alpha/Beta/Gamma-Werte per MQTT an die jeweiligen Geräte.
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
    Sendet aktuelle Offset-Werte und Status an alle bekannten Messgeräte.
    Beim Start werden gespeicherte Offsets wiederhergestellt.
    """
    try:
        conn = get_db()
        zaehler = conn.execute(
            """SELECT mac_adresse, status,
                      offset_alpha, offset_beta, offset_gamma, offset_reset
               FROM geraete
               WHERE typ = 'messgeraet' AND mac_adresse IS NOT NULL"""
        ).fetchall()
        conn.close()

        for z in zaehler:
            if z["mac_adresse"]:
                send_zaehler_cmd(
                    client,
                    mac          = z["mac_adresse"],
                    offset_alpha = z["offset_alpha"] or 0.0,
                    offset_beta  = z["offset_beta"]  or 0.0,
                    offset_gamma = z["offset_gamma"] or 0.0,
                    reset        = bool(z["offset_reset"]),
                    status       = z["status"]        or "aktiv",
                )
        print(f"[SYNC] {len(zaehler)} Zähler synchronisiert")
    except Exception as e:
        print(f"[FEHLER] sync_zaehler: {e}")


# ── HTTP-API für Website ───────────────────────────────────────────────────

@app.route("/api/messgeraete", methods=["GET"])
def api_messgeraete():
    """
    Gibt alle Messgeräte mit aktuellen Offset-Werten zurück.
    GET /api/messgeraete
    """
    try:
        conn = get_db()
        geraete = conn.execute(
            """SELECT id, name, mac_adresse, status, akku,
                      letzter_kontakt, gesamtdosis,
                      offset_alpha, offset_beta, offset_gamma, offset_reset
               FROM geraete
               WHERE typ = 'messgeraet'
               ORDER BY name"""
        ).fetchall()
        conn.close()

        result = [dict(g) for g in geraete]
        return jsonify({"ok": True, "geraete": result})
    except Exception as e:
        return jsonify({"ok": False, "fehler": str(e)}), 500


@app.route("/api/offset", methods=["POST"])
def api_set_offset():
    """
    Setzt Offset-Werte für ein Messgerät und sendet sie sofort per MQTT.

    POST /api/offset
    Body:
    {
        "geraet_id":    5,
        "offset_alpha": 0.5,   ← mSv/h (gleiche Einheit wie Quellen-Stärken)
        "offset_beta":  0.0,
        "offset_gamma": 1.2,
        "reset":        false  ← optional, default false
    }
    """
    global _mqtt_client

    if not _mqtt_client:
        return jsonify({"ok": False, "fehler": "MQTT-Client nicht verfügbar"}), 503

    body = request.get_json(force=True)
    if not body:
        return jsonify({"ok": False, "fehler": "Kein JSON-Body"}), 400

    geraet_id    = body.get("geraet_id")
    offset_alpha = float(body.get("offset_alpha", 0.0))
    offset_beta  = float(body.get("offset_beta",  0.0))
    offset_gamma = float(body.get("offset_gamma", 0.0))
    reset        = bool(body.get("reset",         False))

    if geraet_id is None:
        return jsonify({"ok": False, "fehler": "geraet_id fehlt"}), 400

    try:
        conn = get_db()
        c    = conn.cursor()

        geraet = geraet_by_id(c, geraet_id)
        if not geraet:
            conn.close()
            return jsonify({"ok": False, "fehler": f"Gerät {geraet_id} nicht gefunden"}), 404

        if geraet["typ"] != "messgeraet":
            conn.close()
            return jsonify({"ok": False, "fehler": "Gerät ist kein Messgerät"}), 400

        mac = geraet["mac_adresse"]
        if not mac:
            conn.close()
            return jsonify({"ok": False, "fehler": "Gerät hat keine MAC-Adresse"}), 400

        # Werte in DB speichern
        c.execute(
            """UPDATE geraete
               SET offset_alpha = ?,
                   offset_beta  = ?,
                   offset_gamma = ?,
                   offset_reset = ?
               WHERE id = ?""",
            (offset_alpha, offset_beta, offset_gamma, 1 if reset else 0, geraet_id)
        )
        conn.commit()
        conn.close()

        # Sofort per MQTT senden
        sent = send_zaehler_cmd(
            _mqtt_client,
            mac          = mac,
            offset_alpha = offset_alpha,
            offset_beta  = offset_beta,
            offset_gamma = offset_gamma,
            reset        = reset,
            status       = geraet["status"] or "aktiv",
        )

        return jsonify({
            "ok":     True,
            "mac":    mac,
            "sent":   sent,
        })

    except Exception as e:
        return jsonify({"ok": False, "fehler": str(e)}), 500


@app.route("/api/reset/<int:geraet_id>", methods=["POST"])
def api_reset_geraet(geraet_id: int):
    """
    Sendet einen Reset-Befehl an ein Messgerät (setzt Gesamtdosis zurück).
    Der offset_reset-Flag wird in DB auf 1 gesetzt und nach Bestätigung
    automatisch wieder auf 0 gesetzt (beim nächsten Dateneingang).

    POST /api/reset/<geraet_id>
    """
    global _mqtt_client

    if not _mqtt_client:
        return jsonify({"ok": False, "fehler": "MQTT-Client nicht verfügbar"}), 503

    try:
        conn = get_db()
        c    = conn.cursor()

        geraet = geraet_by_id(c, geraet_id)
        if not geraet:
            conn.close()
            return jsonify({"ok": False, "fehler": f"Gerät {geraet_id} nicht gefunden"}), 404

        mac = geraet["mac_adresse"]
        if not mac:
            conn.close()
            return jsonify({"ok": False, "fehler": "Gerät hat keine MAC-Adresse"}), 400

        # Reset-Flag setzen
        c.execute(
            "UPDATE geraete SET offset_reset = 1 WHERE id = ?",
            (geraet_id,)
        )
        conn.commit()
        conn.close()

        # Reset-Befehl senden (Offsets bleiben erhalten)
        sent = send_zaehler_cmd(
            _mqtt_client,
            mac          = mac,
            offset_alpha = float(geraet["offset_alpha"] or 0.0),
            offset_beta  = float(geraet["offset_beta"]  or 0.0),
            offset_gamma = float(geraet["offset_gamma"] or 0.0),
            reset        = True,
            status       = geraet["status"] or "aktiv",
        )

        return jsonify({"ok": True, "mac": mac, "sent": sent})

    except Exception as e:
        return jsonify({"ok": False, "fehler": str(e)}), 500


# ── Client starten ─────────────────────────────────────────────────────────

def start_http_server():
    """Flask-HTTP-Server in eigenem Thread starten."""
    print(f"[HTTP] API-Server läuft auf http://{HTTP_HOST}:{HTTP_PORT}")
    app.run(host=HTTP_HOST, port=HTTP_PORT, use_reloader=False)


def main():
    global _mqtt_client

    client = mqtt.Client()
    _mqtt_client = client

    def on_connect_with_sync(c, userdata, flags, rc):
        on_connect(c, userdata, flags, rc)
        if rc == 0:
            sync_quellen(c)
            sync_zaehler(c)

    client.on_connect = on_connect_with_sync
    client.on_message = on_message

    print(f"[MQTT] Verbinde mit {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    # HTTP-Server parallel starten
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    client.loop_forever()


if __name__ == "__main__":
    main()