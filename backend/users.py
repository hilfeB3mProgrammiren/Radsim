from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

class User(UserMixin):
    def __init__(self, id, username, rolle):
        self.id       = id
        self.username = username
        self.rolle    = rolle

    def check_password(self, password):
        db = get_db()
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (self.id,)
        ).fetchone()
        return check_password_hash(row["password_hash"], password)

def get_user_by_username(username):
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row:
        return User(row["id"], row["username"], row["rolle"])
    return None

def get_user_by_id(user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row:
        return User(row["id"], row["username"], row["rolle"])
    return None