import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(Path(__file__).resolve().parent / ".env")

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


def _normalize_appointment_datetime(raw):
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None


def chat_subject_key(raw):
    if not raw or raw not in CHAT_SUBJECTS:
        return None
    return raw


def parse_subject_levels(form):
    lv_g = form.get("level_german")
    lv_m = form.get("level_math")
    lv_e = form.get("level_english")
    if lv_g not in LEVELS or lv_m not in LEVELS or lv_e not in LEVELS:
        return None
    return lv_g, lv_m, lv_e


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
    if os.path.isfile(DATABASE) and os.path.getsize(DATABASE) == 0:
        try:
            os.remove(DATABASE)
        except OSError:
            pass
    if os.path.isfile(DATABASE):
        try:
            with closing(sqlite3.connect(DATABASE)) as probe:
                chk = probe.execute("PRAGMA quick_check").fetchone()
                if chk is None or str(chk[0]).lower() != "ok":
                    raise sqlite3.DatabaseError("quick_check failed")
        except sqlite3.Error:
            bad = DATABASE + ".broken"
            try:
                os.replace(DATABASE, bad)
            except OSError:
                try:
                    os.remove(DATABASE)
                except OSError:
                    pass

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
        _ensure_banned_column(db)
        _ensure_user_teacher_email_prefs(db)
        _ensure_chat_tables(db)
        _ensure_invite_codes(db)
        from shop import ensure_shop_table

        ensure_shop_table(db)
        _ensure_admin_subject_scores(db)


def _ensure_role_column(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    if "role" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
    db.commit()


def _ensure_banned_column(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    if "banned" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0"
        )
    if "banned_message" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN banned_message TEXT NOT NULL DEFAULT 'Dein Konto wurde gesperrt. Bitte den Admin kontaktieren.'"
        )
    db.commit()


