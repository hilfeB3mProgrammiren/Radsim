"""
*****************************************************************************
* Copyright (c) 2026, All rights reserved
* Internal Use Only
*
* FILE:        app.py
* PROJECT:     Radsim
* MODULE:      Backend Server (Flask + SocketIO + MQTT)
*
* Description:
*   Zentrale Backend-Anwendung für das Radsim-System.
*   Stellt REST-API, WebSocket-Kommunikation (Socket.IO)
*   sowie MQTT-Anbindung für Geräte und Strahlungsquellen bereit.
*
*   Hauptfunktionen:
*   - Verwaltung von Geräten (Messgeräte & Quellen)
*   - Echtzeit-Übertragung von Messdaten via Socket.IO
*   - Speicherung und Abfrage von Messdaten (SQLite)
*   - Steuerung von Geräten über MQTT
*   - Verwaltung von Übungen (Start, Stop, Zuordnung)
*
* Notes:
*   - Verwendet eventlet für asynchrone Verarbeitung
*   - SQLite mit WAL-Modus für parallelen Zugriff
*   - MQTT-Broker läuft lokal auf Port 1883
*   - Fallback-Watcher überwacht DB auf neue Messdaten
*
* Dependencies:
*   - Python 3.x
*   - Flask
*   - Flask-SocketIO
*   - Flask-Login
*   - eventlet
*   - paho-mqtt
*
* Revision History:
*   2026-03-18  DH   Initiale Version
*
*****************************************************************************
"""
import eventlet
eventlet.monkey_patch()

import os
import json as _json
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user
from auth import auth
from database import init_db, get_db, close_db
from users import get_user_by_id

init_db()

app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False

socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

app.teardown_appcontext(close_db)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

app.register_blueprint(auth)

from flask_socketio import emit

# --------------------
# MQTT-Hilfsfunktion
# --------------------
def mqtt_publish(topic: str, payload: dict):
    """Sendet eine MQTT-Nachricht. Gibt True bei Erfolg zurück."""
    try:
        import paho.mqtt.publish as publish
        publish.single(
            topic,
            _json.dumps(payload),
            hostname="localhost",
            port=1883,
            qos=1,
        )
        print(f"[MQTT→] {topic}  {payload}")
        return True
    except Exception as e:
        print(f"[MQTT-Fehler] {topic}: {e}")
        return False


# --------------------
# SocketIO Events
# --------------------
@socketio.on("connect")
def on_connect():
    db = get_db()
    messungen = db.execute("""
        SELECT m.id, m.geraet_id, m.cps, m.dosis, m.timestamp,
               m.cps_alpha, m.cps_beta, m.cps_gamma,
               m.dosis_alpha, m.dosis_beta,
               g.gesamtdosis, g.gesamtdosis_alpha, g.gesamtdosis_beta,
               g.akku, g.status, g.letzter_kontakt
        FROM messungen m
        JOIN geraete g ON g.id = m.geraet_id
        INNER JOIN (
            SELECT geraet_id, MAX(id) as max_id
            FROM messungen
            GROUP BY geraet_id
        ) latest ON m.geraet_id = latest.geraet_id AND m.id = latest.max_id
    """).fetchall()

    for m in messungen:
        emit("measurement", {
            "id":                 m["geraet_id"],
            "cps":                m["cps"],
            "cps_alpha":          m["cps_alpha"],
            "cps_beta":           m["cps_beta"],
            "cps_gamma":          m["cps_gamma"],
            "gesamtdosis":        m["gesamtdosis"],
            "gesamtdosis_alpha":  m["gesamtdosis_alpha"],
            "gesamtdosis_beta":   m["gesamtdosis_beta"],
            "akku":               m["akku"],
            "status":             m["status"],
            "timestamp":          str(m["timestamp"]),
        })


