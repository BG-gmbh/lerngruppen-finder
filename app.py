import os
import sqlite3
from contextlib import closing
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), "users.db")
LEVELS = frozenset({"pro", "noob"})
CHAT_SUBJECTS = frozenset({"german", "math", "english"})
CHAT_SUBJECT_LABELS = {"german": "Deutsch", "math": "Mathe", "english": "Englisch"}
CHAT_LEVEL_COLUMN = {
    "german": "level_german",
    "math": "level_math",
    "english": "level_english",
}
CHAT_MAX_USERS = 5
CHAT_BODY_MAX = 500
app = Flask(__name__, static_folder="web", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-nur-lokal-bitte-aendern")


def chat_subject_key(raw):
    if not raw or raw not in CHAT_SUBJECTS:
        return None
    return raw


def parse_subject_levels(form):
    g = form.get("level_german")
    m = form.get("level_math")
    e = form.get("level_english")
    if g not in LEVELS or m not in LEVELS or e not in LEVELS:
        return None
    return g, m, e


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


def _ensure_subject_columns(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    for col in ("level_german", "level_math", "level_english"):
        if col not in names:
            db.execute(
                f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT 'noob'"
            )
    db.commit()


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
        _ensure_subject_columns(db)
        _ensure_chat_tables(db)


def _ensure_chat_tables(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_presence (
            subject TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            level TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (subject, user_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_messages_subject_id
        ON chat_messages (subject, id)
        """
    )
    db.commit()


def _prune_stale_chat(db, subject):
    db.execute(
        """
        DELETE FROM chat_presence
        WHERE subject = ? AND last_seen < datetime('now', '-2 minutes')
        """,
        (subject,),
    )


def _user_level_for_subject(db, user_id, subject):
    col = CHAT_LEVEL_COLUMN[subject]
    row = db.execute(
        f"SELECT {col} AS lvl FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return "noob"
    v = row["lvl"]
    return v if v in LEVELS else "noob"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            q = urlencode({"flash": "needlogin", "next": request.path})
            return redirect(f"/login.html?{q}")
        return view(*args, **kwargs)

    return wrapped


def login_required_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="auth"), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect("/dashboard.html")
    return send_from_directory(app.static_folder, "index.html")


@app.route("/dashboard.html")
@login_required
def dashboard_page():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/settings.html")
@login_required
def settings_page():
    return send_from_directory(app.static_folder, "settings.html")


@app.route("/chat.html")
@login_required
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")


@app.route("/api/chat/rooms", methods=["GET"])
@login_required_api
def chat_rooms():
    db = get_db()
    uid = session["user_id"]
    rooms = []
    for sub in ("german", "math", "english"):
        _prune_stale_chat(db, sub)
        members = db.execute(
            """
            SELECT username, level FROM chat_presence
            WHERE subject = ? ORDER BY username COLLATE NOCASE
            """,
            (sub,),
        ).fetchall()
        you = db.execute(
            "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
            (sub, uid),
        ).fetchone()
        you_in = you is not None
        count = len(members)
        full = count >= CHAT_MAX_USERS and not you_in
        rooms.append(
            {
                "subject": sub,
                "label": CHAT_SUBJECT_LABELS[sub],
                "count": count,
                "max": CHAT_MAX_USERS,
                "full": full,
                "you_in": you_in,
                "members": [
                    {"username": m["username"], "level": m["level"]} for m in members
                ],
            }
        )
    db.commit()
    return jsonify(rooms=rooms)


@app.route("/api/chat/join", methods=["POST"])
@login_required_api
def chat_join():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400

    db = get_db()
    uid = session["user_id"]
    uname = session["username"]
    lvl = _user_level_for_subject(db, uid, subject)

    _prune_stale_chat(db, subject)

    row = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if row:
        db.execute(
            """
            UPDATE chat_presence
            SET last_seen = datetime('now'), username = ?, level = ?
            WHERE subject = ? AND user_id = ?
            """,
            (uname, lvl, subject, uid),
        )
        db.commit()
        return jsonify(ok=True, you_in=True)

    n = db.execute(
        "SELECT COUNT(*) AS c FROM chat_presence WHERE subject = ?",
        (subject,),
    ).fetchone()["c"]
    if n >= CHAT_MAX_USERS:
        db.commit()
        return jsonify(error="full", max=CHAT_MAX_USERS), 409

    db.execute(
        """
        INSERT INTO chat_presence (subject, user_id, username, level, last_seen)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (subject, uid, uname, lvl),
    )
    db.commit()
    return jsonify(ok=True, you_in=True)


@app.route("/api/chat/leave", methods=["POST"])
@login_required_api
def chat_leave():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    db.execute(
        "DELETE FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, session["user_id"]),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/messages", methods=["GET"])
@login_required_api
def chat_messages():
    subject = chat_subject_key(request.args.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    try:
        since_id = int(request.args.get("since") or 0)
    except ValueError:
        since_id = 0

    db = get_db()
    uid = session["user_id"]
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403

    _prune_stale_chat(db, subject)
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403

    db.execute(
        """
        UPDATE chat_presence SET last_seen = datetime('now')
        WHERE subject = ? AND user_id = ?
        """,
        (subject, uid),
    )
    rows = db.execute(
        """
        SELECT id, user_id, username, body, created_at
        FROM chat_messages
        WHERE subject = ? AND id > ?
        ORDER BY id ASC
        LIMIT 200
        """,
        (subject, since_id),
    ).fetchall()
    db.commit()
    return jsonify(
        messages=[
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "username": r["username"],
                "body": r["body"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    )


@app.route("/api/chat/send", methods=["POST"])
@login_required_api
def chat_send():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    body = (data.get("body") or "").strip()
    if not subject:
        return jsonify(error="invalid_subject"), 400
    if not body:
        return jsonify(error="empty"), 400
    body = body[:CHAT_BODY_MAX]

    db = get_db()
    uid = session["user_id"]
    uname = session["username"]

    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403

    db.execute(
        """
        UPDATE chat_presence SET last_seen = datetime('now')
        WHERE subject = ? AND user_id = ?
        """,
        (subject, uid),
    )
    db.execute(
        """
        INSERT INTO chat_messages (subject, user_id, username, body)
        VALUES (?, ?, ?, ?)
        """,
        (subject, uid, uname, body),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect("/dashboard.html")

    if request.method == "GET":
        return redirect("/register.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password_confirm") or ""

    if not username or len(username) < 3:
        return redirect("/register.html?flash=shortuser")
    if len(password) < 6:
        return redirect("/register.html?flash=shortpass")
    if password != password2:
        return redirect("/register.html?flash=mismatch")

    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/register.html?flash=levels")

    lg, lm, le = levels
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO users (username, password_hash, level_german, level_math, level_english)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, generate_password_hash(password), lg, lm, le),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return redirect("/register.html?flash=taken")

    row = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    session.clear()
    session["user_id"] = row["id"]
    session["username"] = username
    return redirect("/dashboard.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect("/dashboard.html")

    if request.method == "GET":
        return redirect("/login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    db = get_db()
    row = db.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return redirect("/login.html?flash=invalid")

    session.clear()
    session["user_id"] = row["id"]
    session["username"] = username

    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("/dashboard.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/?flash=logout")


@app.route("/profile", methods=["POST"])
@login_required
def profile_update():
    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/settings.html?flash=levels")
    lg, lm, le = levels
    db = get_db()
    db.execute(
        """
        UPDATE users SET level_german = ?, level_math = ?, level_english = ?
        WHERE id = ?
        """,
        (lg, lm, le, session["user_id"]),
    )
    db.commit()
    return redirect("/settings.html?flash=saved")


@app.route("/api/me")
def api_me():
    if not session.get("user_id"):
        return jsonify({}), 401
    db = get_db()
    row = db.execute(
        """
        SELECT username, level_german, level_math, level_english
        FROM users WHERE id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    if row is None:
        return jsonify({}), 401
    return jsonify(
        user_id=session["user_id"],
        username=row["username"],
        level_german=row["level_german"],
        level_math=row["level_math"],
        level_english=row["level_english"],
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
