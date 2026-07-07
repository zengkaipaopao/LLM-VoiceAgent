"""Create or update a local administrative user."""

import argparse
import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.auth import AdminUser
from app.services.auth.providers import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local VoiceDesk administrator.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="")
    args = parser.parse_args()

    username = args.username.strip().lower()
    if len(username) < 3:
        raise SystemExit("Username must contain at least 3 characters.")
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")

    with SessionLocal() as db:
        user = db.execute(
            select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()
        if user is None:
            user = AdminUser(
                username=username,
                display_name=args.display_name.strip() or username,
                auth_provider="local",
                role="admin",
                is_active=True,
            )
            db.add(user)
        user.password_hash = hash_password(password)
        user.display_name = args.display_name.strip() or user.display_name
        user.auth_provider = "local"
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    print(f"Administrative user '{username}' is ready.")


if __name__ == "__main__":
    main()
