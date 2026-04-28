"""
*****************************************************************************
* Copyright (c) 2026, All rights reserved
* Internal Use Only
*
* FILE:        mqtt_backend.py
* PROJECT:     Radsim
* MODULE:      MQTT-Bridge (Geräte ↔ Datenbank)
*
* Description:
*   Dieses Modul implementiert die MQTT-Bridge zwischen den
*   ESP32-Geräten (Strahlenquellen und Messgeräte) und der
*   radsim.db Datenbank. Es empfängt Messdaten von den
*   Messgeräten, speichert diese in der Datenbank und leitet
*   sie per HTTP an den Flask-Server weiter. Zusätzlich sendet
*   es Steuerbefehle an Quellen und Messgeräte.
*
*   Hauptfunktionen:
*   - Empfang und Speicherung von Messdaten der Messgeräte
*   - Senden von Strahlungsparametern an Strahlenquellen
*   - Senden von Offset- und Resetbefehlen an Messgeräte
*   - Synchronisation aller bekannten Geräte beim Serverstart
*
* Notes:
*   - Nur Messgeräte senden Daten an den Server
*   - Strahlenquellen empfangen ausschließlich Befehle
*   - Bei fehlendem Flask-Server übernimmt der Watcher
*     in app.py die Weiterleitung der Messdaten
*   - Rückwärtskompatibel: "cps"/"dosis" wird als Gamma gewertet
*
* MQTT Topics:
*   - Zähler  → Server : devices/data
*   - Server  → Zähler : devices/cmd/<MAC>
*   - Server  → Quelle : sources/cmd/<MAC>
*
* Dependencies:
*   - paho-mqtt
*   - Flask (HTTP-Push an /internal/measurement)
*   - SQLite3 / radsim.db
*
* Configuration:
*   - MQTT_BROKER          : IP/Hostname des Brokers (Standard: localhost)
*   - MQTT_PORT            : Port des Brokers (Standard: 1883)
*   - MQTT_TOPIC_ZAEHLER_IN: Topic für eingehende Messdaten
*   - DB_FILE              : Pfad zur SQLite-Datenbank
*
* Revision History:
*   2026-03-18  RW   Initiale Version
*
*****************************************************************************
"""

import json
import sqlite3
import os
import requests
import paho.mqtt.client as mqtt
from datetime import datetime

