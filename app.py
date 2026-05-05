import os
import sqlite3
from contextlib import closing
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), "users.db")
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-nur-lokal-bitte-aendern")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DATABASE)) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        db.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Bitte zuerst einloggen.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password_confirm") or ""

        if not username or len(username) < 3:
            flash("Benutzername mindestens 3 Zeichen.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Passwort mindestens 6 Zeichen.", "error")
            return render_template("register.html")
        if password != password2:
            flash("Passwörter stimmen nicht überein.", "error")
            return render_template("register.html")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Dieser Benutzername ist schon vergeben.", "error")
            return render_template("register.html")

        row = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        session.clear()
        session["user_id"] = row["id"]
        session["username"] = username
        flash("Konto erstellt und eingeloggt.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        db = get_db()
        row = db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Benutzername oder Passwort falsch.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = row["id"]
        session["username"] = username
        flash("Willkommen zurück.", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Du bist ausgeloggt.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
