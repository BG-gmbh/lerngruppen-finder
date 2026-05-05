"""
Setzt die Rolle eines bestehenden Nutzers auf 'admin'.

Aufruf (im Projektordner, venv aktiv oder mit system-python3):

  python promote_admin.py DEIN_BENUTZERNAME

Danach neu einloggen (Session kennt die alte Rolle noch, bis Logout/Login).
"""
import os
import sqlite3
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python promote_admin.py USERNAME", file=sys.stderr)
        sys.exit(2)
    username = sys.argv[1].strip()
    if not username:
        print("Username empty.", file=sys.stderr)
        sys.exit(2)

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
    if not os.path.isfile(db_path):
        print(f"No database at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE users SET role = 'admin' WHERE username = ?",
            (username,),
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
    print(f"OK: {username!r} is now admin. Log out in the browser, then log in again.")
    sys.exit(0)


if __name__ == "__main__":
    main()