def _ensure_user_teacher_email_prefs(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    if "contact_email" not in names:
        db.execute("ALTER TABLE users ADD COLUMN contact_email TEXT")
    if "notify_laden_email" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN notify_laden_email INTEGER NOT NULL DEFAULT 0"
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
        CREATE TABLE IF NOT EXISTS chat_appointments (
            subject TEXT PRIMARY KEY,
            appointment TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')), 
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            ended INTEGER NOT NULL DEFAULT 0,
            ended_at TEXT
        )
        """
    )
    cur = db.execute("PRAGMA table_info(chat_appointments)")
    appointment_cols = {row[1] for row in cur.fetchall()}
    if "ended" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN ended INTEGER NOT NULL DEFAULT 0"
        )
    if "ended_at" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN ended_at TEXT"
        )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_ratings (
            subject TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (subject, user_id)
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


def _ensure_admin_subject_scores(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_subject_scores (
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by INTEGER NOT NULL,
            PRIMARY KEY (user_id, subject)
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


def _chat_presence_pro_count(db, subject):
    return int(
        db.execute(
            "SELECT COUNT(*) AS c FROM chat_presence WHERE subject = ? AND level = 'pro'",
            (subject,),
        ).fetchone()["c"]
    )


def _chat_presence_non_pro_count(db, subject):
    return int(
        db.execute(
            "SELECT COUNT(*) AS c FROM chat_presence WHERE subject = ? AND level != 'pro'",
            (subject,),
        ).fetchone()["c"]
    )


def _purge_chat_non_pros_if_no_pro(db, subject):
    if _chat_presence_pro_count(db, subject) == 0:
        db.execute(
            "DELETE FROM chat_presence WHERE subject = ? AND level != 'pro'",
            (subject,),
        )


def _chat_may_use_room(db, user_id, subject):
    """Lesen/Schreiben: Pro im Fach oder mindestens ein Pro im Raum."""
    if _user_level_for_subject(db, user_id, subject) == "pro":
        return True
    return _chat_presence_pro_count(db, subject) >= 1


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            q = urlencode({"flash": "needlogin", "next": request.path})
            return redirect(f"/login.html?{q}")
        db = get_db()
        uid = session["user_id"]
        if is_user_banned(db, uid):
            msg = banned_message_for_user(db, uid)
            session.clear()
            q = urlencode({"flash": "banned", "flash_msg": msg})
            return redirect(f"/login.html?{q}")
        return view(*args, **kwargs)

    return wrapped


def login_required_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="auth"), 401
        db = get_db()
        if is_user_banned(db, session["user_id"]):
            msg = banned_message_for_user(db, session["user_id"])
            session.clear()
            return jsonify(error="banned", message=msg), 403
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            q = urlencode({"flash": "needlogin", "next": request.path})
            return redirect(f"/login.html?{q}")
        db = get_db()
        if is_user_banned(db, session["user_id"]):
            msg = banned_message_for_user(db, session["user_id"])
            session.clear()
            q = urlencode({"flash": "banned", "flash_msg": msg})
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


def is_user_banned(db, user_id):
    row = db.execute("SELECT banned FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["banned"])


def banned_message_for_user(db, user_id):
    row = db.execute(
        "SELECT banned_message FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    default_msg = "Dein Konto wurde gesperrt. Bitte den Admin kontaktieren."
    if row is None:
        return default_msg
    msg = (row["banned_message"] or "").strip()
    return msg or default_msg


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


@app.route("/api/admin/users", methods=["GET"])
@admin_api
def admin_user_list():
    db = get_db()
    rows = db.execute(
        "SELECT id, username, role, banned FROM users ORDER BY username COLLATE NOCASE"
    ).fetchall()
    return jsonify(
        users=[
            {
                "id": r["id"],
                "username": r["username"],
                "role": r["role"],
                "banned": bool(r["banned"]),
            }
            for r in rows
        ]
    )


@app.route("/api/admin/users/ban", methods=["POST"])
@admin_api
def admin_user_ban():
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="invalid_user"), 400
    ban = data.get("ban")
    if ban in (True, "true", "1", 1):
        banned = 1
    elif ban in (False, "false", "0", 0):
        banned = 0
    else:
        return jsonify(error="invalid_ban"), 400
    if user_id == session["user_id"]:
        return jsonify(error="self_ban"), 400
    db = get_db()
    row = db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return jsonify(error="not_found"), 404
    db.execute("UPDATE users SET banned = ? WHERE id = ?", (banned, user_id))
    db.commit()
    return jsonify(ok=True)


@app.route("/api/admin/delete_message/<int:message_id>", methods=["DELETE"])
@admin_api
def admin_delete_message(message_id):
    db = get_db()
    row = db.execute("SELECT id FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
    if not row:
        return jsonify(error="message_not_found"), 404
    db.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    db.commit()
    return jsonify(success=True)


@app.route("/api/admin/chats", methods=["GET"])
@admin_api
def admin_get_chats():
    db = get_db()
    result = []
    for subject in CHAT_SUBJECTS:
        count = db.execute(
            "SELECT COUNT(*) as c FROM chat_messages WHERE subject = ?",
            (subject,),
        ).fetchone()["c"]
        rating_n = db.execute(
            "SELECT COUNT(*) as c FROM chat_ratings WHERE subject = ?",
            (subject,),
        ).fetchone()["c"]
        result.append(
            {
                "subject": subject,
                "label": CHAT_SUBJECT_LABELS[subject],
                "message_count": int(count),
                "rating_count": int(rating_n),
            }
        )
    return jsonify(chats=result)


@app.route("/api/admin/ratings", methods=["GET"])
@admin_api
def admin_list_ratings():
    db = get_db()
    rows = db.execute(
        """
        SELECT r.subject AS subject, r.user_id AS user_id, u.username AS username,
               r.rating AS rating, r.comment AS comment, r.created_at AS created_at,
               s.points AS admin_points, s.note AS admin_note
        FROM chat_ratings r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN admin_subject_scores s
          ON s.user_id = r.user_id AND s.subject = r.subject
        ORDER BY r.created_at DESC
        LIMIT 500
        """
    ).fetchall()
    db.commit()
    return jsonify(
        ratings=[
            {
                "subject": row["subject"],
                "subject_label": CHAT_SUBJECT_LABELS.get(
                    row["subject"], row["subject"]
                ),
                "user_id": row["user_id"],
                "username": row["username"],
                "rating": int(row["rating"]),
                "comment": (row["comment"] or "").strip(),
                "created_at": row["created_at"],
                "admin_points": int(row["admin_points"] or 0),
                "admin_note": row["admin_note"] or "",
            }
            for row in rows
        ]
    )


@app.route("/api/admin/subject-score", methods=["PUT"])
@admin_api
def admin_put_subject_score():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify(error="invalid_user"), 400
    try:
        points = int(data.get("points", 0))
    except (TypeError, ValueError):
        return jsonify(error="invalid_points"), 400
    if points < -10000 or points > 10000:
        return jsonify(error="invalid_points"), 400
    note = (data.get("note") or "").strip()
    if len(note) > 500:
        return jsonify(error="invalid_note"), 400

    db = get_db()
    urow = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not urow:
        db.commit()
        return jsonify(error="not_found"), 404
    admin_id = session["user_id"]
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    cur = db.execute(
        """
        UPDATE admin_subject_scores
        SET points = ?, note = ?, updated_at = ?, updated_by = ?
        WHERE user_id = ? AND subject = ?
        """,
        (points, note or None, now, admin_id, user_id, subject),
    )
    if cur.rowcount == 0:
        db.execute(
            """
            INSERT INTO admin_subject_scores (user_id, subject, points, note, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, subject, points, note or None, now, admin_id),
        )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/admin/delete_chat/<subject>", methods=["DELETE"])
