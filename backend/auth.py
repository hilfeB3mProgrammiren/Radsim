"""
*****************************************************************************
* Copyright (c) 2026, All rights reserved
* Internal Use Only
*
* FILE:        auth.py
* PROJECT:     Radsim
* MODULE:      Authentication
*
* Description:
*   Dieses Modul implementiert die Benutzer-Authentifizierung
*   für das Radsim-System mittels Flask-Login.
*
*   Hauptfunktionen:
*   - Anzeige der Login-Seite mit vorhandenen Benutzern
*   - Verarbeitung von Login-Anfragen (Username/Passwort)
*   - Session-Handling über Flask-Login
*   - Logout und Weiterleitung zur Startseite
*
* Notes:
*   - Login erfolgt aktuell über Formular (POST /login)
*   - Passwortprüfung erfolgt über user.check_password()
*   - Keine Registrierung in diesem Modul enthalten
*   - Für interne Nutzung (kein öffentliches Auth-System)
*
* Dependencies:
*   - Flask
*   - Flask-Login
*   - users (User-Model + Passwortprüfung)
*   - database (DB-Zugriff)
*
* Configuration:
*   - Flask-Login muss im Hauptprogramm initialisiert sein
*   - login_manager.user_loader muss definiert sein
*
* Security:
*   - Passwörter müssen gehashed gespeichert sein
*   - Kein CSRF-Schutz implementiert (nur internes System)
*   - Für Produktion: HTTPS und Secure Cookies aktivieren
*
* Revision History:
*   2026-03-18  DH   Initiale Version
*
***********"""

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, logout_user
from users import get_user_by_username
from database import get_db

auth = Blueprint("auth", __name__)

# Login-Seite anzeigen
@auth.route("/login", methods=["GET"])
def login_page():
    db = get_db()
    users = db.execute("SELECT username FROM users").fetchall()
    return render_template("login.html", users=users)

# Login verarbeiten (AJAX)
@auth.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]

    user = get_user_by_username(username)

    if user and user.check_password(password):
        login_user(user)
        return "", 200

    return "Login fehlgeschlagen", 401

# Logout
@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))