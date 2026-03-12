# create_users.py
import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "radsim.db")

def create_user(username, password, rolle="teilnehmer"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO users (username, password_hash, rolle) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), rolle)
    )
    conn.commit()
    conn.close()
    print(f"User '{username}' erstellt")

create_user("admin", "admin123", "admin")
create_user("uebungsleiter", "leiter123", "uebungsleiter")
