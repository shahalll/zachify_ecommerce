import sys
from app import app, db, User, migrate_sqlite_schema


def make_admin(email: str):
    if not email or not email.strip():
        print("Usage: python make_admin.py <user_email>")
        sys.exit(1)

    clean_email = email.strip().lower()

    with app.app_context():
        migrate_sqlite_schema()
        user = User.query.filter(User.email.ilike(clean_email)).first()

        if not user:
            print(f"Error: No user found with email '{email}'.")
            sys.exit(1)

        user.is_admin = True
        db.session.commit()
        print(f"Success: User '{user.username}' ({user.email}) is now an administrator (is_admin=True).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <user_email>")
        print("Example: python make_admin.py anu123@gmail.com")
        sys.exit(1)

    target_email = sys.argv[1]
    make_admin(target_email)
