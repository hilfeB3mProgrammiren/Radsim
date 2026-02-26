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
    devices       = db.execute("SELECT * FROM geraete").fetchall()
    users         = db.execute("SELECT username FROM users").fetchall()
    aktive_uebung = db.execute("SELECT * FROM uebungen WHERE status = 'aktiv' LIMIT 1").fetchone()
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

@app.route("/device/<int:geraet_id>/reset_dosis", methods=["POST"])
@login_required
def reset_dosis(geraet_id):
    db = get_db()
    db.execute("UPDATE geraete SET gesamtdosis = 0.0 WHERE id = ?", (geraet_id,))
    db.commit()
    socketio.emit("device_updated", {"id": geraet_id, "gesamtdosis": 0.0})
    return "", 200

# --------------------
# Start
# --------------------
if __name__ == "__main__":
    socketio.start_background_task(messdaten_watcher)
    print("Messdaten-Watcher gestartet")

    socketio.run(app, host="0.0.0.0", port=5000, debug=True)