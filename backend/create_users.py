# create_user.py
from werkzeug.security import generate_password_hash
from database import get_db

def create_user(username, password, rolle="teilnehmer"):
    db = get_db()
    db.execute(
        "INSERT INTO users (username, password_hash, rolle) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), rolle)
    )
    db.commit()
    print(f"User '{username}' erstellt")

create_user("admin", "admin123", "admin")
create_user("uebungsleiter", "leiter123", "uebungsleiter")