# --------------------
# Messdaten Watcher (Fallback falls HTTP-Push fehlschlägt)
# --------------------
def messdaten_watcher():
    import sqlite3 as _sqlite3

    try:
        from database import DB_PATH
    except ImportError:
        DB_PATH = os.path.join(os.path.dirname(__file__), "radsim.db")

    letzte_ids = {}
    print(f"[Watcher] Background-Task gestartet – DB: {DB_PATH}")

    while True:
        try:
            conn = _sqlite3.connect(DB_PATH)
            conn.row_factory = _sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            try:
                neueste = conn.execute("""
                    SELECT m.id, m.geraet_id, m.cps, m.dosis, m.timestamp,
                           m.cps_alpha, m.cps_beta, m.cps_gamma,
                           m.dosis_alpha, m.dosis_beta,
                           g.gesamtdosis, g.gesamtdosis_alpha, g.gesamtdosis_beta,
                           g.akku, g.status, g.letzter_kontakt
                    FROM messungen m
                    JOIN geraete g ON g.id = m.geraet_id
                    INNER JOIN (
                        SELECT geraet_id, MAX(id) as max_id
                        FROM messungen
                        GROUP BY geraet_id
                    ) latest ON m.geraet_id = latest.geraet_id AND m.id = latest.max_id
                """).fetchall()
            finally:
                conn.close()

            for m in neueste:
                gid = m["geraet_id"]
                if letzte_ids.get(gid) != m["id"]:
                    letzte_ids[gid] = m["id"]
                    socketio.emit("measurement", {
                        "id":                gid,
                        "cps":               m["cps"],
                        "cps_alpha":         m["cps_alpha"],
                        "cps_beta":          m["cps_beta"],
                        "cps_gamma":         m["cps_gamma"],
                        "gesamtdosis":       m["gesamtdosis"],
                        "gesamtdosis_alpha": m["gesamtdosis_alpha"],
                        "gesamtdosis_beta":  m["gesamtdosis_beta"],
                        "akku":              m["akku"],
                        "status":            m["status"],
                        "timestamp":         str(m["timestamp"]),
                    })

        except Exception as e:
            print(f"[Watcher] Fehler: {e}")

        socketio.sleep(1)


# --------------------
# Interne Route für mqtt_backend → sofortiger SocketIO-Emit
# --------------------
@app.route("/internal/measurement", methods=["POST"])
def internal_measurement():
    data = request.get_json()
    if not data:
        return "", 400
    geraet_id = data.get("id")
    if geraet_id:
        db = get_db()
        g = db.execute(
            "SELECT gesamtdosis, gesamtdosis_alpha, gesamtdosis_beta FROM geraete WHERE id = ?",
            (geraet_id,)
        ).fetchone()
        if g:
            data["gesamtdosis"]       = g["gesamtdosis"]       or 0.0
            data["gesamtdosis_alpha"] = g["gesamtdosis_alpha"] or 0.0
            data["gesamtdosis_beta"]  = g["gesamtdosis_beta"]  or 0.0
    payload = {k: v for k, v in data.items() if v is not None}
    socketio.emit("measurement", payload)
    return "", 200


# --------------------
# Routes
# --------------------
@app.route("/")
def index():
    db = get_db()
    aktive_uebung = db.execute("SELECT * FROM uebungen WHERE status = 'aktiv' LIMIT 1").fetchone()
    if aktive_uebung:
        devices = db.execute(
            "SELECT * FROM geraete WHERE uebung_id = ?", (aktive_uebung["id"],)
        ).fetchall()
    else:
        devices = []
    users = db.execute("SELECT username FROM users").fetchall()
    return render_template("index.html", devices=devices, users=users, aktive_uebung=aktive_uebung)


