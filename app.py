import os
import secrets
import sqlite3
from contextlib import closing
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), "users.db")
LEVELS = frozenset({"pro", "medium", "noob"})
ROLES = frozenset({"admin", "user"})
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
        _ensure_role_column(db)
        _ensure_chat_tables(db)
        _ensure_invite_codes(db)


def _ensure_role_column(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    if "role" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
    db.commit()


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


def _ensure_invite_codes(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS invite_codes (
            code TEXT PRIMARY KEY,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            used_at TEXT,
            used_user_id INTEGER
        )
        """
    )
    db.commit()


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


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            q = urlencode({"flash": "needlogin", "next": request.path})
            return redirect(f"/login.html?{q}")
        if session.get("role") != "admin":
            return redirect("/dashboard.html?flash=admin_only")
        return view(*args, **kwargs)

    return wrapped


def admin_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="auth"), 401
        if session.get("role") != "admin":
            return jsonify(error="forbidden"), 403
        return view(*args, **kwargs)

    return wrapped


def _user_count(db):
    return int(db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])


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


@app.route("/register.html")
def register_page_blocked():
    return redirect("/login.html?flash=register_disabled")


@app.route("/setup.html")
def setup_page():
    db = get_db()
    if _user_count(db) > 0:
        return redirect("/login.html")
    return send_from_directory(app.static_folder, "setup.html")


@app.route("/setup", methods=["POST"])
def setup_create():
    db = get_db()
    if _user_count(db) > 0:
        return redirect("/login.html?flash=setup_done")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password_confirm") or ""

    if not username or len(username) < 3:
        return redirect("/setup.html?flash=shortuser")
    if len(password) < 6:
        return redirect("/setup.html?flash=shortpass")
    if password != password2:
        return redirect("/setup.html?flash=mismatch")

    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/setup.html?flash=levels")

    lg, lm, le = levels
    try:
        db.execute(
            """
            INSERT INTO users (username, password_hash, level_german, level_math, level_english, role)
            VALUES (?, ?, ?, ?, ?, 'admin')
            """,
            (username, generate_password_hash(password), lg, lm, le),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return redirect("/setup.html?flash=taken")

    row = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    session.clear()
    session["user_id"] = row["id"]
    session["username"] = username
    session["role"] = "admin"
    return redirect("/dashboard.html?flash=setup_done")


@app.route("/admin.html")
@admin_required
def admin_page():
    return send_from_directory(app.static_folder, "admin.html")


@app.route("/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password_confirm") or ""

    if not username or len(username) < 3:
        return redirect("/admin.html?flash=shortuser")
    if len(password) < 6:
        return redirect("/admin.html?flash=shortpass")
    if password != password2:
        return redirect("/admin.html?flash=mismatch")

    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/admin.html?flash=levels")

    role = "admin" if request.form.get("is_admin") == "1" else "user"
    if role not in ROLES:
        role = "user"

    lg, lm, le = levels
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO users (username, password_hash, level_german, level_math, level_english, role)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, generate_password_hash(password), lg, lm, le, role),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return redirect("/admin.html?flash=taken")

    return redirect("/admin.html?flash=user_created")


@app.route("/api/setup-status", methods=["GET"])
def setup_status():
    db = get_db()
    return jsonify(setup_needed=_user_count(db) == 0)


@app.route("/einladung.html")
def invite_page():
    if session.get("user_id"):
        return redirect("/dashboard.html")
    return send_from_directory(app.static_folder, "einladung.html")


@app.route("/einladung", methods=["POST"])
def invite_redeem():
    if session.get("user_id"):
        return redirect("/dashboard.html")

    code = (request.form.get("code") or "").strip()
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password_confirm") or ""

    if not code:
        return redirect("/einladung.html?flash=bad_invite")
    if not username or len(username) < 3:
        return redirect("/einladung.html?flash=shortuser")
    if len(password) < 6:
        return redirect("/einladung.html?flash=shortpass")
    if password != password2:
        return redirect("/einladung.html?flash=mismatch")

    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute(
            "SELECT code FROM invite_codes WHERE code = ? AND used_at IS NULL",
            (code,),
        ).fetchone()
        if not inv:
            db.rollback()
            return redirect("/einladung.html?flash=bad_invite")

        db.execute(
            """
            INSERT INTO users (username, password_hash, level_german, level_math, level_english, role)
            VALUES (?, ?, 'noob', 'noob', 'noob', 'user')
            """,
            (username, generate_password_hash(password)),
        )
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        cur = db.execute(
            """
            UPDATE invite_codes
            SET used_at = datetime('now'), used_user_id = ?
            WHERE code = ? AND used_at IS NULL
            """,
            (new_id, code),
        )
        if cur.rowcount != 1:
            db.rollback()
            return redirect("/einladung.html?flash=bad_invite")

        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return redirect("/einladung.html?flash=taken")

    session.clear()
    session["user_id"] = new_id
    session["username"] = username
    session["role"] = "user"
    return redirect("/dashboard.html?flash=redeem_ok")


@app.route("/api/admin/invite-codes", methods=["GET"])
@admin_api
def admin_invite_list():
    db = get_db()
    rows = db.execute(
        """
        SELECT code, created_at
        FROM invite_codes
        WHERE used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 100
        """
    ).fetchall()
    return jsonify(
        codes=[{"code": r["code"], "created_at": r["created_at"]} for r in rows]
    )


@app.route("/api/admin/invite-codes", methods=["POST"])
@admin_api
def admin_invite_create():
    db = get_db()
    uid = session["user_id"]
    for _ in range(12):
        code = secrets.token_hex(6)
        try:
            db.execute(
                "INSERT INTO invite_codes (code, created_by) VALUES (?, ?)",
                (code, uid),
            )
            db.commit()
            return jsonify(code=code, created_by=uid)
        except sqlite3.IntegrityError:
            db.rollback()
            continue
    return jsonify(error="generate"), 500


@app.route("/api/chat/rooms", methods=["GET"])
@login_required_api
def chat_rooms():
    db = get_db()
    uid = session["user_id"]
    rooms = []
    for sub in ("german", "math", "english"):
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
    return redirect("/login.html?flash=register_disabled")


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
        "SELECT id, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return redirect("/login.html?flash=invalid")

    session.clear()
    session["user_id"] = row["id"]
    session["username"] = username
    r = row["role"] if "role" in row.keys() else None
    session["role"] = r if r in ROLES else "user"

    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("/dashboard.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login.html?flash=logout")


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
        SELECT username, role, level_german, level_math, level_english
        FROM users WHERE id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    if row is None:
        return jsonify({}), 401
    r = row["role"] if "role" in row.keys() else None
    role = r if r in ROLES else "user"
    return jsonify(
        user_id=session["user_id"],
        username=row["username"],
        role=role,
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
