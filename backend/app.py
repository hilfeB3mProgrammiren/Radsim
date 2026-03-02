import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user
from auth import auth
from database import init_db, get_db
from users import get_user_by_id

init_db()

app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = "super-secret-key"

socketio = SocketIO(app, async_mode="eventlet")

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

app.register_blueprint(auth)

from flask_socketio import emit

@socketio.on("connect")
def on_connect():
    """Wenn ein Browser sich verbindet, aktuelle Messwerte sofort schicken"""
    db = get_db()
    messungen = db.execute("""
        SELECT m.id, m.geraet_id, m.cps, m.dosis
        FROM messungen m
        INNER JOIN (
            SELECT geraet_id, MAX(timestamp) as max_ts
            FROM messungen
            GROUP BY geraet_id
        ) latest ON m.geraet_id = latest.geraet_id AND m.timestamp = latest.max_ts
    """).fetchall()

    for m in messungen:
        emit("measurement", {
            "id":          m["geraet_id"],
            "cps":         m["cps"],
            "gesamtdosis": m["dosis"]
        })

# --------------------
# Messdaten Watcher
# --------------------
def messdaten_watcher():
    """Läuft im Hintergrund, prüft jede Sekunde auf neue Messwerte"""
    letzte_ids = {}  # { geraet_id: letzter bekannter messungs-id }

    while True:
        try:
            db = get_db()
            messungen = db.execute("""
                SELECT m.id, m.geraet_id, m.cps, m.dosis, m.timestamp
                FROM messungen m
                ORDER BY m.timestamp DESC
            """).fetchall()

            gesehen = set()
            for m in messungen:
                gid = m["geraet_id"]
                if gid in gesehen:
                    continue
                gesehen.add(gid)

                # Nur senden wenn sich der Wert geändert hat
                if letzte_ids.get(gid) != m["id"]:
                    letzte_ids[gid] = m["id"]
                    socketio.emit("measurement", {
                        "id":          gid,
                        "cps":         m["cps"],
                        "gesamtdosis": m["dosis"],
                        "timestamp":   str(m["timestamp"])
                    })

        except Exception as e:
            print("Watcher Fehler:", e)

        time.sleep(1)

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
    db.execute(
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
    neues_geraet = dict(db.execute("SELECT * FROM geraete ORDER BY id DESC LIMIT 1").fetchone())
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
    return jsonify(aktualisiert), 200

@app.route("/devices/ohne_uebung")
@login_required
def devices_ohne_uebung():
    typ = request.args.get("typ")
    db = get_db()
    if typ:
        rows = db.execute(
            "SELECT * FROM geraete WHERE uebung_id IS NULL AND typ = ?", (typ,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM geraete WHERE uebung_id IS NULL"
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/device/<int:geraet_id>/add_to_uebung", methods=["POST"])
@login_required
def add_to_uebung(geraet_id):
    db = get_db()
    uebung = db.execute(
        "SELECT id FROM uebungen WHERE status = 'aktiv' LIMIT 1"
    ).fetchone()
    uebung_id = uebung["id"] if uebung else None
    db.execute(
        "UPDATE geraete SET uebung_id = ? WHERE id = ?", (uebung_id, geraet_id)
    )
    db.commit()
    geraet = dict(db.execute("SELECT * FROM geraete WHERE id = ?", (geraet_id,)).fetchone())
    socketio.emit("new_device", geraet)
    return jsonify(geraet), 200

@app.route("/device/<int:geraet_id>", methods=["DELETE"])
@login_required
def delete_device(geraet_id):
    db = get_db()
    # Zuerst zugehörige Messungen und Konfigurationen löschen
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
    db.execute("UPDATE geraete SET gesamtdosis = 0.0 WHERE id = ?", (geraet_id,))
    db.commit()
    socketio.emit("device_updated", {"id": geraet_id, "gesamtdosis": 0.0})
    return "", 200


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
    # Falls neue Übung aktiv → alle anderen deaktivieren
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
    # Alle anderen beenden
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
    # Geräte aus Übung lösen (nicht löschen)
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
if __name__ == "__main__":
    socketio.start_background_task(messdaten_watcher)
    print("Messdaten-Watcher gestartet")

    socketio.run(app, host="0.0.0.0", port=5000, debug=True)