"""Einmalige Datenmigration SQLite -> MongoDB.

Liest die alte SQLite-DB (users.db bzw. seed.db) und schreibt die Daten nach
MongoDB Atlas. Da wir von INTEGER-Auto-Increment-IDs auf native ObjectId
umstellen, werden alle Primaerschluessel neu vergeben und JEDE Fremdschluessel-
Referenz ueber ID-Maps umgeschrieben.

Aufruf:
    MONGODB_URI="mongodb+srv://..." MONGODB_DB="grouply" \
        python migrate_sqlite_to_mongo.py [pfad/zur/users.db]

Sicherheitsnetz: bricht ab, wenn die Ziel-Collections bereits befuellt sind
(mirror des alten "seed_db_if_empty"-Verhaltens: bestehende Daten werden nie
ueberschrieben). Mit --force werden die Ziel-Collections vorher geleert.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

from bson import ObjectId

from db_mongo import ensure_indexes, get_db

# Collections, die (statt Auto-Increment) einen natuerlichen String-Schluessel
# als _id verwenden. name/subject/code/token/key.
NATURAL_KEY = {
    "schools": "name",
    "chat_appointments": "subject",
    "invite_codes": "code",
    "api_tokens": "token",
    "app_settings": "key",
}

# Alle Collections, die migriert werden (Reihenfolge egal, IDs werden gemappt).
ALL_TABLES = [
    "users",
    "schools",
    "learning_places",
    "chat_presence",
    "chat_messages",
    "chat_appointments",
    "chat_ratings",
    "chat_message_reports",
    "invite_codes",
    "admin_subject_scores",
    "api_tokens",
    "app_settings",
    "shop_items",
    "teacher_contacts",
    "laden_purchases",
]

# Spalten, die auf users.id zeigen (Fremdschluessel -> users-Map).
USER_FK_COLUMNS = {
    "learning_places": ["user_id"],
    "chat_presence": ["user_id"],
    "chat_messages": ["user_id"],
    "chat_appointments": ["created_by"],
    "chat_ratings": ["user_id"],
    "chat_message_reports": ["reported_user_id", "reporter_user_id", "resolved_by"],
    "invite_codes": ["created_by", "used_user_id"],
    "admin_subject_scores": ["user_id", "updated_by"],
    "laden_purchases": ["user_id"],
}

# Datums-/Zeit-Spalten (TEXT "YYYY-MM-DD HH:MM:SS" -> BSON datetime, UTC).
DATE_COLUMNS = {
    "users": ["created_at"],
    "schools": ["created_at"],
    "learning_places": ["created_at"],
    "chat_presence": ["last_seen"],
    "chat_messages": ["created_at"],
    "chat_appointments": ["created_at", "updated_at", "started_at", "ended_at"],
    "chat_ratings": ["created_at"],
    "chat_message_reports": ["created_at", "resolved_at"],
    "invite_codes": ["created_at", "used_at"],
    "admin_subject_scores": ["updated_at"],
    "api_tokens": ["created_at"],
    "shop_items": ["created_at"],
    "teacher_contacts": ["created_at"],
    "laden_purchases": ["created_at"],
}


def parse_dt(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Unbekanntes Format -> als String belassen, statt Daten zu verlieren.
    return value


def table_exists(cur, name):
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def rows_of(cur, table):
    cur.execute(f"SELECT * FROM {table}")
    cols = [c[0] for c in cur.description]
    for r in cur.fetchall():
        yield dict(zip(cols, r))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    src = args[0] if args else os.path.join(os.path.dirname(__file__), "users.db")
    if not os.path.isfile(src):
        raise SystemExit(f"SQLite-Quelle nicht gefunden: {src}")

    db = get_db()

    # Sicherheitsnetz: nicht ueber bestehende Daten druebermigrieren.
    if not force:
        for table in ALL_TABLES:
            if db[table].estimated_document_count() > 0:
                raise SystemExit(
                    f"Ziel-Collection '{table}' ist nicht leer. Abbruch. "
                    f"Mit --force ueberschreiben."
                )
    else:
        for table in ALL_TABLES:
            db[table].delete_many({})

    conn = sqlite3.connect(src)
    cur = conn.cursor()

    # Phase 1: ID-Maps fuer alle referenzierten Auto-Increment-PKs bauen.
    # users, chat_messages, shop_items werden von anderen Tabellen referenziert.
    id_maps = {"users": {}, "chat_messages": {}, "shop_items": {}}
    for table in id_maps:
        if not table_exists(cur, table):
            continue
        for row in rows_of(cur, table):
            id_maps[table][row["id"]] = ObjectId()

    # Phase 2: Tabellen migrieren.
    for table in ALL_TABLES:
        if not table_exists(cur, table):
            print(f"  (uebersprungen, Tabelle fehlt: {table})")
            continue
        natural = NATURAL_KEY.get(table)
        user_fks = USER_FK_COLUMNS.get(table, [])
        date_cols = DATE_COLUMNS.get(table, [])
        docs = []
        for row in rows_of(cur, table):
            doc = dict(row)

            # _id festlegen.
            if natural:
                doc["_id"] = doc.pop(natural)
            elif table in id_maps:
                doc["_id"] = id_maps[table][doc.pop("id")]
            elif "id" in doc:
                # Tabelle mit Auto-Increment-PK, aber nicht referenziert.
                doc["_id"] = ObjectId()
                doc.pop("id")

            # Fremdschluessel auf users umschreiben.
            for col in user_fks:
                if doc.get(col) is not None:
                    doc[col] = id_maps["users"].get(doc[col])

            # Sonderfaelle: Referenzen auf chat_messages / shop_items.
            if table == "chat_message_reports" and doc.get("message_id") is not None:
                doc["message_id"] = id_maps["chat_messages"].get(doc["message_id"])
            if table == "laden_purchases" and doc.get("shop_item_id") is not None:
                doc["shop_item_id"] = id_maps["shop_items"].get(doc["shop_item_id"])

            # Zeitstempel konvertieren.
            for col in date_cols:
                if col in doc:
                    doc[col] = parse_dt(doc[col])

            docs.append(doc)

        if docs:
            db[table].insert_many(docs)
        print(f"  {table}: {len(docs)} Dokumente")

    conn.close()

    print("Indizes anlegen ...")
    ensure_indexes()
    print("Fertig.")


if __name__ == "__main__":
    main()