@app.route("/add_device", methods=["POST"])
@login_required
def add_device():
    data = request.get_json()
    db = get_db()
    cur = db.execute(
        """INSERT INTO geraete
           (name, typ, staerke_alpha, staerke_beta, staerke_gamma, mac_adresse, status, akku)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data["typ"],
            data.get("staerke_alpha", 0.0),
            data.get("staerke_beta",  0.0),
            data.get("staerke_gamma", 0.0),
            data.get("mac_adresse"),
            data.get("status", "aktiv"),
            data.get("akku", 100.0)
        )
    )
    db.commit()
    # FIX: lastrowid statt ORDER BY DESC LIMIT 1 (Race condition)
    neues_geraet = dict(db.execute("SELECT * FROM geraete WHERE id = ?", (cur.lastrowid,)).fetchone())
    socketio.emit("new_device", neues_geraet)
    return jsonify(neues_geraet), 200


@app.route("/device/<int:geraet_id>", methods=["PATCH"])
@login_required
def update_device(geraet_id):
    data = request.get_json()
    db = get_db()
    erlaubte_felder = ["name", "mac_adresse", "status", "akku",
                       "staerke_alpha", "staerke_beta", "staerke_gamma", "gesamtdosis"]
    for feld in erlaubte_felder:
        if feld in data and data[feld] != "" and data[feld] is not None:
            db.execute(f"UPDATE geraete SET {feld} = ? WHERE id = ?", (data[feld], geraet_id))
    db.commit()
    aktualisiert = dict(db.execute("SELECT * FROM geraete WHERE id = ?", (geraet_id,)).fetchone())
    socketio.emit("device_updated", aktualisiert)

    # FIX: Strahlungswerte per MQTT an Quelle senden wenn Stärken geändert wurden
    strahlungs_felder = {"staerke_alpha", "staerke_beta", "staerke_gamma", "status"}
    if (aktualisiert.get("typ") == "quelle"
            and aktualisiert.get("mac_adresse")
            and strahlungs_felder & set(data.keys())):
        mqtt_publish(
            f"sources/cmd/{aktualisiert['mac_adresse'].upper()}",
            {
                "alpha":  round(float(aktualisiert.get("staerke_alpha") or 0), 3),
                "beta":   round(float(aktualisiert.get("staerke_beta")  or 0), 3),
                "gamma":  round(float(aktualisiert.get("staerke_gamma") or 0), 3),
                "status": aktualisiert.get("status") or "aktiv",
            }
        )

    return jsonify(aktualisiert), 200


@app.route("/measurements/history")
def measurements_history():
    uebung_id = request.args.get("uebung_id", type=int)
    geraet_id = request.args.get("geraet_id", type=int)
    limit     = request.args.get("limit", 100, type=int)

    db = get_db()

    if not uebung_id:
        u = db.execute("SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1").fetchone()
        uebung_id = u["id"] if u else None

    if not uebung_id:
        return jsonify([])

    # FIX: DESC + LIMIT holt die neuesten N Punkte, äußeres ASC sortiert für den Graph
    if geraet_id:
        rows = db.execute("""
            SELECT * FROM (
                SELECT m.timestamp, m.cps, m.cps_alpha, m.cps_beta, m.cps_gamma,
                       m.dosis, m.dosis_alpha, m.dosis_beta, m.geraet_id, g.name AS geraet_name
                FROM messungen m
                JOIN geraete g ON g.id = m.geraet_id
                WHERE m.uebung_id = ? AND m.geraet_id = ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            ) ORDER BY timestamp ASC
        """, (uebung_id, geraet_id, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT * FROM (
                SELECT m.timestamp, m.cps, m.cps_alpha, m.cps_beta, m.cps_gamma,
                       m.dosis, m.dosis_alpha, m.dosis_beta, m.geraet_id, g.name AS geraet_name
                FROM messungen m
                JOIN geraete g ON g.id = m.geraet_id
                WHERE m.uebung_id = ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            ) ORDER BY timestamp ASC
        """, (uebung_id, limit)).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/uebungen/liste")
def uebungen_liste():
    db = get_db()
    uebungen = db.execute("SELECT id, name, status FROM uebungen ORDER BY erstellt_am DESC").fetchall()
    result = []
    for u in uebungen:
        u = dict(u)
        geraete = db.execute(
            "SELECT id, name FROM geraete WHERE uebung_id = ? AND typ = 'messgeraet'", (u["id"],)
        ).fetchall()
        u["geraete"] = [dict(g) for g in geraete]
        result.append(u)
    return jsonify(result)


