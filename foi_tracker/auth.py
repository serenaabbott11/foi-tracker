"""Authentication: User model, Flask-Login wiring, credential helpers.

Password hashing uses werkzeug.security (bundled with Flask — no extra dep).
"""
import sqlite3
from typing import Callable, Optional

from flask import has_request_context, jsonify, redirect, request, url_for
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin):
    """Minimal Flask-Login user. Loaded from the `users` table row."""

    def __init__(self, id: int, username: str, role: str, team_id: Optional[str]):
        self.id = id
        self.username = username
        self.role = role
        self.team_id = team_id

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(row["id"], row["username"], row["role"], row["team_id"])

    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_foi_officer(self) -> bool:
        return self.role == "foi_officer"


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "info"


def init_login(app, get_db: Callable[[], sqlite3.Connection]) -> None:
    """Bind the LoginManager to the app, register loader + unauthorized handler."""
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, username, role, team_id FROM users WHERE id = ?",
                (uid,),
            ).fetchone()
        finally:
            conn.close()
        return User.from_row(row) if row is not None else None

    @login_manager.unauthorized_handler
    def unauthorized():
        """Return JSON 401 for the API surface; redirect to /login for the SPA shell."""
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        return redirect(url_for("login", next=request.path))


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> Optional[User]:
    """Return a User if username+password check out, else None."""
    row = conn.execute(
        "SELECT id, username, password_hash, role, team_id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return User(row["id"], row["username"], row["role"], row["team_id"])


def hash_password(password: str) -> str:
    """One place to hash — keeps hashing algorithm choice consistent."""
    return generate_password_hash(password)


def current_actor() -> str:
    """Actor string for audit_log rows.

    - Authenticated web request → username
    - Anonymous web request (login page, healthz) → 'anonymous'
    - CLI / cron / no request context → 'system'
    """
    if not has_request_context():
        return "system"
    try:
        if current_user.is_authenticated:
            return current_user.username
    except Exception:
        # Login manager not wired, or user_loader failed — fall through.
        pass
    return "anonymous"
