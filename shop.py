"""Shop-Modul (Laden): Artikel, Punktekäufe, Lehrer-E-Mail-Benachrichtigungen."""

import sqlite3

from flask import jsonify, request, send_from_directory, session

from mailer import send_smtp_mail, smtp_configured

TITLE_MAX = 200
DESC_MAX = 4000
PRICE_MAX = 120
POINTS_PRICE_MAX = 1_000_000
SCHOOL_MAX = 120
CLASS_MAX = 20


def ensure_shop_table(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price_hint TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur = db.execute("PRAGMA table_info(shop_items)")
    cols = {row[1] for row in cur.fetchall()}
    if "points_price" not in cols:
        db.execute(
            "ALTER TABLE shop_items ADD COLUMN points_price INTEGER NOT NULL DEFAULT 0"
        )
    if "school" not in cols:
        db.execute("ALTER TABLE shop_items ADD COLUMN school TEXT NOT NULL DEFAULT ''")
    if "class_name" not in cols:
        db.execute(
            "ALTER TABLE shop_items ADD COLUMN class_name TEXT NOT NULL DEFAULT ''"
        )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            display_name TEXT,
            school TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur = db.execute("PRAGMA table_info(teacher_contacts)")
    teacher_cols = {row[1] for row in cur.fetchall()}
    if "school" not in teacher_cols:
        db.execute(
            "ALTER TABLE teacher_contacts ADD COLUMN school TEXT NOT NULL DEFAULT ''"
        )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS laden_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            shop_item_id INTEGER NOT NULL,
            item_title TEXT NOT NULL,
            points_spent INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            email_sent INTEGER NOT NULL DEFAULT 0,
            email_error TEXT
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_laden_purchases_created
        ON laden_purchases (created_at)
        """
    )
    db.commit()


def _is_dev():
    return session.get("role") == "dev"


def _session_school(db):
    if "school" in session:
        return session.get("school") or ""
    uid = session.get("user_id")
    if not uid:
        return ""
    row = db.execute("SELECT school FROM users WHERE id = ?", (uid,)).fetchone()
    school = (row["school"] if row else "") or ""
    session["school"] = school
    return school


def _admin_item_school(db, raw_school):
    school = (raw_school or "").strip()
    return school if _is_dev() else _session_school(db)


def _normalize_class_name(raw):
    class_name = (raw or "").strip()
    if len(class_name) > CLASS_MAX:
        return None
    return class_name


def _can_admin_access_school(db, school):
    return _is_dev() or (school or "") == _session_school(db)


def _user_points_sum(db, user_id):
    r = db.execute(
        """
        SELECT COALESCE(SUM(points), 0) AS s
        FROM admin_subject_scores
        WHERE user_id = ? AND subject IN ('german', 'math', 'english', 'biology', 'pgw', 'spanish', 'art')
        """,
        (user_id,),
    ).fetchone()
    return int(r["s"])


def _deduct_user_points(db, user_id, amount, actor_user_id):
    """Zieht Punkte von positiven admin_subject_scores-Zeilen ab. actor_user_id für updated_by."""
    remaining = amount
    rows = db.execute(
        """
        SELECT subject, points FROM admin_subject_scores
        WHERE user_id = ? AND points > 0 AND subject IN ('german', 'math', 'english', 'biology', 'pgw', 'spanish', 'art')
        ORDER BY subject
        """,
        (user_id,),
    ).fetchall()
    now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
    for row in rows:
        if remaining <= 0:
            break
        p = int(row["points"])
        take = min(p, remaining)
        newp = p - take
        db.execute(
            """
            UPDATE admin_subject_scores
            SET points = ?, updated_at = ?, updated_by = ?
            WHERE user_id = ? AND subject = ?
            """,
            (newp, now, actor_user_id, user_id, row["subject"]),
        )
        remaining -= take
    return remaining == 0


def _purchase_email_notice(mail_err):
    """Deutschsprachiger Hinweis für die Kauf-Bestätigung (keine internen Codes)."""
    if not mail_err:
        return None
    # Kurz halten: Erfolg („gespeichert“ / Punkte) steht schon im Shop-Dialog.
    mapping = {
        "smtp_not_configured": "Lehrer-E-Mail: SMTP ist noch nicht eingerichtet (.env / README).",
        "no_teachers": "Lehrer-E-Mail: keine Benachrichtigungsadresse hinterlegt (Admin).",
        "no_recipients": "Lehrer-E-Mail: keine gültigen Empfänger.",
        "smtp_no_from": "Lehrer-E-Mail: Absender (SMTP_FROM / SMTP_USER) fehlt.",
        "send_failed": "Lehrer-E-Mail konnte nicht gesendet werden.",
    }
    if mail_err in mapping:
        return mapping[mail_err]
    return "Lehrer-E-Mail konnte nicht gesendet werden."


def _notify_teachers_laden(
    db, student_username, item_title, points_spent, created_at, student_school
):
    seen = set()
    emails = []
    for r in db.execute(
        """
        SELECT email FROM teacher_contacts
        WHERE active = 1 AND TRIM(email) != ''
          AND (TRIM(school) = '' OR school = ?)
        ORDER BY id ASC
        """,
        (student_school or "",),
    ).fetchall():
        raw = (r["email"] or "").strip()
        low = raw.lower()
        if raw and "@" in raw and low not in seen:
            seen.add(low)
            emails.append(raw)
    for r in db.execute(
        """
        SELECT contact_email FROM users
        WHERE notify_laden_email = 1
          AND school = ?
          AND contact_email IS NOT NULL
          AND TRIM(contact_email) != ''
        """,
        (student_school or "",),
    ).fetchall():
        raw = (r["contact_email"] or "").strip()
        low = raw.lower()
        if raw and "@" in raw and low not in seen:
            seen.add(low)
            emails.append(raw)
    if not emails:
        return False, "no_teachers"
    subject = f"Laden: {student_username} hat Punkte ausgegeben"
    body = (
        f"Schüler/in (Nutzername): {student_username}\n"
        f"Artikel: {item_title}\n"
        f"Punkte: {points_spent}\n"
        f"Zeitpunkt: {created_at}\n\n"
        f"(Automatische Nachricht vom Lerngruppen-Finder.)\n"
    )
    ok, err = send_smtp_mail(emails, subject, body)
    if not ok:
        return False, err or "send_failed"
    return True, None


def _row_to_item(r):
    try:
        pp = int(r["points_price"])
    except (KeyError, TypeError, ValueError):
        pp = 0
    return {
        "id": r["id"],
        "title": r["title"],
        "description": r["description"] or "",
        "price_hint": r["price_hint"] or "",
        "points_price": pp,
        "school": r["school"] or "",
        "class_name": r["class_name"] or "",
        "sort_order": int(r["sort_order"]),
        "active": bool(r["active"]),
        "updated_at": r["updated_at"],
    }


def register_shop_routes(app, get_db, admin_api, login_required, login_required_api):
    @app.route("/laden.html")
    @login_required
    def laden_page():
        return send_from_directory(app.static_folder, "shop.html")

    @app.route("/shop.html")
    @login_required
    def shop_page():
        return send_from_directory(app.static_folder, "shop.html")

    @app.route("/api/shop", methods=["GET"])
    @login_required_api
    def api_shop_public():
        db = get_db()
        uid = session["user_id"]
        user_row = db.execute(
            "SELECT school, class_name FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        user_school = (user_row["school"] if user_row else "") or ""
        user_class = (user_row["class_name"] if user_row else "") or ""
        rows = db.execute(
            """
            SELECT id, title, description, price_hint, points_price, school, class_name, sort_order, active, updated_at
            FROM shop_items
            WHERE active = 1
              AND (trim(school) = '' OR school = ?)
              AND (trim(class_name) = '' OR class_name = ?)
            ORDER BY sort_order ASC, id ASC
            """,
            (user_school, user_class),
        ).fetchall()
        bal = _user_points_sum(db, uid)
        db.commit()
        return jsonify(
            items=[_row_to_item(r) for r in rows],
            points_balance=bal,
            smtp_configured=smtp_configured(),
        )

    @app.route("/api/shop/purchase", methods=["POST"])
    @login_required_api
    def api_shop_purchase():
        data = request.get_json(silent=True) or {}
        try:
            item_id = int(data.get("item_id"))
        except (TypeError, ValueError):
            return jsonify(error="invalid_item"), 400

        db = get_db()
        uid = session["user_id"]
        uname = session.get("username") or ""

        row = db.execute(
            """
            SELECT id, title, points_price, school, class_name, active FROM shop_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        if not row or not row["active"]:
            db.commit()
            return jsonify(error="not_found"), 404
        user_row = db.execute(
            "SELECT school, class_name FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        user_school = (user_row["school"] if user_row else "") or ""
        user_class = (user_row["class_name"] if user_row else "") or ""
        item_school = (row["school"] or "").strip()
        item_class = (row["class_name"] or "").strip()
        if item_school and item_school != user_school:
            db.commit()
            return jsonify(error="not_found"), 404
        if item_class and item_class != user_class:
            db.commit()
            return jsonify(error="not_found"), 404
        cost = int(row["points_price"] or 0)
        if cost <= 0:
            db.commit()
            return jsonify(error="not_purchasable"), 400

        try:
            db.execute("BEGIN IMMEDIATE")
            bal = _user_points_sum(db, uid)
            if bal < cost:
                db.rollback()
                return jsonify(error="insufficient_points", balance=bal, cost=cost), 400
            if not _deduct_user_points(db, uid, cost, uid):
                db.rollback()
                return jsonify(error="deduct_failed"), 500
            now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
            db.execute(
                """
                INSERT INTO laden_purchases
                (user_id, username, shop_item_id, item_title, points_spent, created_at, email_sent, email_error)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (uid, uname, item_id, row["title"], cost, now),
            )
            pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()
        except sqlite3.Error:
            db.rollback()
            try:
                db.commit()
            except sqlite3.Error:
                pass
            return jsonify(error="database"), 500

        mail_ok = False
        mail_err = None
        try:
            sent, merr = _notify_teachers_laden(
                db, uname, row["title"], cost, now, user_school
            )
            mail_ok = bool(sent)
            mail_err = merr
        except OSError as ex:
            mail_err = str(ex)[:200]
        db.execute(
            """
            UPDATE laden_purchases
            SET email_sent = ?, email_error = ?
            WHERE id = ?
            """,
            (1 if mail_ok else 0, mail_err, pid),
        )
        db.commit()

        new_bal = _user_points_sum(db, uid)
        db.commit()
        return jsonify(
            ok=True,
            points_balance=new_bal,
            mail_sent=mail_ok,
            mail_notice=_purchase_email_notice(mail_err) if not mail_ok else None,
        )

    @app.route("/api/admin/shop", methods=["GET"])
    @admin_api
    def admin_shop_list():
        db = get_db()
        where = ""
        params = []
        if not _is_dev():
            where = "WHERE school = ?"
            params.append(_session_school(db))
        rows = db.execute(
            f"""
            SELECT id, title, description, price_hint, points_price, school, class_name, sort_order, active, updated_at
            FROM shop_items
            {where}
            ORDER BY sort_order ASC, id ASC
            """,
            params,
        ).fetchall()
        return jsonify(items=[_row_to_item(r) for r in rows])

    @app.route("/api/admin/shop", methods=["POST"])
    @admin_api
    def admin_shop_create():
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title or len(title) > TITLE_MAX:
            return jsonify(error="invalid_title"), 400
        description = (data.get("description") or "").strip()
        if len(description) > DESC_MAX:
            return jsonify(error="invalid_description"), 400
        price_hint = (data.get("price_hint") or "").strip()
        if len(price_hint) > PRICE_MAX:
            return jsonify(error="invalid_price_hint"), 400
        db = get_db()
        school = _admin_item_school(db, data.get("school"))
        if len(school) > SCHOOL_MAX:
            return jsonify(error="invalid_school"), 400
        class_name = _normalize_class_name(data.get("class_name"))
        if class_name is None:
            return jsonify(error="invalid_class"), 400
        try:
            points_price = int(data.get("points_price", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_points_price"), 400
        if points_price < 0 or points_price > POINTS_PRICE_MAX:
            return jsonify(error="invalid_points_price"), 400
        try:
            sort_order = int(data.get("sort_order", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_sort"), 400
        active = 1 if data.get("active") in (True, "true", "1", 1) else 0

        now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
        cur = db.execute(
            """
            INSERT INTO shop_items (title, description, price_hint, points_price, school, class_name, sort_order, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                price_hint,
                points_price,
                school,
                class_name,
                sort_order,
                active,
                now,
            ),
        )
        if school:
            db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
        db.commit()
        new_id = cur.lastrowid
        row = db.execute(
            """
            SELECT id, title, description, price_hint, points_price, school, class_name, sort_order, active, updated_at
            FROM shop_items WHERE id = ?
            """,
            (new_id,),
        ).fetchone()
        return jsonify(item=_row_to_item(row))

    @app.route("/api/admin/shop/<int:item_id>", methods=["PUT"])
    @admin_api
    def admin_shop_update(item_id):
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title or len(title) > TITLE_MAX:
            return jsonify(error="invalid_title"), 400
        description = (data.get("description") or "").strip()
        if len(description) > DESC_MAX:
            return jsonify(error="invalid_description"), 400
        price_hint = (data.get("price_hint") or "").strip()
        if len(price_hint) > PRICE_MAX:
            return jsonify(error="invalid_price_hint"), 400
        db = get_db()
        school = _admin_item_school(db, data.get("school"))
        if len(school) > SCHOOL_MAX:
            return jsonify(error="invalid_school"), 400
        class_name = _normalize_class_name(data.get("class_name"))
        if class_name is None:
            return jsonify(error="invalid_class"), 400
        try:
            points_price = int(data.get("points_price", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_points_price"), 400
        if points_price < 0 or points_price > POINTS_PRICE_MAX:
            return jsonify(error="invalid_points_price"), 400
        try:
            sort_order = int(data.get("sort_order", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_sort"), 400
        active = 1 if data.get("active") in (True, "true", "1", 1) else 0

        existing = db.execute(
            "SELECT school FROM shop_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if existing is None:
            db.commit()
            return jsonify(error="not_found"), 404
        if not _can_admin_access_school(db, existing["school"] or ""):
            db.commit()
            return jsonify(error="not_found"), 404
        now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
        cur = db.execute(
            """
            UPDATE shop_items
            SET title = ?, description = ?, price_hint = ?, points_price = ?, school = ?, class_name = ?, sort_order = ?, active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                description,
                price_hint,
                points_price,
                school,
                class_name,
                sort_order,
                active,
                now,
                item_id,
            ),
        )
        if school:
            db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        row = db.execute(
            """
            SELECT id, title, description, price_hint, points_price, school, class_name, sort_order, active, updated_at
            FROM shop_items WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        return jsonify(item=_row_to_item(row))

    @app.route("/api/admin/shop/<int:item_id>", methods=["DELETE"])
    @admin_api
    def admin_shop_delete(item_id):
        db = get_db()
        existing = db.execute(
            "SELECT school FROM shop_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if existing is None or not _can_admin_access_school(db, existing["school"] or ""):
            db.commit()
            return jsonify(error="not_found"), 404
        cur = db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        return jsonify(ok=True)

    @app.route("/api/admin/laden-purchases", methods=["GET"])
    @admin_api
    def admin_laden_purchases():
        db = get_db()
        school_filter = ""
        params = []
        if not _is_dev():
            school_filter = "WHERE u.school = ?"
            params.append(_session_school(db))
        rows = db.execute(
            f"""
            SELECT p.id, p.user_id, p.username, p.shop_item_id, p.item_title,
                   p.points_spent, p.created_at, p.email_sent, p.email_error
            FROM laden_purchases p
            JOIN users u ON u.id = p.user_id
            {school_filter}
            ORDER BY datetime(p.created_at) DESC, p.id DESC
            LIMIT 300
            """,
            params,
        ).fetchall()
        return jsonify(
            purchases=[
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "username": r["username"],
                    "shop_item_id": r["shop_item_id"],
                    "item_title": r["item_title"],
                    "points_spent": int(r["points_spent"]),
                    "created_at": r["created_at"],
                    "email_sent": bool(r["email_sent"]),
                    "email_error": r["email_error"] or "",
                }
                for r in rows
            ]
        )

    @app.route("/api/admin/teachers", methods=["GET"])
    @admin_api
    def admin_teachers_list():
        db = get_db()
        where = ""
        params = []
        if not _is_dev():
            where = "WHERE school = ?"
            params.append(_session_school(db))
        rows = db.execute(
            f"""
            SELECT id, email, display_name, school, active, created_at
            FROM teacher_contacts
            {where}
            ORDER BY id ASC
            """,
            params,
        ).fetchall()
        return jsonify(
            teachers=[
                {
                    "id": r["id"],
                    "email": r["email"],
                    "display_name": r["display_name"] or "",
                    "school": r["school"] or "",
                    "active": bool(r["active"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        )

    @app.route("/api/admin/teachers", methods=["POST"])
    @admin_api
    def admin_teachers_create():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        display_name = (data.get("display_name") or "").strip()[:120]
        if not email or "@" not in email or len(email) > 254:
            return jsonify(error="invalid_email"), 400
        db = get_db()
        school = _admin_item_school(db, data.get("school"))
        dup = db.execute(
            "SELECT id FROM teacher_contacts WHERE lower(trim(email)) = ?",
            (email,),
        ).fetchone()
        if dup:
            return jsonify(error="duplicate"), 409
        db.execute(
            """
            INSERT INTO teacher_contacts (email, display_name, school, active)
            VALUES (?, ?, ?, 1)
            """,
            (email, display_name or None, school),
        )
        if school:
            db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
        db.commit()
        rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = db.execute(
            "SELECT id, email, display_name, school, active, created_at FROM teacher_contacts WHERE id = ?",
            (rid,),
        ).fetchone()
        return jsonify(
            teacher={
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"] or "",
                "school": row["school"] or "",
                "active": bool(row["active"]),
                "created_at": row["created_at"],
            }
        )

    @app.route("/api/admin/teachers/<int:tid>", methods=["DELETE"])
    @admin_api
    def admin_teachers_delete(tid):
        db = get_db()
        existing = db.execute(
            "SELECT school FROM teacher_contacts WHERE id = ?",
            (tid,),
        ).fetchone()
        if existing is None or not _can_admin_access_school(db, existing["school"] or ""):
            db.commit()
            return jsonify(error="not_found"), 404
        cur = db.execute("DELETE FROM teacher_contacts WHERE id = ?", (tid,))
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        return jsonify(ok=True)

    @app.route("/api/admin/teachers/<int:tid>", methods=["PUT"])
    @admin_api
    def admin_teachers_update(tid):
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        display_name = (data.get("display_name") or "").strip()[:120]
        active = 1 if data.get("active") in (True, "true", "1", 1) else 0
        if not email or "@" not in email or len(email) > 254:
            return jsonify(error="invalid_email"), 400
        db = get_db()
        school = _admin_item_school(db, data.get("school"))
        existing = db.execute(
            "SELECT school FROM teacher_contacts WHERE id = ?",
            (tid,),
        ).fetchone()
        if existing is None or not _can_admin_access_school(db, existing["school"] or ""):
            db.commit()
            return jsonify(error="not_found"), 404
        cur = db.execute(
            """
            UPDATE teacher_contacts
            SET email = ?, display_name = ?, school = ?, active = ?
            WHERE id = ?
            """,
            (email, display_name or None, school, active, tid),
        )
        if school:
            db.execute("INSERT OR IGNORE INTO schools (name) VALUES (?)", (school,))
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        row = db.execute(
            "SELECT id, email, display_name, school, active, created_at FROM teacher_contacts WHERE id = ?",
            (tid,),
        ).fetchone()
        return jsonify(
            teacher={
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"] or "",
                "school": row["school"] or "",
                "active": bool(row["active"]),
                "created_at": row["created_at"],
            }
        )