@app.route("/measurements/latest")
def measurements_latest():
    db = get_db()
    # FIX: MAX(id) statt MAX(timestamp) – Timestamps können bei schnellen Messungen gleich sein
    rows = db.execute("""
        SELECT m.geraet_id AS id,
               m.cps, m.cps_alpha, m.cps_beta, m.cps_gamma,
               m.dosis AS gesamtdosis, m.dosis_alpha, m.dosis_beta,
               g.gesamtdosis_alpha, g.gesamtdosis_beta,
               g.akku, g.status, g.letzter_kontakt
        FROM messungen m
        JOIN geraete g ON g.id = m.geraet_id
        INNER JOIN (
            SELECT geraet_id, MAX(id) AS max_id
            FROM messungen
            GROUP BY geraet_id
        ) latest ON m.geraet_id = latest.geraet_id AND m.id = latest.max_id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/devices/ohne_uebung")
@login_required
def devices_ohne_uebung():
    typ       = request.args.get("typ")
    uebung_id = request.args.get("uebung_id", type=int)
    db        = get_db()

    if uebung_id:
        if typ:
            rows = db.execute(
                "SELECT * FROM geraete WHERE (uebung_id IS NULL OR uebung_id != ?) AND typ = ?",
                (uebung_id, typ)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM geraete WHERE (uebung_id IS NULL OR uebung_id != ?)",
                (uebung_id,)
            ).fetchall()
    else:
        if typ:
            rows = db.execute(
                "SELECT * FROM geraete WHERE uebung_id IS NULL AND typ = ?", (typ,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM geraete WHERE uebung_id IS NULL").fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/device/<int:geraet_id>/add_to_uebung", methods=["POST"])
@login_required
def add_to_uebung(geraet_id):
    db = get_db()
    uebung = db.execute("SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1").fetchone()
    uebung_id = uebung["id"] if uebung else None
    db.execute("UPDATE geraete SET uebung_id = ? WHERE id = ?", (uebung_id, geraet_id))
    db.commit()
    geraet = dict(db.execute("SELECT * FROM geraete WHERE id = ?", (geraet_id,)).fetchone())
    socketio.emit("new_device", geraet)
    return jsonify(geraet), 200


@app.route("/device/<int:geraet_id>", methods=["DELETE"])
@login_required
def delete_device(geraet_id):
    db = get_db()
    db.execute("DELETE FROM messungen WHERE geraet_id = ?", (geraet_id,))
    db.execute("DELETE FROM konfiguration WHERE geraet_id = ?", (geraet_id,))
    db.execute("DELETE FROM geraete WHERE id = ?", (geraet_id,))
    db.commit()
    socketio.emit("device_deleted", {"id": geraet_id})
    return "", 200


@app.route("/device/<int:geraet_id>/remove_from_uebung", methods=["POST"])
@login_required
def remove_from_uebung(geraet_id):
    db = get_db()
    db.execute("UPDATE geraete SET uebung_id = NULL WHERE id = ?", (geraet_id,))
    db.commit()
    socketio.emit("device_updated", {"id": geraet_id, "uebung_id": None})
    return "", 200


@app.route("/device/<int:geraet_id>/reset_dosis", methods=["POST"])
@login_required
def reset_dosis(geraet_id):
    db = get_db()
    db.execute(
        """UPDATE geraete
           SET gesamtdosis = 0.0, gesamtdosis_alpha = 0.0, gesamtdosis_beta = 0.0
           WHERE id = ?""",
        (geraet_id,)
    )
    db.commit()
    socketio.emit("device_updated", {
        "id":                geraet_id,
        "gesamtdosis":       0.0,
        "gesamtdosis_alpha": 0.0,
        "gesamtdosis_beta":  0.0,
    })
    return "", 200


@app.route("/device/<int:geraet_id>/offset", methods=["POST"])
@login_required
def set_offset(geraet_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Kein JSON-Body"}), 400

    offset_alpha = float(data.get("offset_alpha", 0.0))
    offset_beta  = float(data.get("offset_beta",  0.0))
    offset_gamma = float(data.get("offset_gamma", 0.0))
    reset        = bool(data.get("reset", False))

    db = get_db()
    geraet = db.execute("SELECT * FROM geraete WHERE id = ?", (geraet_id,)).fetchone()
    if not geraet:
        return jsonify({"error": "Gerät nicht gefunden"}), 404
    if geraet["typ"] != "messgeraet":
        return jsonify({"error": "Gerät ist kein Messgerät"}), 400

    mac = geraet["mac_adresse"]

    db.execute(
        """UPDATE geraete
           SET offset_alpha = ?, offset_beta = ?, offset_gamma = ?, offset_reset = ?
           WHERE id = ?""",
        (offset_alpha, offset_beta, offset_gamma, 1 if reset else 0, geraet_id)
    )
    db.commit()

    mqtt_ok = False
    if mac:
        mqtt_ok = mqtt_publish(
            f"devices/cmd/{mac.upper()}",
            {
                "offset_alpha": round(offset_alpha, 3),
                "offset_beta":  round(offset_beta,  3),
                "offset_gamma": round(offset_gamma, 3),
                "reset":        reset,
                "status":       geraet["status"] or "aktiv",
            }
        )

    socketio.emit("device_updated", {
        "id":           geraet_id,
        "offset_alpha": offset_alpha,
        "offset_beta":  offset_beta,
        "offset_gamma": offset_gamma,
        "offset_reset": 1 if reset else 0,
    })

    return jsonify({
        "ok":      True,
        "mac":     mac,
        "mqtt_ok": mqtt_ok,
        "sent": {
            "offset_alpha": offset_alpha,
            "offset_beta":  offset_beta,
            "offset_gamma": offset_gamma,
            "reset":        reset,
        }
    }), 200


@app.route("/messgeraete/offsets")
@login_required
def get_messgeraete_offsets():
    db = get_db()
    rows = db.execute(
        """SELECT id, name, mac_adresse, status, akku, letzter_kontakt,
                  gesamtdosis, offset_alpha, offset_beta, offset_gamma, offset_reset
           FROM geraete
           WHERE typ = 'messgeraet'
           ORDER BY name"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# --------------------
# Übungen Routes
# --------------------

@app.route("/uebungen", methods=["GET"])
def get_uebungen():
    db = get_db()
    uebungen = db.execute("SELECT * FROM uebungen ORDER BY erstellt_am DESC").fetchall()
    result = []
    for u in uebungen:
        u = dict(u)
        u["anzahl_messgeraete"] = db.execute(
            "SELECT COUNT(*) FROM geraete WHERE uebung_id = ? AND typ = 'messgeraet'", (u["id"],)
        ).fetchone()[0]
        u["anzahl_quellen"] = db.execute(
            "SELECT COUNT(*) FROM geraete WHERE uebung_id = ? AND typ = 'quelle'", (u["id"],)
        ).fetchone()[0]
        result.append(u)
    return jsonify(result)


@app.route("/uebungen", methods=["POST"])
@login_required
def create_uebung():
    data = request.get_json()
    name   = data.get("name", "").strip()
    status = data.get("status", "vorbereitung")
    start  = data.get("start_zeit")

    if not name:
        return "Name fehlt", 400

    db = get_db()
    if status == "aktiv":
        db.execute("UPDATE uebungen SET status = 'abgeschlossen' WHERE status = 'aktiv'")

    cur = db.execute(
        "INSERT INTO uebungen (name, status, start_zeit) VALUES (?, ?, ?)",
        (name, status, start)
    )
    db.commit()
    neue = dict(db.execute("SELECT * FROM uebungen WHERE id = ?", (cur.lastrowid,)).fetchone())
    if status == "aktiv":
        socketio.emit("uebung_gestartet", {"id": neue["id"], "name": neue["name"]})
    return jsonify(neue), 200


@app.route("/uebung/<int:uebung_id>", methods=["GET"])
def get_uebung(uebung_id):
    db = get_db()
    u = db.execute("SELECT * FROM uebungen WHERE id = ?", (uebung_id,)).fetchone()
    if not u:
        return "Nicht gefunden", 404
    u = dict(u)
    geraete = db.execute("SELECT * FROM geraete WHERE uebung_id = ?", (uebung_id,)).fetchall()
    u["geraete"] = [dict(g) for g in geraete]
    return jsonify(u)


@app.route("/uebung/<int:uebung_id>/aktivieren", methods=["POST"])
@login_required
def uebung_aktivieren(uebung_id):
    db = get_db()
    db.execute("UPDATE uebungen SET status = 'abgeschlossen' WHERE status = 'aktiv'")
    db.execute("UPDATE uebungen SET status = 'aktiv', start_zeit = CURRENT_TIMESTAMP WHERE id = ?", (uebung_id,))
    db.commit()
    u = dict(db.execute("SELECT * FROM uebungen WHERE id = ?", (uebung_id,)).fetchone())
    socketio.emit("uebung_gestartet", {"id": u["id"], "name": u["name"]})
    return jsonify(u), 200


@app.route("/uebung/<int:uebung_id>/beenden", methods=["POST"])
@login_required
def uebung_beenden(uebung_id):
    db = get_db()
    db.execute(
        "UPDATE uebungen SET status = 'abgeschlossen', end_zeit = CURRENT_TIMESTAMP WHERE id = ?",
        (uebung_id,)
    )
    db.commit()
    socketio.emit("uebung_gestoppt", {"id": uebung_id})
    return "", 200


@app.route("/uebung/<int:uebung_id>", methods=["DELETE"])
@login_required
def delete_uebung(uebung_id):
    db = get_db()
    db.execute("UPDATE geraete SET uebung_id = NULL WHERE uebung_id = ?", (uebung_id,))
    db.execute("DELETE FROM uebungen WHERE id = ?", (uebung_id,))
    db.commit()
    socketio.emit("uebung_gestoppt", {"id": uebung_id})
    return "", 200


@app.route("/device/<int:geraet_id>/add_to_specific_uebung/<int:uebung_id>", methods=["POST"])
@login_required
def add_to_specific_uebung(geraet_id, uebung_id):
    db = get_db()
    db.execute("UPDATE geraete SET uebung_id = ? WHERE id = ?", (uebung_id, geraet_id))
    db.commit()
    geraet = dict(db.execute("SELECT * FROM geraete WHERE id = ?", (geraet_id,)).fetchone())
    socketio.emit("new_device", geraet)
    return jsonify(geraet), 200


# --------------------
# Start
# --------------------
socketio.start_background_task(messdaten_watcher)
print("Messdaten-Watcher gestartet")

if __name__ == "__main__":
    print("=" * 45)
    print("  Radsim läuft auf http://0.0.0.0:5000")
    print("  Warte auf Verbindungen... (Ctrl+C zum Beenden)")
    print("=" * 45)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)