@admin_api
def admin_delete_chat(subject):
    if subject not in CHAT_SUBJECTS:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    db.execute("DELETE FROM chat_messages WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_appointments WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_ratings WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_presence WHERE subject = ?", (subject,))
    db.commit()
    return jsonify(success=True)


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
        appointment_row = db.execute(
            "SELECT appointment FROM chat_appointments WHERE subject = ?",
            (sub,),
        ).fetchone()
        you_in = you is not None
        count_total = len(members)
        non_pro_n = sum(1 for m in members if m["level"] != "pro")
        pro_n = sum(1 for m in members if m["level"] == "pro")
        has_pro = pro_n >= 1
        viewer_lv = _user_level_for_subject(db, uid, sub)
        if viewer_lv == "pro":
            can_join = True
            join_block = None
            full = False
        else:
            slot_free = non_pro_n < CHAT_MAX_USERS
            can_join = (you_in or (has_pro and slot_free))
            if you_in:
                join_block = None
            elif not has_pro:
                join_block = "need_pro"
            elif not slot_free:
                join_block = "full"
            else:
                join_block = None
            full = not can_join
        rooms.append(
            {
                "subject": sub,
                "label": CHAT_SUBJECT_LABELS[sub],
                "count": count_total,
                "count_non_pro": non_pro_n,
                "count_pro": pro_n,
                "has_pro": has_pro,
                "max": CHAT_MAX_USERS,
                "full": full,
                "can_join": can_join,
                "join_block": join_block,
                "you_in": you_in,
                "appointment": appointment_row["appointment"] if appointment_row else None,
                "members": [
                    {"username": m["username"], "level": m["level"]} for m in members
                ],
            }
        )
    db.commit()
    return jsonify(rooms=rooms)


