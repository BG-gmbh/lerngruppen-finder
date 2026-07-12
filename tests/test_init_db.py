"""Unit-Tests fuer die MongoDB-Umstellung (keine DB-Verbindung noetig).

Der fruehere SQLite-Schema-/Migrationstest ist obsolet: init_db() legt jetzt nur
noch MongoDB-Indizes an (ensure_indexes()). Diese Tests pruefen die reinen
Hilfsfunktionen der neuen Datenschicht ohne laufende Datenbank.
"""

import app as app_module
from db_mongo import oid
from bson import ObjectId


def test_new_user_defaults_has_full_schema_field_set():
    d = app_module._new_user_defaults()
    # Felder, die unter SQLite NOT NULL DEFAULT-Werte hatten, muessen vorhanden
    # sein, damit row["feld"]-Zugriffe unter MongoDB kein KeyError werfen.
    for field in (
        "role", "display_name", "onboarded", "banned", "banned_message",
        "school", "class_name", "notify_laden_email", "avatar_url", "iserv_email",
    ):
        assert field in d
    # Alle Fach-Level und Verifizierungsflags sind gesetzt.
    for col in app_module.CHAT_LEVEL_COLUMN.values():
        assert d[col] == "noob"
    for col in app_module.CHAT_VERIFIED_COLUMN.values():
        assert d[col] == 0


def test_oid_parses_valid_and_rejects_invalid():
    real = ObjectId()
    assert oid(str(real)) == real
    assert oid(real) == real
    assert oid("not-an-objectid") is None
    assert oid("") is None
    assert oid(None) is None
