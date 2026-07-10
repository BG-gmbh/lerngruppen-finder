import os
import secrets
try:
    import sqlite3
except ImportError:
    from pysqlite3 import dbapi2 as sqlite3
import ipaddress
import re
from contextlib import closing
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from mailer import send_smtp_mail, smtp_status

load_dotenv(Path(__file__).resolve().parent / ".env")

default_database_path = os.path.join(os.path.dirname(__file__), "users.db")
if os.environ.get("DATABASE_PATH"):
    DATABASE = os.environ.get("DATABASE_PATH")
elif os.access(os.path.dirname(default_database_path) or ".", os.W_OK):
    DATABASE = default_database_path
else:
    DATABASE = "/tmp/lerngruppen-finder/users.db"
LEVELS = frozenset({"pro", "medium", "noob"})
ROLES = frozenset({"dev", "admin", "teacher", "user"})
ROLE_RANK = {"user": 0, "teacher": 1, "admin": 2, "dev": 3}
CHAT_SUBJECT_ORDER = ("german", "math", "english", "biology", "pgw", "spanish", "art")
CHAT_SUBJECTS = frozenset(CHAT_SUBJECT_ORDER)
CHAT_SUBJECT_LABELS = {
    "german": "Deutsch",
    "math": "Mathe",
    "english": "Englisch",
    "biology": "Biologie",
    "pgw": "PGW",
    "spanish": "Spanisch",
    "art": "Kunst",
}
CHAT_LEVEL_COLUMN = {subject: f"level_{subject}" for subject in CHAT_SUBJECT_ORDER}
CHAT_VERIFIED_COLUMN = {
    subject: f"pro_verified_{subject}" for subject in CHAT_SUBJECT_ORDER
}
CHAT_MAX_USERS = 5
CHAT_BODY_MAX = 500
CHAT_ROOM_SUFFIX_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
AVATAR_UPLOAD_DIR = Path(__file__).resolve().parent / "flutter_app" / "docs" / "uploads" / "avatars"
AVATAR_ALLOWED_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
AVATAR_MAX_BYTES = 2 * 1024 * 1024
STATIC_DIR = Path(__file__).resolve().parent / "flutter_app" / "docs"
app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-nur-lokal-bitte-aendern")
ALLOWED_ORIGINS = frozenset(
    origin.strip().rstrip("/")
    for origin in os.environ.get("FLASK_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)


@app.after_request
def add_flutter_cors_headers(response):
    origin = request.headers.get("Origin", "")
    normalized_origin = origin.rstrip("/")
    allow_origin = (
        _is_local_origin(origin)
        or normalized_origin in ALLOWED_ORIGINS
    )
    if allow_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
    return response


def _is_local_origin(origin):
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


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


def _normalize_appointment_location(raw):
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) > 120:
        return None
    return text


def _normalize_school_name(raw):
    text = " ".join((raw or "").strip().split())
    if len(text) > 120:
        return None
    return text


def chat_subject_key(raw):
    if not raw or raw not in CHAT_SUBJECTS:
        return None
    return raw


def chat_room_key(raw):
    value = (raw or "").strip().lower()
    if not value:
        return None, None
    if ":" not in value:
        subject = chat_subject_key(value)
        if not subject:
            return None, None
        return subject, subject
    subject, suffix = value.split(":", 1)
    subject = chat_subject_key(subject)
    if not subject:
        return None, None
    suffix = suffix.strip()
    if not CHAT_ROOM_SUFFIX_RE.fullmatch(suffix):
        return None, None
    return f"{subject}:{suffix}", subject


def chat_room_label(room_key):
    room_key = (room_key or "").strip().lower()
    room, subject = chat_room_key(room_key)
    if not room or not subject:
        return room_key or "Chat"
    base = CHAT_SUBJECT_LABELS.get(subject, subject)
    if room == subject:
        return base
    return f"{base} · {room.split(':', 1)[1]}"


def parse_subject_levels(form):
    levels = tuple(form.get(CHAT_LEVEL_COLUMN[subject]) for subject in CHAT_SUBJECT_ORDER)
    if any(level not in LEVELS for level in levels):
        return None
    return levels


def normalize_class_name(raw):
    class_name = "".join((raw or "").strip().split()).lower()
    if len(class_name) > 20:
        return None
    return class_name


def class_name_for_role(role, raw):
    if role in ("admin", "dev"):
        return ""
    return normalize_class_name(raw)


def class_grade_number(class_name):
    digits = []
    for ch in (class_name or "").strip():
        if ch.isdigit():
            digits.append(ch)
        elif digits:
            break
    if not digits:
        return None
    try:
        return int("".join(digits))
    except ValueError:
        return None


def user_may_access_subject(db, user_id, subject):
    if subject != "pgw":
        return True
    row = db.execute(
        "SELECT class_name, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    role = row["role"] if row["role"] in ROLES else "user"
    if role in ("teacher", "admin", "dev"):
        return True
    grade = class_grade_number(row["class_name"])
    return grade is not None and grade >= 9


def next_pro_verification_values(row, levels):
    next_values = []
    for subject, level in zip(CHAT_SUBJECT_ORDER, levels):
        level_col = CHAT_LEVEL_COLUMN[subject]
        verified_col = CHAT_VERIFIED_COLUMN[subject]
        if level != "pro":
            next_values.append(0)
        elif row is not None and row[level_col] == "pro" and row[verified_col]:
            next_values.append(1)
        else:
            next_values.append(0)
    return tuple(next_values)


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


def _ensure_database_path():
    db_path = Path(DATABASE)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.touch()
    return db_path


def _ensure_subject_columns(db):
    cur = db.execute("PRAGMA table_info(users)")
    names = {row[1] for row in cur.fetchall()}
    for col in CHAT_LEVEL_COLUMN.values():
        if col not in names:
            try:
                db.execute(
                    f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT 'noob'"
                )
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
    for subject, col in CHAT_VERIFIED_COLUMN.items():
        if col not in names:
            try:
                db.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        db.execute(
            f"UPDATE users SET {col} = 1 WHERE {CHAT_LEVEL_COLUMN[subject]} = 'pro' AND ({col} IS NULL OR {col} = 0)"
        )
    db.commit()


def init_db():
    _ensure_database_path()
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
        db.row_factory = sqlite3.Row
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
        _ensure_schools(db)
        _ensure_chat_tables(db)
        _ensure_learning_places(db)
        _ensure_invite_codes(db)
        _ensure_app_settings(db)
        _ensure_api_tokens(db)
        from shop import ensure_shop_table

        ensure_shop_table(db)
        _ensure_schools(db)
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
    if "school" not in names:
        db.execute("ALTER TABLE users ADD COLUMN school TEXT NOT NULL DEFAULT ''")
    if "class_name" not in names:
        db.execute("ALTER TABLE users ADD COLUMN class_name TEXT NOT NULL DEFAULT ''")
    if "contact_email" not in names:
        db.execute("ALTER TABLE users ADD COLUMN contact_email TEXT")
    if "notify_laden_email" not in names:
        db.execute(
            "ALTER TABLE users ADD COLUMN notify_laden_email INTEGER NOT NULL DEFAULT 0"
        )
    if "avatar_url" not in names:
        db.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT NOT NULL DEFAULT ''")
    if "iserv_email" not in names:
        db.execute("ALTER TABLE users ADD COLUMN iserv_email TEXT NOT NULL DEFAULT ''")
    db.execute("UPDATE users SET class_name = lower(replace(trim(class_name), ' ', ''))")
    db.execute("UPDATE users SET class_name = '' WHERE role IN ('admin', 'dev')")
    db.commit()


def _ensure_schools(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schools (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    for table in ("users", "invite_codes", "shop_items", "teacher_contacts"):
        try:
            rows = db.execute(
                f"SELECT DISTINCT school FROM {table} WHERE TRIM(school) != ''"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            school = (row["school"] or "").strip()
            if school:
                db.execute(
                    "INSERT OR IGNORE INTO schools (name) VALUES (?)",
                    (school,),
                )
    db.commit()


def _ensure_learning_places(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            school TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            address TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learning_places_school_created
        ON learning_places (school, created_at)
        """
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
            location TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')), 
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            started INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            ended INTEGER NOT NULL DEFAULT 0,
            ended_at TEXT
        )
        """
    )
    cur = db.execute("PRAGMA table_info(chat_appointments)")
    appointment_cols = {row[1] for row in cur.fetchall()}
    if "location" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN location TEXT NOT NULL DEFAULT ''"
        )
    if "ended" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN ended INTEGER NOT NULL DEFAULT 0"
        )
    if "ended_at" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN ended_at TEXT"
        )
    if "started" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN started INTEGER NOT NULL DEFAULT 0"
        )
    if "started_at" not in appointment_cols:
        db.execute(
            "ALTER TABLE chat_appointments ADD COLUMN started_at TEXT"
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
        CREATE TABLE IF NOT EXISTS chat_message_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            reported_user_id INTEGER NOT NULL,
            reported_username TEXT NOT NULL,
            reported_school TEXT NOT NULL DEFAULT '',
            reported_class_name TEXT NOT NULL DEFAULT '',
            reported_role TEXT NOT NULL DEFAULT 'user',
            reporter_user_id INTEGER NOT NULL,
            reporter_username TEXT NOT NULL,
            body TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT,
            resolved_by INTEGER,
            UNIQUE(message_id, reporter_user_id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_messages_subject_id
        ON chat_messages (subject, id)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chat_reports_subject_created
        ON chat_message_reports (subject, created_at)
        """
    )
    db.commit()


def _ensure_invite_codes(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS invite_codes (
            code TEXT PRIMARY KEY,
            created_by INTEGER NOT NULL,
            school TEXT NOT NULL DEFAULT '',
            class_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',
            created_by_role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            used_at TEXT,
            used_user_id INTEGER
        )
        """
    )
    cur = db.execute("PRAGMA table_info(invite_codes)")
    names = {row[1] for row in cur.fetchall()}
    if "school" not in names:
        db.execute("ALTER TABLE invite_codes ADD COLUMN school TEXT NOT NULL DEFAULT ''")
    if "class_name" not in names:
        db.execute("ALTER TABLE invite_codes ADD COLUMN class_name TEXT NOT NULL DEFAULT ''")
    if "role" not in names:
        db.execute("ALTER TABLE invite_codes ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "created_by_role" not in names:
        db.execute("ALTER TABLE invite_codes ADD COLUMN created_by_role TEXT NOT NULL DEFAULT 'user'")
        db.execute(
            """
            UPDATE invite_codes
            SET created_by_role = COALESCE(
                (SELECT role FROM users WHERE users.id = invite_codes.created_by),
                'user'
            )
            """
        )
    db.execute("UPDATE invite_codes SET class_name = lower(replace(trim(class_name), ' ', ''))")
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


def _ensure_api_tokens(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id
        ON api_tokens (user_id)
        """
    )
    db.commit()


def _ensure_app_settings(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.commit()


def app_setting(db, key, default=""):
    row = db.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return default
    return row["value"] or default


def set_app_setting(db, key, value):
    db.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def int_app_setting(db, key, default=0):
    raw = app_setting(db, key, str(default))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def school_license_limit_key(school):
    school = (school or "").strip()
    return f"school_license_limit::{school}" if school else "school_license_limit"


def school_license_limit(db, school):
    return int_app_setting(db, school_license_limit_key(school), 0)


def set_school_license_limit(db, school, limit):
    set_app_setting(db, school_license_limit_key(school), str(max(0, int(limit))))


def invite_license_usage_for_school(db, school):
    school = (school or "").strip()
    user_row = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM users
        WHERE school = ?
        """,
        (school,),
    ).fetchone()
    code_row = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM invite_codes
        WHERE used_at IS NULL AND school = ?
        """,
        (school,),
    ).fetchone()
    users = int(user_row["c"] or 0) if user_row else 0
    codes = int(code_row["c"] or 0) if code_row else 0
    return {
        "users": users,
        "codes": codes,
        "active": users + codes,
    }


def invite_code_quota_payload(db, school):
    school = (school or "").strip()
    limit = school_license_limit(db, school)
    usage = invite_license_usage_for_school(db, school)
    active = usage["active"]
    return {
        "school": school,
        "limit": limit,
        "users": usage["users"],
        "codes": usage["codes"],
        "active": active,
        "remaining": None if limit <= 0 else max(0, limit - active),
    }


def school_license_has_free_slot(db, school):
    quota = invite_code_quota_payload(db, school)
    return quota["limit"] <= 0 or quota["active"] < quota["limit"]


def school_logo_key(school):
    school = (school or "").strip()
    return f"school_logo_url::{school}" if school else "school_logo_url"


def school_logo_url_for(db, school):
    school = (school or "").strip()
    if school:
        value = app_setting(db, school_logo_key(school))
        if value:
            return value
    return app_setting(db, "school_logo_url")


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


def _user_is_verified_pro_for_subject(db, user_id, subject):
    level_col = CHAT_LEVEL_COLUMN[subject]
    verified_col = CHAT_VERIFIED_COLUMN[subject]
    row = db.execute(
        f"SELECT {level_col} AS lvl, {verified_col} AS verified, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    return row["lvl"] == "pro" and (
        bool(row["verified"]) or row["role"] in ("teacher", "admin", "dev")
    )


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


def _clear_chat_messages_if_room_empty(db, subject):
    row = db.execute(
        "SELECT COUNT(*) AS c FROM chat_presence WHERE subject = ?",
        (subject,),
    ).fetchone()
    if row and int(row["c"]) == 0:
        db.execute("DELETE FROM chat_messages WHERE subject = ?", (subject,))


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
        if not _load_api_auth_context():
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
        if session.get("role") not in ("teacher", "admin", "dev"):
            return redirect("/dashboard.html?flash=admin_only")
        return view(*args, **kwargs)

    return wrapped


def admin_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _load_api_auth_context():
            return jsonify(error="auth"), 401
        if session.get("role") not in ("teacher", "admin", "dev"):
            return jsonify(error="forbidden"), 403
        return view(*args, **kwargs)

    return wrapped


def _load_api_auth_context():
    if session.get("user_id"):
        return True
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(None, 1)[1].strip()
    if not token:
        return False
    db = get_db()
    row = db.execute(
        """
        SELECT u.id AS id, u.username AS username, u.role AS role, u.school AS school
        FROM api_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = ?
        """,
        (token,),
    ).fetchone()
    if row is None:
        return False
    role = row["role"] if row["role"] in ROLES else "user"
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["role"] = role
    session["school"] = row["school"] or ""
    g.api_token = token
    return True


def is_dev_session():
    return session.get("role") == "dev"


def role_rank(role):
    return ROLE_RANK.get(role if role in ROLES else "user", 0)


def hidden_roles_for_session():
    if is_dev_session():
        return []
    current_rank = role_rank(session.get("role"))
    return [role for role, rank in ROLE_RANK.items() if rank >= current_rank]


def admin_school(db):
    if "school" in session:
        return session.get("school") or ""
    uid = session.get("user_id")
    if not uid:
        return ""
    row = db.execute("SELECT school FROM users WHERE id = ?", (uid,)).fetchone()
    school = (row["school"] if row else "") or ""
    session["school"] = school
    return school


def scoped_user_where(db, table_alias="u"):
    if is_dev_session():
        return "", ()
    hidden_roles = hidden_roles_for_session()
    placeholders = ", ".join("?" for _ in hidden_roles)
    
    current_role = session.get("role", "user")
    conditions = f"{table_alias}.school = ? AND {table_alias}.role NOT IN ({placeholders})"
    params = [admin_school(db), *hidden_roles]
    
    if current_role == "teacher":
        teacher_class = teacher_class_for_session(db)
        if not teacher_class:
            return f" WHERE 1 = 0", ()
        conditions += f" AND {table_alias}.class_name = ?"
        params.append(teacher_class)
    
    return f" WHERE {conditions}", tuple(params)


def can_access_user(db, user_id):
    row = db.execute(
        "SELECT role, school, class_name FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    if is_dev_session():
        return True
    target_role = row["role"] if row["role"] in ROLES else "user"
    current_role = session.get("role", "user")
    
    # Rank check: can only manage lower-ranked users
    if role_rank(target_role) >= role_rank(current_role):
        return False
    
    # School check
    if (row["school"] or "") != admin_school(db):
        return False
    
    if current_role == "teacher":
        teacher_class = teacher_class_for_session(db)
        target_class = normalize_class_name(row["class_name"]) or ""
        if not teacher_class or teacher_class != target_class:
            return False
    
    return True


def teacher_class_for_session(db):
    if session.get("role") != "teacher":
        return ""
    row = db.execute(
        "SELECT class_name FROM users WHERE id = ?",
        (session.get("user_id"),),
    ).fetchone()
    return normalize_class_name(row["class_name"] if row else "") or ""


def can_set_classes():
    return session.get("role") in ("admin", "dev")


def school_names_for_admin(db):
    if is_dev_session():
        rows = db.execute(
            "SELECT name FROM schools ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [r["name"] for r in rows]
    school = admin_school(db)
    return [school] if school else []


def _user_count(db):
    return int(db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])


def _admin_count(db):
    return int(
        db.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role IN ('admin', 'dev')"
        ).fetchone()["c"]
    )


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
    if _admin_count(db) > 0:
        return redirect("/login.html")
    return send_from_directory(app.static_folder, "setup.html")


@app.route("/setup", methods=["GET", "POST"])
def setup_create():
    if request.method == "GET":
        return redirect("/setup.html")

    db = get_db()
    if _admin_count(db) > 0:
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

    levels = parse_subject_levels(request.form) or tuple("pro" for _ in CHAT_SUBJECT_ORDER)
    lg, lm, le, lb, lp, ls, la = levels
    password_hash = generate_password_hash(password)
    row = db.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is not None:
        db.execute(
            """
            UPDATE users
            SET password_hash = ?, level_german = ?, level_math = ?,
                level_english = ?, level_biology = ?, level_pgw = ?,
                level_spanish = ?, level_art = ?, role = 'dev', banned = 0,
                class_name = ''
            WHERE id = ?
            """,
            (password_hash, lg, lm, le, lb, lp, ls, la, row["id"]),
        )
        db.execute("DELETE FROM api_tokens WHERE user_id = ?", (row["id"],))
        new_id = row["id"]
    else:
        try:
            cur = db.execute(
                """
                INSERT INTO users (
                    username, password_hash,
                    level_german, level_math, level_english, level_biology,
                    level_pgw, level_spanish, level_art, role
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'dev')
                """,
                (username, password_hash, lg, lm, le, lb, lp, ls, la),
            )
        except sqlite3.IntegrityError:
            return redirect("/setup.html?flash=taken")
        new_id = cur.lastrowid

    try:
        db.commit()
    except sqlite3.Error:
        return redirect("/setup.html?flash=error")

    session.clear()
    session["user_id"] = new_id
    session["username"] = username
    session["role"] = "dev"
    session["school"] = ""
    return redirect("/dashboard.html?flash=setup_done")


@app.route("/api/setup", methods=["POST"])
def api_setup_create():
    db = get_db()
    if _admin_count(db) > 0:
        return jsonify(error="setup_done"), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    password2 = data.get("password_confirm") or ""

    if not username or len(username) < 3:
        return jsonify(error="shortuser"), 400
    if len(password) < 6:
        return jsonify(error="shortpass"), 400
    if password != password2:
        return jsonify(error="mismatch"), 400

    password_hash = generate_password_hash(password)
    row = db.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is not None:
        db.execute(
            """
            UPDATE users
            SET password_hash = ?, level_german = 'pro', level_math = 'pro',
                level_english = 'pro', level_biology = 'pro', level_pgw = 'pro',
                level_spanish = 'pro', level_art = 'pro', role = 'dev', banned = 0,
                class_name = ''
            WHERE id = ?
            """,
            (password_hash, row["id"]),
        )
        db.execute("DELETE FROM api_tokens WHERE user_id = ?", (row["id"],))
        user_id = row["id"]
    else:
        try:
            cur = db.execute(
                """
                INSERT INTO users (
                    username, password_hash,
                    level_german, level_math, level_english, level_biology,
                    level_pgw, level_spanish, level_art, role
                )
                VALUES (?, ?, 'pro', 'pro', 'pro', 'pro', 'pro', 'pro', 'pro', 'dev')
                """,
                (username, password_hash),
            )
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify(error="taken"), 409

    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO api_tokens (token, user_id) VALUES (?, ?)", (token, user_id))
    db.commit()
    return jsonify(ok=True, token=token, user=_public_user_payload(db, user_id))


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

    role = (request.form.get("role") or "").strip()
    if not role:
        role = "admin" if request.form.get("is_admin") == "1" else "user"
    if role not in ROLES:
        role = "user"
    if role == "dev" and not is_dev_session():
        role = "user"
    if not is_dev_session() and role_rank(role) >= role_rank(session.get("role")):
        role = "user"

    lg, lm, le, lb, lp, ls, la = levels
    vg, vm, ve, vb, vp, vs, va = tuple(1 if level == "pro" else 0 for level in levels)
    db = get_db()
    school = (request.form.get("school") or "").strip()
    class_name = normalize_class_name(request.form.get("class_name"))
    if class_name is None:
        return redirect("/admin.html?flash=invalid_class")
    if not is_dev_session():
        school = admin_school(db)
    if session.get("role") == "teacher":
        teacher_class = teacher_class_for_session(db)
        if not teacher_class:
            return redirect("/admin.html?flash=invalid_class")
        class_name = teacher_class
    class_name = class_name_for_role(role, class_name)
    if class_name is None:
        return redirect("/admin.html?flash=invalid_class")
    if len(school) > 120:
        return redirect("/admin.html?flash=invalid_school")
    if not school_license_has_free_slot(db, school):
        return redirect("/admin.html?flash=code_limit")
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
    try:
        db.execute(
            """
            INSERT INTO users (
                username, password_hash,
                level_german, level_math, level_english, level_biology,
                level_pgw, level_spanish, level_art,
                pro_verified_german, pro_verified_math, pro_verified_english,
                pro_verified_biology, pro_verified_pgw, pro_verified_spanish,
                pro_verified_art,
                role, school, class_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                lg,
                lm,
                le,
                lb,
                lp,
                ls,
                la,
                vg,
                vm,
                ve,
                vb,
                vp,
                vs,
                va,
                role,
                school,
                class_name,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return redirect("/admin.html?flash=taken")

    return redirect("/admin.html?flash=user_created")


@app.route("/api/admin/users", methods=["GET"])
@admin_api
def admin_user_list():
    db = get_db()
    where, params = scoped_user_where(db)
    rows = db.execute(
        f"""
        SELECT id, username, role, school, class_name,
               level_german, level_math, level_english, level_biology,
               level_pgw, level_spanish, level_art,
               pro_verified_german, pro_verified_math, pro_verified_english,
               pro_verified_biology, pro_verified_pgw, pro_verified_spanish,
               pro_verified_art,
               banned, banned_message
        FROM users u
        {where}
        ORDER BY username COLLATE NOCASE
        """,
        params,
    ).fetchall()
    return jsonify(
        users=[
            {
                "id": r["id"],
                "username": r["username"],
                "role": r["role"],
                "school": r["school"] or "",
                "class_name": r["class_name"] or "",
                "level_german": r["level_german"],
                "level_math": r["level_math"],
                "level_english": r["level_english"],
                "level_biology": r["level_biology"],
                "level_pgw": r["level_pgw"],
                "level_spanish": r["level_spanish"],
                "level_art": r["level_art"],
                "pro_verified_german": bool(r["pro_verified_german"]),
                "pro_verified_math": bool(r["pro_verified_math"]),
                "pro_verified_english": bool(r["pro_verified_english"]),
                "pro_verified_biology": bool(r["pro_verified_biology"]),
                "pro_verified_pgw": bool(r["pro_verified_pgw"]),
                "pro_verified_spanish": bool(r["pro_verified_spanish"]),
                "pro_verified_art": bool(r["pro_verified_art"]),
                "banned": bool(r["banned"]),
                "banned_message": r["banned_message"] or "",
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
    message = (data.get("message") or "").strip()
    if banned and not message:
        return jsonify(error="ban_message_required"), 400
    if len(message) > 500:
        return jsonify(error="ban_message_too_long"), 400
    if user_id == session["user_id"]:
        return jsonify(error="self_ban"), 400
    db = get_db()
    if not can_access_user(db, user_id):
        return jsonify(error="not_found"), 404
    if banned:
        db.execute(
            "UPDATE users SET banned = ?, banned_message = ? WHERE id = ?",
            (banned, message, user_id),
        )
    else:
        db.execute("UPDATE users SET banned = ? WHERE id = ?", (banned, user_id))
    db.commit()
    return jsonify(ok=True)


@app.route("/api/admin/users/class", methods=["POST"])
@admin_api
def admin_user_class_update():
    if not can_set_classes():
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="invalid_user"), 400
    class_name = normalize_class_name(data.get("class_name"))
    if class_name is None:
        return jsonify(error="invalid_class"), 400
    db = get_db()
    if not can_access_user(db, user_id):
        return jsonify(error="not_found"), 404
    row = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    role = row["role"] if row and row["role"] in ROLES else "user"
    class_name = class_name_for_role(role, class_name)
    if class_name is None:
        return jsonify(error="invalid_class"), 400
    db.execute("UPDATE users SET class_name = ? WHERE id = ?", (class_name, user_id))
    db.commit()
    return jsonify(ok=True, class_name=class_name)


@app.route("/api/admin/users/pro-verification", methods=["POST"])
@admin_api
def admin_user_pro_verification():
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="invalid_user"), 400

    values = {}
    for subject, col in CHAT_VERIFIED_COLUMN.items():
        raw = data.get(subject)
        values[col] = 1 if raw in (True, "true", "1", 1) else 0

    db = get_db()
    if not can_access_user(db, user_id):
        return jsonify(error="not_found"), 404

    row = db.execute(
        """
        SELECT level_german, level_math, level_english, level_biology,
               level_pgw, level_spanish, level_art
        FROM users WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return jsonify(error="not_found"), 404

    for subject, level_col in CHAT_LEVEL_COLUMN.items():
        if row[level_col] != "pro":
            values[CHAT_VERIFIED_COLUMN[subject]] = 0

    db.execute(
        """
        UPDATE users
        SET pro_verified_german = ?,
            pro_verified_math = ?,
            pro_verified_english = ?,
            pro_verified_biology = ?,
            pro_verified_pgw = ?,
            pro_verified_spanish = ?,
            pro_verified_art = ?
        WHERE id = ?
        """,
        (
            values["pro_verified_german"],
            values["pro_verified_math"],
            values["pro_verified_english"],
            values["pro_verified_biology"],
            values["pro_verified_pgw"],
            values["pro_verified_spanish"],
            values["pro_verified_art"],
            user_id,
        ),
    )
    db.commit()
    return jsonify(
        ok=True,
        pro_verified_german=bool(values["pro_verified_german"]),
        pro_verified_math=bool(values["pro_verified_math"]),
        pro_verified_english=bool(values["pro_verified_english"]),
        pro_verified_biology=bool(values["pro_verified_biology"]),
        pro_verified_pgw=bool(values["pro_verified_pgw"]),
        pro_verified_spanish=bool(values["pro_verified_spanish"]),
        pro_verified_art=bool(values["pro_verified_art"]),
    )


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_api
def admin_user_update(user_id):
    if not is_dev_session():
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "user").strip()
    school = (data.get("school") or "").strip()
    if role not in ROLES:
        return jsonify(error="invalid_role"), 400
    if len(school) > 120:
        return jsonify(error="invalid_school"), 400
    db = get_db()
    row = db.execute("SELECT id, school FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return jsonify(error="not_found"), 404
    old_school = row["school"] or ""
    if school != old_school and not school_license_has_free_slot(db, school):
        return jsonify(error="code_limit", **invite_code_quota_payload(db, school)), 429
    class_name = "" if role in ("admin", "dev") else None
    if class_name is None:
        db.execute(
            "UPDATE users SET role = ?, school = ? WHERE id = ?",
            (role, school, user_id),
        )
    else:
        db.execute(
            "UPDATE users SET role = ?, school = ?, class_name = ? WHERE id = ?",
            (role, school, class_name, user_id),
        )
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
    if user_id == session.get("user_id"):
        session["role"] = role
        session["school"] = school
    else:
        db.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
    db.commit()
    return jsonify(ok=True)


@app.route("/api/admin/schools", methods=["GET"])
@admin_api
def admin_schools_list():
    db = get_db()
    return jsonify(schools=school_names_for_admin(db))


@app.route("/api/admin/schools", methods=["POST"])
@admin_api
def admin_schools_create():
    if not is_dev_session():
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > 120:
        return jsonify(error="invalid_school"), 400
    db = get_db()
    try:
        db.execute("INSERT INTO schools (name) VALUES (?)", (name,))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="duplicate"), 409
    return jsonify(ok=True, name=name)


@app.route("/api/admin/app-settings", methods=["GET"])
@admin_api
def admin_app_settings_get():
    db = get_db()
    school = (request.args.get("school") or "").strip() if is_dev_session() else admin_school(db)
    return jsonify(school_logo_url=school_logo_url_for(db, school), school=school)


@app.route("/api/admin/app-settings", methods=["POST"])
@admin_api
def admin_app_settings_post():
    data = request.get_json(silent=True) or {}
    school_logo_url = (data.get("school_logo_url") or "").strip()
    if len(school_logo_url) > 1000:
        return jsonify(error="invalid_logo_url"), 400
    if school_logo_url and not (
        school_logo_url.startswith("http://")
        or school_logo_url.startswith("https://")
    ):
        return jsonify(error="invalid_logo_url"), 400
    db = get_db()
    school = (data.get("school") or "").strip() if is_dev_session() else admin_school(db)
    if len(school) > 120:
        return jsonify(error="invalid_school"), 400
    set_app_setting(db, school_logo_key(school), school_logo_url)
    db.commit()
    return jsonify(ok=True, school_logo_url=school_logo_url, school=school)


@app.route("/api/admin/mail-status", methods=["GET"])
@admin_api
def admin_mail_status():
    return jsonify(smtp=smtp_status())


@app.route("/api/admin/mail-test", methods=["POST"])
@admin_api
def admin_mail_test():
    data = request.get_json(silent=True) or {}
    recipient = _valid_contact_email(data.get("email"))
    if not recipient:
        return jsonify(error="invalid_email"), 400
    ok, err = send_smtp_mail(
        [recipient],
        "Lerngruppen-Finder: Test-Mail",
        (
            "Das ist eine Test-Mail vom Lerngruppen-Finder.\n\n"
            "Wenn diese Nachricht angekommen ist, funktioniert der Mailserver.\n"
        ),
    )
    if not ok:
        return jsonify(ok=False, error=err or "send_failed", smtp=smtp_status()), 400
    return jsonify(ok=True, smtp=smtp_status())


@app.route("/api/admin/users/password", methods=["POST"])
@admin_api
def admin_user_password():
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="invalid_user"), 400
    password = data.get("password") or ""
    if len(password) < 6:
        return jsonify(error="shortpass"), 400

    db = get_db()
    if not can_access_user(db, user_id):
        return jsonify(error="not_found"), 404
    row = db.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    db.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
    db.commit()
    return jsonify(ok=True, username=row["username"])


@app.route("/api/admin/delete_message/<int:message_id>", methods=["DELETE"])
@admin_api
def admin_delete_message(message_id):
    db = get_db()
    row = db.execute(
        """
        SELECT m.id, u.id AS user_id, u.school, u.role, u.class_name
        FROM chat_messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.id = ?
        """,
        (message_id,),
    ).fetchone()
    target_role = row["role"] if row and row["role"] in ROLES else "user"
    teacher_class = teacher_class_for_session(db) if row else ""
    if not row or (
        not is_dev_session()
        and (
            (row["school"] or "") != admin_school(db)
            or role_rank(target_role) >= role_rank(session.get("role"))
            or (
                session.get("role") == "teacher"
                and (
                    not teacher_class
                    or (normalize_class_name(row["class_name"]) or "") != teacher_class
                )
            )
        )
    ):
        return jsonify(error="message_not_found"), 404
    db.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    db.commit()
    return jsonify(success=True)


@app.route("/api/admin/chat-reports", methods=["GET"])
@admin_api
def admin_chat_reports():
    db = get_db()
    params = []
    where = ["r.resolved_at IS NULL"]
    if not is_dev_session():
        hidden_roles = hidden_roles_for_session()
        placeholders = ", ".join("?" for _ in hidden_roles)
        where.append("r.reported_school = ?")
        where.append(f"r.reported_role NOT IN ({placeholders})")
        params.extend([admin_school(db), *hidden_roles])
        if session.get("role") == "teacher":
            teacher_class = teacher_class_for_session(db)
            if not teacher_class:
                return jsonify(reports=[])
            where.append("r.reported_class_name = ?")
            params.append(teacher_class)
    rows = db.execute(
        f"""
        SELECT
            r.id,
            r.message_id,
            r.subject,
            r.reported_user_id,
            r.reported_username,
            r.reported_school,
            r.reported_class_name,
            r.reporter_user_id,
            r.reporter_username,
            r.body,
            r.reason,
            r.created_at
        FROM chat_message_reports r
        WHERE {" AND ".join(where)}
        ORDER BY datetime(r.created_at) DESC, r.id DESC
        LIMIT 100
        """,
        params,
    ).fetchall()
    return jsonify(
        reports=[
            {
                "id": row["id"],
                "message_id": row["message_id"],
                "subject": row["subject"],
                "subject_label": CHAT_SUBJECT_LABELS.get(row["subject"], row["subject"]),
                "reported_user_id": row["reported_user_id"],
                "reported_username": row["reported_username"],
                "reported_school": row["reported_school"],
                "reported_class_name": row["reported_class_name"],
                "reporter_user_id": row["reporter_user_id"],
                "reporter_username": row["reporter_username"],
                "body": row["body"],
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    )


@app.route("/api/admin/chat-reports/<int:report_id>/resolve", methods=["POST"])
@admin_api
def admin_resolve_chat_report(report_id):
    db = get_db()
    row = db.execute(
        """
        SELECT reported_school, reported_class_name, reported_role
        FROM chat_message_reports
        WHERE id = ? AND resolved_at IS NULL
        """,
        (report_id,),
    ).fetchone()
    target_role = row["reported_role"] if row and row["reported_role"] in ROLES else "user"
    teacher_class = teacher_class_for_session(db) if row else ""
    if not row or (
        not is_dev_session()
        and (
            (row["reported_school"] or "") != admin_school(db)
            or role_rank(target_role) >= role_rank(session.get("role"))
            or (
                session.get("role") == "teacher"
                and (
                    not teacher_class
                    or (normalize_class_name(row["reported_class_name"]) or "") != teacher_class
                )
            )
        )
    ):
        return jsonify(error="report_not_found"), 404
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    db.execute(
        """
        UPDATE chat_message_reports
        SET resolved_at = ?, resolved_by = ?
        WHERE id = ?
        """,
        (now, session["user_id"], report_id),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/admin/chats", methods=["GET"])
@admin_api
def admin_get_chats():
    db = get_db()
    result = []
    for subject in CHAT_SUBJECT_ORDER:
        if is_dev_session():
            count = db.execute(
                "SELECT COUNT(*) as c FROM chat_messages WHERE subject = ?",
                (subject,),
            ).fetchone()["c"]
            rating_n = db.execute(
                "SELECT COUNT(*) as c FROM chat_ratings WHERE subject = ?",
                (subject,),
            ).fetchone()["c"]
            report_n = db.execute(
                """
                SELECT COUNT(*) as c
                FROM chat_message_reports
                WHERE subject = ? AND resolved_at IS NULL
                """,
                (subject,),
            ).fetchone()["c"]
        else:
            school = admin_school(db)
            hidden_roles = hidden_roles_for_session()
            placeholders = ", ".join("?" for _ in hidden_roles)
            class_filter = ""
            class_params = []
            if session.get("role") == "teacher":
                teacher_class = teacher_class_for_session(db)
                if not teacher_class:
                    result.append(
                        {
                            "subject": subject,
                            "label": CHAT_SUBJECT_LABELS[subject],
                            "message_count": 0,
                            "rating_count": 0,
                            "report_count": 0,
                        }
                    )
                    continue
                class_filter = " AND u.class_name = ?"
                class_params.append(teacher_class)
            count = db.execute(
                f"""
                SELECT COUNT(*) as c
                FROM chat_messages m
                JOIN users u ON u.id = m.user_id
                WHERE m.subject = ? AND u.school = ? AND u.role NOT IN ({placeholders}){class_filter}
                """,
                (subject, school, *hidden_roles, *class_params),
            ).fetchone()["c"]
            rating_n = db.execute(
                f"""
                SELECT COUNT(*) as c
                FROM chat_ratings r
                JOIN users u ON u.id = r.user_id
                WHERE r.subject = ? AND u.school = ? AND u.role NOT IN ({placeholders}){class_filter}
                """,
                (subject, school, *hidden_roles, *class_params),
            ).fetchone()["c"]
            report_n = db.execute(
                f"""
                SELECT COUNT(*) as c
                FROM chat_message_reports r
                WHERE r.subject = ?
                  AND r.resolved_at IS NULL
                  AND r.reported_school = ?
                  AND r.reported_role NOT IN ({placeholders}){class_filter.replace("u.", "r.reported_")}
                """,
                (subject, school, *hidden_roles, *class_params),
            ).fetchone()["c"]
        result.append(
            {
                "subject": subject,
                "label": CHAT_SUBJECT_LABELS[subject],
                "message_count": int(count),
                "rating_count": int(rating_n),
                "report_count": int(report_n),
            }
        )
    return jsonify(chats=result)


@app.route("/api/admin/ratings", methods=["GET"])
@admin_api
def admin_list_ratings():
    db = get_db()
    school_filter = ""
    params = []
    if not is_dev_session():
        hidden_roles = hidden_roles_for_session()
        placeholders = ", ".join("?" for _ in hidden_roles)
        school_filter = f"WHERE u.school = ? AND u.role NOT IN ({placeholders})"
        params.extend([admin_school(db), *hidden_roles])
        if session.get("role") == "teacher":
            teacher_class = teacher_class_for_session(db)
            if not teacher_class:
                return jsonify(ratings=[])
            school_filter += " AND u.class_name = ?"
            params.append(teacher_class)
    rows = db.execute(
        f"""
        SELECT r.subject AS subject, r.user_id AS user_id, u.username AS username,
               r.rating AS rating, r.comment AS comment, r.created_at AS created_at,
               s.points AS admin_points, s.note AS admin_note,
               a.started_at AS started_at,
               a.ended_at AS ended_at,
               CASE
                 WHEN a.started_at IS NOT NULL AND a.ended_at IS NOT NULL
                 THEN CAST(strftime('%s', a.ended_at) - strftime('%s', a.started_at) AS INTEGER)
                 ELSE NULL
               END AS duration_seconds
        FROM chat_ratings r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN chat_appointments a ON a.subject = r.subject
        LEFT JOIN admin_subject_scores s
          ON s.user_id = r.user_id AND s.subject = r.subject
        {school_filter}
        ORDER BY r.created_at DESC
        LIMIT 500
        """,
        params,
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
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "duration_seconds": row["duration_seconds"],
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
    if not can_access_user(db, user_id):
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
    if not is_dev_session():
        return jsonify(error="forbidden"), 403
    if subject not in CHAT_SUBJECTS:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    db.execute("DELETE FROM chat_messages WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_appointments WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_ratings WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_message_reports WHERE subject = ?", (subject,))
    db.execute("DELETE FROM chat_presence WHERE subject = ?", (subject,))
    db.commit()
    return jsonify(success=True)


@app.route("/api/setup-status", methods=["GET"])
def setup_status():
    db = get_db()
    return jsonify(setup_needed=_admin_count(db) == 0)


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
            "SELECT code, school, class_name, role FROM invite_codes WHERE code = ? AND used_at IS NULL",
            (code,),
        ).fetchone()
        if not inv:
            db.rollback()
            return redirect("/einladung.html?flash=bad_invite")

        invite_role = inv["role"] if inv["role"] in ROLES else "user"
        invite_class = class_name_for_role(invite_role, inv["class_name"]) or ""
        db.execute(
            """
            INSERT INTO users (
                username, password_hash,
                level_german, level_math, level_english, level_biology,
                level_pgw, level_spanish, level_art,
                role, school, class_name
            )
            VALUES (?, ?, 'noob', 'noob', 'noob', 'noob', 'noob', 'noob', 'noob', ?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                invite_role,
                inv["school"] or "",
                invite_class,
            ),
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
    session["role"] = inv["role"] if inv["role"] in ROLES else "user"
    session["school"] = inv["school"] or ""
    return redirect("/dashboard.html?flash=redeem_ok")


@app.route("/api/invite", methods=["POST"])
def api_invite_redeem():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    password2 = data.get("password_confirm") or ""

    if not code:
        return jsonify(error="bad_invite"), 400
    if not username or len(username) < 3:
        return jsonify(error="shortuser"), 400
    if len(password) < 6:
        return jsonify(error="shortpass"), 400
    if password != password2:
        return jsonify(error="mismatch"), 400

    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute(
            "SELECT code, school, class_name, role FROM invite_codes WHERE code = ? AND used_at IS NULL",
            (code,),
        ).fetchone()
        if not inv:
            db.rollback()
            return jsonify(error="bad_invite"), 400

        invite_role = inv["role"] if inv["role"] in ROLES else "user"
        invite_class = class_name_for_role(invite_role, inv["class_name"]) or ""
        db.execute(
            """
            INSERT INTO users (
                username, password_hash,
                level_german, level_math, level_english, level_biology,
                level_pgw, level_spanish, level_art,
                role, school, class_name
            )
            VALUES (?, ?, 'noob', 'noob', 'noob', 'noob', 'noob', 'noob', 'noob', ?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                invite_role,
                inv["school"] or "",
                invite_class,
            ),
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
            return jsonify(error="bad_invite"), 400

        token = secrets.token_urlsafe(32)
        db.execute(
            "INSERT INTO api_tokens (token, user_id) VALUES (?, ?)",
            (token, new_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="taken"), 409

    return jsonify(ok=True, token=token, user=_public_user_payload(db, new_id))


@app.route("/api/admin/invite-codes", methods=["GET"])
@admin_api
def admin_invite_list():
    db = get_db()
    where = "WHERE used_at IS NULL"
    params = []
    if not is_dev_session():
        where += " AND school = ?"
        params.append(admin_school(db))
        if session.get("role") == "teacher":
            teacher_class = teacher_class_for_session(db)
            if not teacher_class:
                return jsonify(codes=[])
            where += " AND class_name = ?"
            params.append(teacher_class)
    rows = db.execute(
        f"""
        SELECT code, school, class_name, role, created_at
        FROM invite_codes
        {where}
        ORDER BY created_at DESC
        LIMIT 100
        """,
        params,
    ).fetchall()
    return jsonify(
        codes=[
            {
                "code": r["code"],
                "school": r["school"] or "",
                "class_name": r["class_name"] or "",
                "role": r["role"] or "user",
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    )


@app.route("/api/admin/invite-code-limits", methods=["GET"])
@admin_api
def admin_invite_code_limits_get():
    db = get_db()
    school = (request.args.get("school") or "").strip() if is_dev_session() else admin_school(db)
    payload = {
        "school": school,
        "school_limit": school_license_limit(db, school),
        "current": invite_code_quota_payload(db, school),
        "can_edit": is_dev_session(),
    }
    return jsonify(payload)


@app.route("/api/admin/invite-code-limits", methods=["POST"])
@admin_api
def admin_invite_code_limits_post():
    if not is_dev_session():
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    school = (data.get("school") or "").strip()
    if len(school) > 120:
        return jsonify(error="invalid_school"), 400
    try:
        limit = max(0, int(data.get("school_limit") or data.get("limit") or 0))
    except (TypeError, ValueError):
        return jsonify(error="invalid_limit"), 400
    db = get_db()
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
    set_school_license_limit(db, school, limit)
    db.commit()
    return jsonify(
        ok=True,
        school=school,
        school_limit=limit,
        current=invite_code_quota_payload(db, school),
    )


@app.route("/api/admin/invite-codes", methods=["POST"])
@admin_api
def admin_invite_create():
    data = request.get_json(silent=True) or {}
    school = (data.get("school") or "").strip()
    class_name = normalize_class_name(data.get("class_name"))
    role = (data.get("role") or "user").strip()
    if role not in ROLES:
        return jsonify(error="invalid_role"), 400
    if class_name is None:
        return jsonify(error="invalid_class"), 400

    db = get_db()
    if not is_dev_session():
        school = admin_school(db)
        if role_rank(role) >= role_rank(session.get("role")):
            return jsonify(error="forbidden"), 403
        if session.get("role") == "teacher":
            teacher_class = teacher_class_for_session(db)
            if not teacher_class:
                return jsonify(error="forbidden"), 403
            if role != "user":
                return jsonify(error="forbidden"), 403
            class_name = teacher_class
    quota = invite_code_quota_payload(db, school)
    if quota["limit"] > 0 and quota["active"] >= quota["limit"]:
        return jsonify(error="code_limit", **quota), 429
    class_name = class_name_for_role(role, class_name)
    if class_name is None:
        return jsonify(error="invalid_class"), 400
    if len(school) > 120:
        return jsonify(error="invalid_school"), 400
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
    uid = session["user_id"]
    creator_role = session.get("role", "user")
    for _ in range(12):
        code = secrets.token_hex(6)
        try:
            db.execute(
                """
                INSERT INTO invite_codes
                    (code, created_by, created_by_role, school, class_name, role)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (code, uid, creator_role, school, class_name, role),
            )
            db.commit()
            return jsonify(
                code=code,
                created_by=uid,
                school=school,
                class_name=class_name,
                role=role,
            )
        except sqlite3.IntegrityError:
            db.rollback()
            continue
    return jsonify(error="generate"), 500


@app.route("/api/admin/invite-codes/<code>", methods=["DELETE"])
@admin_api
def admin_invite_delete(code):
    code = (code or "").strip()
    if not code:
        return jsonify(error="bad_invite"), 400
    db = get_db()
    row = db.execute(
        """
        SELECT code, school, class_name, role
        FROM invite_codes
        WHERE code = ? AND used_at IS NULL
        """,
        (code,),
    ).fetchone()
    if not row:
        return jsonify(error="bad_invite"), 404
    target_role = row["role"] if row["role"] in ROLES else "user"
    if not is_dev_session():
        if (row["school"] or "") != admin_school(db):
            return jsonify(error="bad_invite"), 404
        if role_rank(target_role) >= role_rank(session.get("role")):
            return jsonify(error="forbidden"), 403
        if session.get("role") == "teacher":
            teacher_class = teacher_class_for_session(db)
            if not teacher_class or (row["class_name"] or "") != teacher_class:
                return jsonify(error="bad_invite"), 404
            if target_role != "user":
                return jsonify(error="forbidden"), 403
    db.execute("DELETE FROM invite_codes WHERE code = ? AND used_at IS NULL", (code,))
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/rooms", methods=["GET"])
@login_required_api
def chat_rooms():
    db = get_db()
    uid = session["user_id"]
    rooms = []
    creatable = []
    for base_subject in CHAT_SUBJECT_ORDER:
        if not user_may_access_subject(db, uid, base_subject):
            continue
        room_keys = [
            row["subject"]
            for row in db.execute(
                "SELECT DISTINCT subject FROM chat_presence WHERE subject = ? OR subject LIKE ? ORDER BY subject",
                (base_subject, f"{base_subject}:%"),
            ).fetchall()
        ]
        viewer_lv = _user_level_for_subject(db, uid, base_subject)
        if viewer_lv == "pro":
            creatable.append({"subject": base_subject, "label": CHAT_SUBJECT_LABELS[base_subject]})
        for room_key in room_keys:
            verified_col = CHAT_VERIFIED_COLUMN[base_subject]
            members = db.execute(
                f"""
                SELECT
                    p.username,
                    p.level,
                    COALESCE(u.{verified_col}, 0) AS verified,
                    COALESCE(u.role, 'user') AS role
                FROM chat_presence p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE p.subject = ? ORDER BY p.username COLLATE NOCASE
                """,
                (room_key,),
            ).fetchall()
            you = db.execute(
                "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
                (room_key, uid),
            ).fetchone()
            appointment_row = db.execute(
                "SELECT appointment, location, started FROM chat_appointments WHERE subject = ?",
                (room_key,),
            ).fetchone()
            you_in = you is not None
            count_total = len(members)
            if count_total == 0:
                db.execute("DELETE FROM chat_messages WHERE subject = ?", (room_key,))
                continue
            non_pro_n = sum(1 for m in members if m["level"] != "pro")
            pro_n = sum(1 for m in members if m["level"] == "pro")
            if pro_n == 0:
                db.execute("DELETE FROM chat_presence WHERE subject = ?", (room_key,))
                db.execute("DELETE FROM chat_messages WHERE subject = ?", (room_key,))
                continue
            has_pro = pro_n >= 1
            locked = bool(appointment_row and appointment_row["started"] and not you_in)
            if viewer_lv == "pro":
                can_join = not locked
                join_block = "started" if locked else None
                full = False
            else:
                slot_free = non_pro_n < CHAT_MAX_USERS
                can_join = (you_in or (has_pro and slot_free and not locked))
                if you_in:
                    join_block = None
                elif locked:
                    join_block = "started"
                elif not has_pro:
                    join_block = "need_pro"
                elif not slot_free:
                    join_block = "full"
                else:
                    join_block = None
                full = not can_join
            rooms.append(
                {
                    "subject": room_key,
                    "base_subject": base_subject,
                    "label": chat_room_label(room_key),
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
                    "location": appointment_row["location"] if appointment_row else None,
                    "started": bool(appointment_row["started"]) if appointment_row else False,
                    "members": [
                        {
                            "username": m["username"],
                            "level": m["level"],
                            "pro_verified": m["level"] == "pro"
                            and (bool(m["verified"]) or m["role"] in ("teacher", "admin", "dev")),
                        }
                        for m in members
                    ],
                }
            )
    db.commit()
    return jsonify(rooms=rooms, creatable=creatable)


@app.route("/api/chat/appointment", methods=["GET"])
@login_required_api
def chat_appointment_get():
    room_key, base_subject = chat_room_key(request.args.get("subject"))
    if not room_key:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    uid = session["user_id"]
    if not user_may_access_subject(db, uid, base_subject):
        return jsonify(error="invalid_subject"), 400
    row = db.execute(
        "SELECT appointment, location, created_at, started, started_at, ended, ended_at FROM chat_appointments WHERE subject = ?",
        (room_key,),
    ).fetchone()
    if not row:
        db.commit()
        return jsonify(appointment=None)

    is_pro = _user_level_for_subject(db, uid, base_subject) == "pro"
    your_rating = None
    rating_count = None
    rating_avg = None
    ratings = None
    if is_pro:
        your_rating = db.execute(
            "SELECT rating, comment FROM chat_ratings WHERE subject = ? AND user_id = ?",
            (room_key, uid),
        ).fetchone()
        rating_stats = db.execute(
            "SELECT COUNT(*) AS count, AVG(rating) AS avg FROM chat_ratings WHERE subject = ?",
            (room_key,),
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
            (room_key,),
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
        location=row["location"],
        created_at=row["created_at"],
        started=bool(row["started"]),
        started_at=row["started_at"],
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
    room_key, base_subject = chat_room_key(data.get("subject"))
    appointment = _normalize_appointment_datetime(data.get("appointment"))
    location = _normalize_appointment_location(data.get("location"))
    if not room_key:
        return jsonify(error="invalid_subject"), 400
    if data.get("appointment") is None or not str(data.get("appointment")).strip():
        return jsonify(error="empty"), 400
    if not appointment:
        return jsonify(error="invalid_datetime"), 400
    if data.get("location") is None or not str(data.get("location")).strip():
        return jsonify(error="empty_location"), 400
    if not location:
        return jsonify(error="invalid_location"), 400

    db = get_db()
    uid = session["user_id"]
    if not user_may_access_subject(db, uid, base_subject):
        return jsonify(error="invalid_subject"), 400
    level = _user_level_for_subject(db, uid, base_subject)
    if level != "pro":
        return jsonify(error="permission"), 403

    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    existing = db.execute(
        "SELECT 1 FROM chat_appointments WHERE subject = ?",
        (room_key,),
    ).fetchone()
    if existing:
        db.execute(
            """
            UPDATE chat_appointments
            SET appointment = ?,
                location = ?,
                created_by = ?,
                updated_at = ?,
                started = 0,
                started_at = NULL,
                ended = 0,
                ended_at = NULL
            WHERE subject = ?
            """,
            (appointment, location, uid, now, room_key),
        )
    else:
        db.execute(
            """
            INSERT INTO chat_appointments (subject, appointment, location, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (room_key, appointment, location, uid, now, now),
        )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/appointment/start", methods=["POST"])
@login_required_api
def chat_appointment_start():
    data = request.get_json(silent=True) or {}
    room_key, base_subject = chat_room_key(data.get("subject"))
    if not room_key:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    uid = session["user_id"]
    if not user_may_access_subject(db, uid, base_subject):
        return jsonify(error="invalid_subject"), 400
    level = _user_level_for_subject(db, uid, base_subject)
    if level != "pro":
        return jsonify(error="permission"), 403
    row = db.execute(
        "SELECT started, ended FROM chat_appointments WHERE subject = ?",
        (room_key,),
    ).fetchone()
    if not row:
        db.commit()
        return jsonify(error="no_appointment"), 400
    if row["ended"]:
        db.commit()
        return jsonify(error="already_ended"), 400
    if row["started"]:
        db.commit()
        return jsonify(ok=True)
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    db.execute(
        """
        UPDATE chat_appointments
        SET started = 1, started_at = ?, updated_at = ?
        WHERE subject = ?
        """,
        (now, now, room_key),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/chat/appointment/end", methods=["POST"])
@login_required_api
def chat_appointment_end():
    data = request.get_json(silent=True) or {}
    room_key, base_subject = chat_room_key(data.get("subject"))
    if not room_key:
        return jsonify(error="invalid_subject"), 400
    db = get_db()
    uid = session["user_id"]
    if not user_may_access_subject(db, uid, base_subject):
        return jsonify(error="invalid_subject"), 400
    level = _user_level_for_subject(db, uid, base_subject)
    if level != "pro":
        return jsonify(error="permission"), 403
    row = db.execute(
        "SELECT started, ended FROM chat_appointments WHERE subject = ?",
        (room_key,),
    ).fetchone()
    if not row:
        db.commit()
        return jsonify(error="no_appointment"), 400
    if row["ended"]:
        db.commit()
        return jsonify(ok=True)
    if not row["started"]:
        db.commit()
        return jsonify(error="not_started"), 400
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    db.execute(
        "UPDATE chat_appointments SET ended = 1, ended_at = ?, updated_at = ? WHERE subject = ?",
        (now, now, room_key),
    )
    db.execute("DELETE FROM chat_messages WHERE subject = ?", (room_key,))
    db.commit()
    return jsonify(ok=True, cleared=True)


@app.route("/api/chat/appointment/rate", methods=["POST"])
@login_required_api
def chat_appointment_rate():
    data = request.get_json(silent=True) or {}
    room_key, base_subject = chat_room_key(data.get("subject"))
    if not room_key:
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
    if not user_may_access_subject(db, uid, base_subject):
        return jsonify(error="invalid_subject"), 400
    level = _user_level_for_subject(db, uid, base_subject)
    if level != "pro":
        db.commit()
        return jsonify(error="permission"), 403
    appointment = db.execute(
        "SELECT ended FROM chat_appointments WHERE subject = ?",
        (room_key,),
    ).fetchone()
    if not appointment or not appointment["ended"]:
        db.commit()
        return jsonify(error="not_ended"), 400
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (room_key, uid),
    ).fetchone()
    if not in_room:
        db.commit()
        return jsonify(error="not_in_room"), 403
    existing = db.execute(
        "SELECT 1 FROM chat_ratings WHERE subject = ? AND user_id = ?",
        (room_key, uid),
    ).fetchone()
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    if existing:
        db.execute(
            "UPDATE chat_ratings SET rating = ?, comment = ?, created_at = ? WHERE subject = ? AND user_id = ?",
            (rating, comment, now, room_key, uid),
        )
    else:
        db.execute(
            "INSERT INTO chat_ratings (subject, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (room_key, uid, rating, comment, now),
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
    if not user_may_access_subject(db, uid, subject):
        return jsonify(error="invalid_subject"), 400
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

    appointment_row = db.execute(
        "SELECT started FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if appointment_row and appointment_row["started"]:
        db.commit()
        return jsonify(error="room_closed"), 403

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
    if not user_may_access_subject(db, uid, subject):
        return jsonify(error="invalid_subject"), 400
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
    _clear_chat_messages_if_room_empty(db, subject)
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
    if not user_may_access_subject(db, uid, subject):
        return jsonify(error="invalid_subject"), 400
    level_col = CHAT_LEVEL_COLUMN[subject]
    verified_col = CHAT_VERIFIED_COLUMN[subject]
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403
    appointment_row = db.execute(
        "SELECT ended FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if appointment_row and appointment_row["ended"]:
        db.commit()
        return jsonify(error="appointment_ended"), 400
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
        f"""
        SELECT
            m.id,
            m.user_id,
            m.username,
            COALESCE(u.role, 'user') AS role,
            COALESCE(u.{level_col}, 'noob') AS level,
            COALESCE(u.{verified_col}, 0) AS pro_verified,
            m.body,
            m.created_at
        FROM chat_messages m
        LEFT JOIN users u ON u.id = m.user_id
        WHERE m.subject = ? AND m.id > ?
        ORDER BY m.id ASC
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
                "role": r["role"],
                "level": r["level"],
                "pro_verified": r["level"] == "pro"
                and (
                    bool(r["pro_verified"])
                    or r["role"] in ("teacher", "admin", "dev")
                ),
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
    if not user_may_access_subject(db, uid, subject):
        return jsonify(error="invalid_subject"), 400
    uname = session["username"]

    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (subject, uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403
    appointment_row = db.execute(
        "SELECT ended FROM chat_appointments WHERE subject = ?",
        (subject,),
    ).fetchone()
    if appointment_row and appointment_row["ended"]:
        db.commit()
        return jsonify(error="appointment_ended"), 400
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


@app.route("/api/chat/report-message", methods=["POST"])
@login_required_api
def chat_report_message():
    data = request.get_json(silent=True) or {}
    try:
        message_id = int(data.get("message_id") or 0)
    except (TypeError, ValueError):
        return jsonify(error="invalid_message"), 400
    reason = (data.get("reason") or "").strip()
    if len(reason) > 300:
        return jsonify(error="reason_too_long"), 400

    db = get_db()
    uid = session["user_id"]
    row = db.execute(
        """
        SELECT
            m.id,
            m.subject,
            m.user_id AS reported_user_id,
            m.username AS reported_username,
            m.body,
            u.school AS reported_school,
            u.class_name AS reported_class_name,
            COALESCE(u.role, 'user') AS reported_role
        FROM chat_messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.id = ?
        """,
        (message_id,),
    ).fetchone()
    if not row:
        return jsonify(error="message_not_found"), 404
    if row["reported_user_id"] == uid:
        return jsonify(error="own_message"), 400
    if not user_may_access_subject(db, uid, row["subject"]):
        return jsonify(error="message_not_found"), 404
    in_room = db.execute(
        "SELECT 1 FROM chat_presence WHERE subject = ? AND user_id = ?",
        (row["subject"], uid),
    ).fetchone()
    if not in_room:
        return jsonify(error="not_in_room"), 403

    reporter = db.execute(
        "SELECT username FROM users WHERE id = ?",
        (uid,),
    ).fetchone()
    try:
        db.execute(
            """
            INSERT INTO chat_message_reports (
                message_id,
                subject,
                reported_user_id,
                reported_username,
                reported_school,
                reported_class_name,
                reported_role,
                reporter_user_id,
                reporter_username,
                body,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["subject"],
                row["reported_user_id"],
                row["reported_username"],
                row["reported_school"] or "",
                row["reported_class_name"] or "",
                row["reported_role"] if row["reported_role"] in ROLES else "user",
                uid,
                reporter["username"] if reporter else session.get("username", ""),
                row["body"],
                reason,
            ),
        )
    except sqlite3.IntegrityError:
        db.commit()
        return jsonify(error="already_reported"), 409
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
        "SELECT id, password_hash, role, school, banned FROM users WHERE username = ?",
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
    session["school"] = row["school"] or ""

    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("/dashboard.html")


def _public_user_payload(db, user_id):
    row = db.execute(
        """
        SELECT username, role, school, class_name,
               level_german, level_math, level_english, level_biology,
               level_pgw, level_spanish, level_art,
               pro_verified_german, pro_verified_math, pro_verified_english,
               pro_verified_biology, pro_verified_pgw, pro_verified_spanish,
               pro_verified_art,
               contact_email, notify_laden_email,
               avatar_url, iserv_email
        FROM users WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    role = row["role"] if row["role"] in ROLES else "user"
    return {
        "user_id": user_id,
        "username": row["username"],
        "role": role,
        "school": row["school"] or "",
        "class_name": row["class_name"] or "",
        "level_german": row["level_german"],
        "level_math": row["level_math"],
        "level_english": row["level_english"],
        "level_biology": row["level_biology"],
        "level_pgw": row["level_pgw"],
        "level_spanish": row["level_spanish"],
        "level_art": row["level_art"],
        "pro_verified_german": bool(row["pro_verified_german"]),
        "pro_verified_math": bool(row["pro_verified_math"]),
        "pro_verified_english": bool(row["pro_verified_english"]),
        "pro_verified_biology": bool(row["pro_verified_biology"]),
        "pro_verified_pgw": bool(row["pro_verified_pgw"]),
        "pro_verified_spanish": bool(row["pro_verified_spanish"]),
        "pro_verified_art": bool(row["pro_verified_art"]),
        "contact_email": row["contact_email"] or "",
        "notify_laden_email": bool(row["notify_laden_email"]),
        "avatar_url": row["avatar_url"] or "",
        "iserv_email": row["iserv_email"] or "",
        "school_logo_url": school_logo_url_for(db, row["school"] or ""),
    }


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    row = db.execute(
        "SELECT id, password_hash, role, banned FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify(error="invalid"), 401
    if row["banned"]:
        msg = banned_message_for_user(db, row["id"])
        return jsonify(error="banned", message=msg), 403

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO api_tokens (token, user_id) VALUES (?, ?)",
        (token, row["id"]),
    )
    db.commit()
    user = _public_user_payload(db, row["id"])
    return jsonify(ok=True, token=token, user=user)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login.html?flash=logout")


@app.route("/api/logout", methods=["POST"])
@login_required_api
def api_logout():
    token = getattr(g, "api_token", None)
    if token:
        db = get_db()
        db.execute("DELETE FROM api_tokens WHERE token = ?", (token,))
        db.commit()
    session.clear()
    return jsonify(ok=True)


def _valid_contact_email(raw):
    s = (raw or "").strip()
    if not s:
        return None
    if len(s) > 254 or "@" not in s or " " in s:
        return None
    return s


def _valid_optional_url(raw, max_len=1000):
    s = (raw or "").strip()
    if not s:
        return ""
    if len(s) > max_len:
        return None
    if not (s.startswith("http://") or s.startswith("https://")):
        return None
    return s


def _valid_avatar_value(raw):
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith("/uploads/avatars/"):
        return s if len(s) <= 300 else None
    if len(s) > 4000:
        return None
    if s.startswith("data:image/svg+xml"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return None


def _save_avatar_upload(file_storage):
    if file_storage is None or not file_storage.filename:
        return ""
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in AVATAR_ALLOWED_EXTENSIONS:
        return None
    data = file_storage.read(AVATAR_MAX_BYTES + 1)
    if not data or len(data) > AVATAR_MAX_BYTES:
        return None
    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_urlsafe(18)}.{ext}"
    path = AVATAR_UPLOAD_DIR / filename
    path.write_bytes(data)
    return f"/uploads/avatars/{filename}"


@app.route("/profile", methods=["POST"])
@login_required
def profile_update():
    levels = parse_subject_levels(request.form)
    if levels is None:
        return redirect("/settings.html?flash=levels")
    lg, lm, le, lb, lp, ls, la = levels
    raw_mail = (request.form.get("contact_email") or "").strip()
    contact_email = _valid_contact_email(raw_mail)
    if raw_mail and contact_email is None:
        return redirect("/settings.html?flash=bad_contact_email")
    want_notify = request.form.get("notify_laden_email") == "1"
    if want_notify and not contact_email:
        return redirect("/settings.html?flash=notify_no_email")
    notify_val = 1 if (want_notify and contact_email) else 0
    email_val = contact_email
    school = _normalize_school_name(request.form.get("school"))
    if school is None:
        return redirect("/settings.html?flash=invalid_school")

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
    level_row = db.execute(
        """
        SELECT level_german, level_math, level_english, level_biology,
               level_pgw, level_spanish, level_art,
               pro_verified_german, pro_verified_math, pro_verified_english,
               pro_verified_biology, pro_verified_pgw, pro_verified_spanish,
               pro_verified_art,
               avatar_url, school
        FROM users WHERE id = ?
        """,
        (uid,),
    ).fetchone()
    if level_row is None:
        return redirect("/login.html?flash=needlogin")
    avatar_url = level_row["avatar_url"] or ""
    uploaded_avatar = _save_avatar_upload(request.files.get("avatar_upload"))
    if uploaded_avatar is None:
        return redirect("/settings.html?flash=bad_avatar")
    if uploaded_avatar:
        avatar_url = uploaded_avatar
    elif request.form.get("avatar_choice") == "builder":
        built_avatar = _valid_avatar_value(request.form.get("avatar_data"))
        if built_avatar is None:
            return redirect("/settings.html?flash=bad_avatar")
        avatar_url = built_avatar
    vg, vm, ve, vb, vp, vs, va = next_pro_verification_values(level_row, levels)
    if school != (level_row["school"] or "") and not school_license_has_free_slot(db, school):
        return redirect("/settings.html?flash=code_limit")
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
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
                level_biology = ?, level_pgw = ?, level_spanish = ?, level_art = ?,
                pro_verified_german = ?, pro_verified_math = ?, pro_verified_english = ?,
                pro_verified_biology = ?, pro_verified_pgw = ?, pro_verified_spanish = ?,
                pro_verified_art = ?,
                contact_email = ?, notify_laden_email = ?,
                school = ?, avatar_url = ?,
                password_hash = ?
            WHERE id = ?
            """,
            (
                lg, lm, le, lb, lp, ls, la,
                vg, vm, ve, vb, vp, vs, va,
                email_val, notify_val, school, avatar_url, new_hash, uid,
            ),
        )
    else:
        db.execute(
            """
            UPDATE users SET level_german = ?, level_math = ?, level_english = ?,
                level_biology = ?, level_pgw = ?, level_spanish = ?, level_art = ?,
                pro_verified_german = ?, pro_verified_math = ?, pro_verified_english = ?,
                pro_verified_biology = ?, pro_verified_pgw = ?, pro_verified_spanish = ?,
                pro_verified_art = ?,
                contact_email = ?, notify_laden_email = ?,
                school = ?, avatar_url = ?
            WHERE id = ?
            """,
            (
                lg, lm, le, lb, lp, ls, la,
                vg, vm, ve, vb, vp, vs, va,
                email_val, notify_val, school, avatar_url, uid,
            ),
        )
    db.commit()
    session["school"] = school or ""
    return redirect("/settings.html?flash=saved")


@app.route("/api/profile", methods=["POST"])
@login_required_api
def api_profile_update():
    data = request.get_json(silent=True) or {}
    levels = parse_subject_levels(data)
    if levels is None:
        return jsonify(error="levels"), 400
    lg, lm, le, lb, lp, ls, la = levels
    raw_mail = (data.get("contact_email") or "").strip()
    contact_email = _valid_contact_email(raw_mail)
    if raw_mail and contact_email is None:
        return jsonify(error="bad_contact_email"), 400
    want_notify = data.get("notify_laden_email") in (True, "true", "1", 1)
    if want_notify and not contact_email:
        return jsonify(error="notify_no_email"), 400
    notify_val = 1 if (want_notify and contact_email) else 0
    avatar_url = _valid_avatar_value(data.get("avatar_url"))
    if avatar_url is None:
        return jsonify(error="invalid_avatar_url"), 400
    school = _normalize_school_name(data.get("school"))
    if school is None:
        return jsonify(error="invalid_school"), 400
    raw_iserv = (data.get("iserv_email") or "").strip()
    iserv_email = _valid_contact_email(raw_iserv)
    if raw_iserv and iserv_email is None:
        return jsonify(error="bad_iserv_email"), 400

    cur_pwd = data.get("current_password") or ""
    new_pwd = data.get("new_password") or ""
    new_pwd2 = data.get("new_password_confirm") or ""
    pwd_change = bool(cur_pwd or new_pwd or new_pwd2)
    if pwd_change:
        if not cur_pwd or not new_pwd or not new_pwd2:
            return jsonify(error="pwd_incomplete"), 400
        if len(new_pwd) < 6:
            return jsonify(error="shortpass"), 400
        if new_pwd != new_pwd2:
            return jsonify(error="mismatch"), 400

    db = get_db()
    uid = session["user_id"]
    level_row = db.execute(
        """
        SELECT level_german, level_math, level_english, level_biology,
               level_pgw, level_spanish, level_art,
               pro_verified_german, pro_verified_math, pro_verified_english,
               pro_verified_biology, pro_verified_pgw, pro_verified_spanish,
               pro_verified_art, school
        FROM users WHERE id = ?
        """,
        (uid,),
    ).fetchone()
    if level_row is None:
        return jsonify(error="auth"), 401
    vg, vm, ve, vb, vp, vs, va = next_pro_verification_values(level_row, levels)
    if school != (level_row["school"] or "") and not school_license_has_free_slot(db, school):
        return jsonify(error="code_limit", **invite_code_quota_payload(db, school)), 429
    if school:
        db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
    if pwd_change:
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], cur_pwd):
            return jsonify(error="pwd_current_wrong"), 400
        db.execute(
            """
            UPDATE users SET level_german = ?, level_math = ?, level_english = ?,
                level_biology = ?, level_pgw = ?, level_spanish = ?, level_art = ?,
                pro_verified_german = ?, pro_verified_math = ?, pro_verified_english = ?,
                pro_verified_biology = ?, pro_verified_pgw = ?, pro_verified_spanish = ?,
                pro_verified_art = ?,
                contact_email = ?, notify_laden_email = ?, school = ?,
                avatar_url = ?, iserv_email = ?, password_hash = ?
            WHERE id = ?
            """,
            (
                lg,
                lm,
                le,
                lb,
                lp,
                ls,
                la,
                vg,
                vm,
                ve,
                vb,
                vp,
                vs,
                va,
                contact_email,
                notify_val,
                school,
                avatar_url,
                iserv_email or "",
                generate_password_hash(new_pwd),
                uid,
            ),
        )
    else:
        db.execute(
            """
            UPDATE users SET level_german = ?, level_math = ?, level_english = ?,
                level_biology = ?, level_pgw = ?, level_spanish = ?, level_art = ?,
                pro_verified_german = ?, pro_verified_math = ?, pro_verified_english = ?,
                pro_verified_biology = ?, pro_verified_pgw = ?, pro_verified_spanish = ?,
                pro_verified_art = ?,
                contact_email = ?, notify_laden_email = ?, school = ?,
                avatar_url = ?, iserv_email = ?
            WHERE id = ?
            """,
            (
                lg, lm, le, lb, lp, ls, la,
                vg, vm, ve, vb, vp, vs, va,
                contact_email, notify_val, school, avatar_url, iserv_email or "", uid,
            ),
        )
    db.commit()
    session["school"] = school or ""
    return jsonify(ok=True, user=_public_user_payload(db, uid))


@app.route("/api/learning-places", methods=["GET"])
@login_required_api
def learning_places_list():
    db = get_db()
    school = admin_school(db)
    if school:
        rows = db.execute(
            """
            SELECT id, username, school, name, address, note, created_at
            FROM learning_places
            WHERE school = ? OR school = ''
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 50
            """,
            (school,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT id, username, school, name, address, note, created_at
            FROM learning_places
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 50
            """
        ).fetchall()
    return jsonify(
        places=[
            {
                "id": row["id"],
                "username": row["username"],
                "school": row["school"] or "",
                "name": row["name"],
                "address": row["address"] or "",
                "note": row["note"] or "",
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    )


@app.route("/api/learning-places", methods=["POST"])
@login_required_api
def learning_places_create():
    data = request.get_json(silent=True) or {}
    name = " ".join((data.get("name") or "").strip().split())
    address = " ".join((data.get("address") or "").strip().split())
    note = (data.get("note") or "").strip()
    if not name or len(name) > 120:
        return jsonify(error="invalid_name"), 400
    if len(address) > 200:
        return jsonify(error="invalid_address"), 400
    if len(note) > 500:
        return jsonify(error="invalid_note"), 400
    db = get_db()
    uid = session["user_id"]
    user = _public_user_payload(db, uid)
    if user is None:
        return jsonify(error="auth"), 401
    school = user["school"] or ""
    db.execute(
        """
        INSERT INTO learning_places (user_id, username, school, name, address, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (uid, user["username"], school, name, address, note),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/api/me")
def api_me():
    if not _load_api_auth_context():
        return jsonify({}), 401
    db = get_db()
    user = _public_user_payload(db, session["user_id"])
    if user is None:
        return jsonify({}), 401
    return jsonify(user)


@app.route("/uploads/avatars/<path:filename>")
def uploaded_avatar(filename):
    return send_from_directory(str(AVATAR_UPLOAD_DIR), filename)


from shop import register_shop_routes

register_shop_routes(app, get_db, admin_api, login_required, login_required_api)

with app.app_context():
    init_db()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5000")))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
