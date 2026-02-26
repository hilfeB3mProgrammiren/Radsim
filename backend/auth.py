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