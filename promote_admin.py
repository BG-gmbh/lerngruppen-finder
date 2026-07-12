"""
Setzt die Rolle eines bestehenden Nutzers auf 'admin' oder 'dev'.

Aufruf (im Projektordner, mit gesetzter MONGODB_URI):

  MONGODB_URI="mongodb+srv://..." python promote_admin.py DEIN_BENUTZERNAME [admin|dev]

Danach neu einloggen (Session kennt die alte Rolle noch, bis Logout/Login).
"""
import sys

from db_mongo import get_db


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python promote_admin.py USERNAME [user|teacher|admin|dev]", file=sys.stderr)
        sys.exit(2)
    username = sys.argv[1].strip()
    role = sys.argv[2].strip() if len(sys.argv) == 3 else "admin"
    if not username:
        print("Username empty.", file=sys.stderr)
        sys.exit(2)
    if role not in ("user", "teacher", "admin", "dev"):
        print("Role must be 'user', 'teacher', 'admin' or 'dev'.", file=sys.stderr)
        sys.exit(2)

    db = get_db()
    result = db.users.update_one({"username": username}, {"$set": {"role": role}})

    if result.matched_count == 0:
        print("No user with that username. List users:")
        for row in db.users.find({}, {"username": 1, "role": 1}):
            print(f"  id={row['_id']}  username={row.get('username')!r}  role={row.get('role')!r}")
        sys.exit(1)
    print(f"OK: {username!r} is now {role}. Log out in the browser, then log in again.")
    sys.exit(0)


if __name__ == "__main__":
    main()