# ── Konfiguration ──────────────────────────────────────────────────────────
MQTT_BROKER           = "localhost"      # IP/Hostname des MQTT-Brokers
MQTT_PORT             = 1883
MQTT_TOPIC_ZAEHLER_IN = "devices/data"  # Zähler → Server (Messdaten)
# Server → Zähler:   devices/cmd/<mac>
# Server → Quelle:   sources/cmd/<mac>
DB_FILE               = "radsim.db"
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
    """
    Empfängt Messdaten vom Zähler. Erwartet alle drei Strahlungstypen:
      { "mac": "...", "cps_alpha": 1.2, "cps_beta": 0.5, "cps_gamma": 3.1,
        "dosis_alpha": 0.04, "dosis_beta": 0.01, "dosis": 0.12 }
    Rückwärtskompatibel: "cps"/"dosis" allein → wird als Gamma interpretiert.
    """
    try:
        data = json.loads(msg.payload.decode())
        mac  = data.get("mac", "").strip().upper()

        if not mac:
            print("[WARN] Nachricht ohne MAC ignoriert")
            return

        cps_alpha   = float(data.get("cps_alpha",   data.get("cps",   0.0)))
        cps_beta    = float(data.get("cps_beta",    0.0))
        cps_gamma   = float(data.get("cps_gamma",   data.get("cps",   0.0)))
        dosis_alpha = float(data.get("dosis_alpha", 0.0))
        dosis_beta  = float(data.get("dosis_beta",  0.0))
        dosis_gamma = float(data.get("total_gamma_dose", data.get("dosis", data.get("dosis_gamma", 0.0))))
        cps_gesamt  = round(cps_alpha + cps_beta + cps_gamma, 4)

        conn = get_db()
        c    = conn.cursor()

        geraet = geraet_by_mac(c, mac)

        if not geraet:
            uebung_id = aktive_uebung_id(c)
            c.execute(
                """INSERT INTO geraete
                   (name, typ, mac_adresse, status,
                    gesamtdosis, gesamtdosis_alpha, gesamtdosis_beta, uebung_id)
                   VALUES (?, 'messgeraet', ?, 'aktiv', ?, ?, ?, ?)""",
                (f"Zähler {mac[-8:]}", mac, dosis_gamma, dosis_alpha, dosis_beta, uebung_id)
            )
            conn.commit()
            geraet = geraet_by_mac(c, mac)
            print(f"[DB] Neuer Zähler registriert: {mac} (id={geraet['id']})")

        geraet_id = geraet["id"]
        uebung_id = geraet["uebung_id"]

        # Messung speichern (alle drei Typen)
        c.execute(
            """INSERT INTO messungen
               (geraet_id, uebung_id, cps, dosis,
                cps_alpha, cps_beta, cps_gamma,
                dosis_alpha, dosis_beta, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (geraet_id, uebung_id, cps_gesamt, dosis_gamma,
             cps_alpha, cps_beta, cps_gamma,
             dosis_alpha, dosis_beta,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

        # Gesamtdosis aller Typen + letzter_kontakt aktualisieren
        c.execute(
            """UPDATE geraete
               SET gesamtdosis       = ?,
                   gesamtdosis_alpha = ?,
                   gesamtdosis_beta  = ?,
                   letzter_kontakt   = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (dosis_gamma, dosis_alpha, dosis_beta, geraet_id)
        )

        if geraet["offset_reset"]:
            c.execute("UPDATE geraete SET offset_reset = 0 WHERE id = ?", (geraet_id,))

        conn.commit()
        conn.close()

        # Sofort per HTTP an Flask-SocketIO schicken (kein Watcher-Delay)
        try:
            requests.post("http://localhost:5000/internal/measurement", json={
                "id":                geraet_id,
                "cps":               cps_gesamt,
                "cps_alpha":         cps_alpha,
                "cps_beta":          cps_beta,
                "cps_gamma":         cps_gamma,
                "gesamtdosis":       dosis_gamma,
                "gesamtdosis_alpha": dosis_alpha,
                "gesamtdosis_beta":  dosis_beta,
                "akku":              float(akku) if akku is not None else None,
                "status":            str(status) if status is not None else None,
                "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }, timeout=1)
        except Exception:
            pass  # Flask nicht erreichbar – kein Problem, Watcher springt ein

        print(
            f"[ZÄHLER] {mac} → "
            f"α={cps_alpha} β={cps_beta} γ={cps_gamma} mSv/h | "
            f"dosisγ={dosis_gamma} mSv (id={geraet_id})"
        )

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
    print(f"[QUELLE→] {topic}  cps_alpha={alpha} cps_beta={beta} cps_gamma={gamma} status={status}")


def send_zaehler_cmd(client, mac: str,
                     offset_alpha: float = 0.0,
                     offset_beta:  float = 0.0,
                     offset_gamma: float = 0.0,
                     reset: bool   = False,
                     status: str   = "aktiv"):
    """
    Sendet Steuerparameter an einen Zähler.
    Topic: devices/cmd/<MAC>
    Payload:
        { "offset_alpha": 0.0, "offset_beta": 0.0, "offset_gamma": 0.0,
          "reset": false, "status": "aktiv" }
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
    print(f"[ZÄHLER→] {topic}  α={offset_alpha} β={offset_beta} γ={offset_gamma} reset={reset} status={status}")


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
    Sendet beim Server-Start die gespeicherten Offset-Werte an alle
    bekannten Messgeräte, damit der Zähler nach Neustart korrekt konfiguriert ist.
    """
    try:
        conn = get_db()
        zaehler = conn.execute(
            """SELECT mac_adresse, status,
                      offset_alpha, offset_beta, offset_gamma
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
                    reset        = False,
                    status       = z["status"] or "aktiv",
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