"""MongoDB-Zugriffsschicht.

Ersetzt die frühere SQLite-Anbindung (get_db/close_db/init_db in app.py). Der
MongoClient ist ein prozessweiter, thread-sicherer Singleton – anders als bei
SQLite braucht es keine Verbindung pro Request und kein teardown.

Verbindung/Datenbank kommen aus der Umgebung:
    MONGODB_URI   z. B. mongodb+srv://user:pass@cluster.xxxxx.mongodb.net
    MONGODB_DB    Datenbankname (Default: "grouply")
"""

import os

from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError  # noqa: F401  (re-export für app.py)
from bson import ObjectId
from bson.errors import InvalidId

_client = None


def get_client():
    """Prozessweiter MongoClient-Singleton (lazy)."""
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError(
                "MONGODB_URI ist nicht gesetzt – ohne Datenbank-URI kann die "
                "App nicht starten."
            )
        # tz_aware: Datetimes kommen als timezone-aware (UTC) zurück, passend zu
        # datetime.now(timezone.utc), das wir beim Schreiben verwenden.
        _client = MongoClient(uri, tz_aware=True)
    return _client


def get_db():
    """Gibt die pymongo-Database zurück (Ersatz für das alte get_db())."""
    return get_client()[os.environ.get("MONGODB_DB", "grouply")]


def oid(value):
    """Parst einen String/ObjectId zu ObjectId. Gibt None bei ungültigem Wert.

    Ersetzt die frühere int()-Konvertierung von IDs. Aufrufer behandeln None
    als "nicht gefunden / 400".
    """
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def ensure_indexes():
    """Legt alle Indizes an (idempotent). Ersatz für init_db()/_ensure_*.

    MongoDB ist schemalos, daher entfallen CREATE TABLE / ALTER TABLE. Wir legen
    nur die Unique-/Sekundär-Indizes an, die die frühere SQLite-Schemadefinition
    hatte.
    """
    db = get_db()

    # users.username war UNIQUE NOT NULL.
    db.users.create_index("username", unique=True, name="uq_users_username")

    # schools.name war PRIMARY KEY -> als _id gespeichert, kein extra Index nötig.

    # learning_places: Index (school, created_at).
    db.learning_places.create_index(
        [("school", ASCENDING), ("created_at", ASCENDING)],
        name="idx_learning_places_school_created",
    )

    # chat_presence: PRIMARY KEY (subject, user_id).
    db.chat_presence.create_index(
        [("subject", ASCENDING), ("user_id", ASCENDING)],
        unique=True,
        name="uq_chat_presence_subject_user",
    )

    # chat_messages: Index (subject, _id) für Cursor-Paginierung.
    db.chat_messages.create_index(
        [("subject", ASCENDING), ("_id", ASCENDING)],
        name="idx_chat_messages_subject_id",
    )

    # chat_appointments.subject war PRIMARY KEY -> als _id gespeichert.

    # chat_ratings: PRIMARY KEY (subject, user_id).
    db.chat_ratings.create_index(
        [("subject", ASCENDING), ("user_id", ASCENDING)],
        unique=True,
        name="uq_chat_ratings_subject_user",
    )

    # chat_message_reports: UNIQUE(message_id, reporter_user_id) + Index.
    db.chat_message_reports.create_index(
        [("message_id", ASCENDING), ("reporter_user_id", ASCENDING)],
        unique=True,
        name="uq_chat_reports_message_reporter",
    )
    db.chat_message_reports.create_index(
        [("subject", ASCENDING), ("created_at", ASCENDING)],
        name="idx_chat_reports_subject_created",
    )

    # invite_codes.code war PRIMARY KEY -> als _id gespeichert.

    # admin_subject_scores: PRIMARY KEY (user_id, subject).
    db.admin_subject_scores.create_index(
        [("user_id", ASCENDING), ("subject", ASCENDING)],
        unique=True,
        name="uq_admin_subject_scores_user_subject",
    )

    # api_tokens.token war PRIMARY KEY -> als _id gespeichert. Index auf user_id.
    db.api_tokens.create_index("user_id", name="idx_api_tokens_user_id")

    # app_settings.key war PRIMARY KEY -> als _id gespeichert.

    # laden_purchases: Index created_at.
    db.laden_purchases.create_index("created_at", name="idx_laden_purchases_created")