@app.route("/api/chat/appointment", methods=["GET"])
@login_required_api
def chat_appointment_get():
    subject = chat_subject_key(request.args.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    uid = session["user_id"]
    row = db.execute(
        "SELECT appointment, created_at, ended, ended_at FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if not row:
        db.commit()
        return jsonify(appointment=None)

    your_rating = db.execute(
        "SELECT rating, comment FROM chat_ratings WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    is_pro = _user_level_for_subject(db, uid, subject) == "pro"
    rating_count = None
    rating_avg = None
    ratings = None
    if is_pro:
        rating_stats = db.execute(
            "SELECT COUNT(*) AS count, AVG(rating) AS avg FROM chat_ratings WHERE subject = ?",
            (subject,),
        ).fetchone()
        rating_count = int(rating_stats["count"])
        rating_avg = (
            float(rating_stats["avg"]) if rating_stats["avg"] is not None else None
        )
        rows = db.execute(
            """
            SELECT u.username AS username, r.rating AS rating, r.comment AS comment
            FROM chat_ratings r
            JOIN users u ON u.id = r.user_id
            WHERE r.subject = ?
            ORDER BY r.created_at ASC
            """,
            (subject,),
        ).fetchall()
        ratings = [
            {
                "username": r["username"],
                "rating": int(r["rating"]),
                "comment": (r["comment"] or "").strip(),
            }
            for r in rows
        ]
    db.commit()
    return jsonify(
        appointment=row["appointment"],
        created_at=row["created_at"],
        ended=bool(row["ended"]),
        ended_at=row["ended_at"],
        your_rating={
            "rating": your_rating["rating"],
            "comment": your_rating["comment"],
        } if your_rating else None,
        rating_count=rating_count,
        rating_avg=rating_avg,
        ratings=ratings,
    )


@app.route("/api/chat/appointment", methods=["POST"])
@login_required_api
def chat_appointment_post():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    appointment = _normalize_appointment_datetime(data.get("appointment"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    if data.get("appointment") is None or not str(data.get("appointment")).strip():
        return jsonify(error="empty"), 400
    if not appointment:
        return jsonify(error="invalid_datetime"), 400

    db = get_db()
    uid = session["user_id"]
    level = _user_level_for_subject(db, uid, subject)
    if level != "pro":
        return jsonify(error="permission"), 403

    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    existing = db.execute(
        "SELECT 1 FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if existing:
        db.execute(
            """
            UPDATE chat_appointments
            SET appointment = ?, created_by = ?, updated_at = ?
            WHERE subject = ?
            """,
            (appointment, uid, now, subject),
        )
    else:
        db.execute(
            """
            INSERT INTO chat_appointments (subject, appointment, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (subject, appointment, uid, now, now),
        )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/appointment/end", methods=["POST"])
@login_required_api
def chat_appointment_end():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    uid = session["user_id"]
    level = _user_level_for_subject(db, uid, subject)
    if level != "pro":
        return jsonify(error="permission"), 403
    row = db.execute(
        "SELECT ended FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if not row:
        db.commit()
        return jsonify(error="no_appointment"), 400
    if row["ended"]:
        db.commit()
        return jsonify(ok=True)
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    db.execute(
        "UPDATE chat_appointments SET ended = 1, ended_at = ?, updated_at = ? WHERE subject = ?",
        (now, now, subject),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/appointment/rate", methods=["POST"])
@login_required_api
def chat_appointment_rate():
    data = request.get_json(silent=True) or {}
    subject = chat_subject_key(data.get("subject"))
    if not subject:
        return jsonify(error="invalid_subject"), 400
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify(error="invalid_rating"), 400
    if rating < 1 or rating > 5:
        return jsonify(error="invalid_rating"), 400
    comment = (data.get("comment") or "").strip()
    if rating < 4 and not comment:
        return jsonify(error="need_comment"), 400
    db = get_db()
    uid = session["user_id"]
    appointment = db.execute(
        "SELECT ended FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if not appointment or not appointment["ended"]:
        db.commit()
        return jsonify(error="not_ended"), 400
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        db.commit()
        return jsonify(error="not_in_room"), 403
    existing = db.execute(
        "SELECT 1 FROM chat_ratings WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    if existing:
        db.execute(
            "UPDATE chat_ratings SET rating = ?, comment = ?, created_at = ? WHERE subject = ? AND user_id = ?",
            (rating, comment, now, subject, uid),
        )
    else:
        db.execute(
            "INSERT INTO chat_ratings (subject, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (subject, uid, rating, comment, now),
        )
    db.commit()
    return jsonify(ok=True)


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

    if lvl != "pro":
        if _chat_presence_pro_count(db, subject) < 1:
            db.commit()
            return jsonify(error="need_pro"), 403
        if _chat_presence_non_pro_count(db, subject) >= CHAT_MAX_USERS:
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
    uid = session["user_id"]
    prow = db.execute(
        "SELECT level FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    was_pro = prow is not None and prow["level"] == "pro"
    db.execute(
        "DELETE FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    )
    if was_pro:
        _purge_chat_non_pros_if_no_pro(db, subject)
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
    if not _chat_may_use_room(db, uid, subject):
        db.execute(
            "DELETE FROM chat_presence WHERE subject = ? AND user_id = ?",
            (subject, uid),
        )
        db.commit()
        return jsonify(error="need_pro"), 403

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
    if not _chat_may_use_room(db, uid, subject):
        db.execute(
            "DELETE FROM chat_presence WHERE subject = ? AND user_id = ?",
            (subject, uid),
        )
        db.commit()
        return jsonify(error="need_pro"), 403

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
        "SELECT id, password_hash, role, banned FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return redirect("/login.html?flash=invalid")
    if row["banned"]:
        msg = banned_message_for_user(db, row["id"])
        q = urlencode({"flash": "banned", "flash_msg": msg})
        return redirect(f"/login.html?{q}")

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


def _valid_contact_email(raw):
    s = (raw or "").strip()
    if not s:
        return None
    if len(s) > 254 or "@" not in s or " " in s:
        return None
    return s


@app.route("/profile", methods=["POST"])
@login_required
def profile_update():
    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/settings.html?flash=levels")
    lg, lm, le = levels
    raw_mail = (request.form.get("contact_email") or "").strip()
    contact_email = _valid_contact_email(raw_mail)
    if raw_mail and contact_email is None:
        return redirect("/settings.html?flash=bad_contact_email")
    want_notify = request.form.get("notify_laden_email") == "1"
    if want_notify and not contact_email:
        return redirect("/settings.html?flash=notify_no_email")
    notify_val = 1 if (want_notify and contact_email) else 0
    email_val = contact_email

    cur_pwd = request.form.get("current_password") or ""
    new_pwd = request.form.get("new_password") or ""
    new_pwd2 = request.form.get("new_password_confirm") or ""
    pwd_change = bool(cur_pwd or new_pwd or new_pwd2)
    if pwd_change:
        if not cur_pwd or not new_pwd or not new_pwd2:
            return redirect("/settings.html?flash=pwd_incomplete")
        if len(new_pwd) < 6:
            return redirect("/settings.html?flash=shortpass")
        if new_pwd != new_pwd2:
            return redirect("/settings.html?flash=mismatch")

    db = get_db()
    uid = session["user_id"]
    if pwd_change:
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], cur_pwd):
            return redirect("/settings.html?flash=pwd_current_wrong")
        new_hash = generate_password_hash(new_pwd)
        db.execute(
            """
            UPDATE users SET level_german = ?, level_math = ?, level_english = ?,
                contact_email = ?, notify_laden_email = ?,
                password_hash = ?
            WHERE id = ?
            """,
            (lg, lm, le, email_val, notify_val, new_hash, uid),
        )
    else:
        db.execute(
            """
            UPDATE users SET level_german = ?, level_math = ?, level_english = ?,
                contact_email = ?, notify_laden_email = ?
            WHERE id = ?
            """,
            (lg, lm, le, email_val, notify_val, uid),
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
        SELECT username, role, level_german, level_math, level_english,
               contact_email, notify_laden_email
        FROM users WHERE id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    if row is None:
        return jsonify({}), 401
    r = row["role"] if "role" in row.keys() else None
    role = r if r in ROLES else "user"
    ce = row["contact_email"] if "contact_email" in row.keys() else None
    nl = row["notify_laden_email"] if "notify_laden_email" in row.keys() else 0
    return jsonify(
        user_id=session["user_id"],
        username=row["username"],
        role=role,
        level_german=row["level_german"],
        level_math=row["level_math"],
        level_english=row["level_english"],
        contact_email=ce or "",
        notify_laden_email=bool(nl),
    )


from shop import register_shop_routes

register_shop_routes(app, get_db, admin_api, login_required, login_required_api)

with app.app_context():
    init_db()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
