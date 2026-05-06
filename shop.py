"""Shop-Modul: Angebote in SQLite, im Admin-Panel pflegbar, für eingeloggte Nutzer unter /shop.html."""

from flask import jsonify, request, send_from_directory

TITLE_MAX = 200
DESC_MAX = 4000
PRICE_MAX = 120


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
    db.commit()


def _row_to_item(r):
    return {
        "id": r["id"],
        "title": r["title"],
        "description": r["description"] or "",
        "price_hint": r["price_hint"] or "",
        "sort_order": int(r["sort_order"]),
        "active": bool(r["active"]),
        "updated_at": r["updated_at"],
    }


def register_shop_routes(app, get_db, admin_api, login_required, login_required_api):
    @app.route("/shop.html")
    @login_required
    def shop_page():
        return send_from_directory(app.static_folder, "shop.html")

    @app.route("/api/shop", methods=["GET"])
    @login_required_api
    def api_shop_public():
        db = get_db()
        rows = db.execute(
            """
            SELECT id, title, description, price_hint, sort_order, active, updated_at
            FROM shop_items
            WHERE active = 1
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()
        return jsonify(items=[_row_to_item(r) for r in rows])

    @app.route("/api/admin/shop", methods=["GET"])
    @admin_api
    def admin_shop_list():
        db = get_db()
        rows = db.execute(
            """
            SELECT id, title, description, price_hint, sort_order, active, updated_at
            FROM shop_items
            ORDER BY sort_order ASC, id ASC
            """
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
        try:
            sort_order = int(data.get("sort_order", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_sort"), 400
        active = 1 if data.get("active") in (True, "true", "1", 1) else 0

        db = get_db()
        now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
        cur = db.execute(
            """
            INSERT INTO shop_items (title, description, price_hint, sort_order, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, price_hint, sort_order, active, now),
        )
        db.commit()
        new_id = cur.lastrowid
        row = db.execute(
            """
            SELECT id, title, description, price_hint, sort_order, active, updated_at
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
        try:
            sort_order = int(data.get("sort_order", 0))
        except (TypeError, ValueError):
            return jsonify(error="invalid_sort"), 400
        active = 1 if data.get("active") in (True, "true", "1", 1) else 0

        db = get_db()
        now = db.execute("SELECT datetime('now') AS now").fetchone()["now"]
        cur = db.execute(
            """
            UPDATE shop_items
            SET title = ?, description = ?, price_hint = ?, sort_order = ?, active = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, description, price_hint, sort_order, active, now, item_id),
        )
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        row = db.execute(
            """
            SELECT id, title, description, price_hint, sort_order, active, updated_at
            FROM shop_items WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        return jsonify(item=_row_to_item(row))

    @app.route("/api/admin/shop/<int:item_id>", methods=["DELETE"])
    @admin_api
    def admin_shop_delete(item_id):
        db = get_db()
        cur = db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
        if cur.rowcount != 1:
            db.commit()
            return jsonify(error="not_found"), 404
        db.commit()
        return jsonify(ok=True)
