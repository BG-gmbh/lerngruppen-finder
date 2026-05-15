"""
Setzt die Rolle eines bestehenden Nutzers auf 'admin' oder 'dev'.

Aufruf (im Projektordner, venv aktiv oder mit system-python3):

  python promote_admin.py DEIN_BENUTZERNAME [admin|dev]

Danach neu einloggen (Session kennt die alte Rolle noch, bis Logout/Login).
"""
import os
import sqlite3
import sys

def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python promote_admin.py USERNAME [admin|dev]", file=sys.stderr)
        sys.exit(2)
    username = sys.argv[1].strip()
    role = sys.argv[2].strip() if len(sys.argv) == 3 else "admin"
    if not username:
        print("Username empty.", file=sys.stderr)
        sys.exit(2)
    if role not in ("admin", "dev"):
        print("Role must be 'admin' or 'dev'.", file=sys.stderr)
        sys.exit(2)

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
    if not os.path.isfile(db_path):
        print(f"No database at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (role, username),
        )
        conn.commit()
        n = cur.rowcount
    finally:
        conn.close()

    if n == 0:
        print("No user with that username. List users:")
        c2 = sqlite3.connect(db_path)
        try:
            for row in c2.execute("SELECT id, username, role FROM users"):
                print(f"  id={row[0]}  username={row[1]!r}  role={row[2]!r}")
        finally:
            c2.close()
        sys.exit(1)
    print(f"OK: {username!r} is now {role}. Log out in the browser, then log in again.")
    sys.exit(0)


if __name__ == "__main__":
    main()
