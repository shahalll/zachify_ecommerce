import sys
from werkzeug.security import generate_password_hash
from app import app, db, User, migrate_sqlite_schema, DEFAULT_ADMIN_EMAILS


def set_password(email: str, new_password: str, username: str = None):
    if not email or not new_password:
        print("Usage: python set_password.py <user_email> <new_password> [username]")
        sys.exit(1)

    clean_email = email.strip()

    with app.app_context():
        migrate_sqlite_schema()
        user = User.query.filter(User.email.ilike(clean_email)).first()

        if not user:
            # Auto-create user if not found
            uname = username or clean_email.split("@")[0]
            is_admin = True if clean_email.lower() in {e.lower() for e in DEFAULT_ADMIN_EMAILS} else True
            user = User(
                username=uname,
                email=clean_email,
                password=generate_password_hash(new_password),
                is_admin=is_admin,
            )
            db.session.add(user)
            db.session.commit()
            print(f"Success: User '{user.username}' ({user.email}) created and password set.")
            print(f"Admin Status: {'Admin (is_admin=True)' if user.is_admin else 'Customer (is_admin=False)'}")
            return

        user.password = generate_password_hash(new_password)
        if clean_email.lower() in {e.lower() for e in DEFAULT_ADMIN_EMAILS}:
            user.is_admin = True
        db.session.commit()
        print(f"Success: Password updated successfully for '{user.username}' ({user.email}).")
        print(f"Admin Status: {'Admin (is_admin=True)' if user.is_admin else 'Customer (is_admin=False)'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python set_password.py <user_email> <new_password> [username]")
        print("Example: python set_password.py mhdshahal3182005@gmail.com shahal123")
        sys.exit(1)

    target_email = sys.argv[1]
    new_pass = sys.argv[2]
    uname = sys.argv[3] if len(sys.argv) > 3 else None
    set_password(target_email, new_pass, uname)
