import sys
from werkzeug.security import generate_password_hash
from app import app, db, User, migrate_sqlite_schema


def set_password(email: str, new_password: str):
    if not email or not new_password:
        print("Usage: python set_password.py <user_email> <new_password>")
        sys.exit(1)

    clean_email = email.strip()

    with app.app_context():
        migrate_sqlite_schema()
        user = User.query.filter(User.email.ilike(clean_email)).first()

        if not user:
            print(f"Error: No user found with email '{email}'.")
            print("\nAvailable registered users in database:")
            for u in User.query.all():
                print(f"  - Username: {u.username}, Email: {u.email}, is_admin: {u.is_admin}")
            sys.exit(1)

        user.password = generate_password_hash(new_password)
        db.session.commit()
        print(f"Success: Password updated successfully for '{user.username}' ({user.email}).")
        print(f"Admin Status: {'Admin (is_admin=True)' if user.is_admin else 'Customer (is_admin=False)'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python set_password.py <user_email> <new_password>")
        print("Example: python set_password.py admin@example.com myNewPass123")
        sys.exit(1)

    target_email = sys.argv[1]
    new_pass = sys.argv[2]
    set_password(target_email, new_pass)
