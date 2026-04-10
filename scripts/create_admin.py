import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, engine, Base
from models.core import AdminUser
from services import auth_utils


def create_admin(email, password):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_user = db.query(AdminUser).filter(AdminUser.email == email).first()
        if existing_user:
            print(f"User {email} already exists.")
            return

        hashed_pwd = auth_utils.get_password_hash(password)
        new_admin = AdminUser(email=email, hashed_password=hashed_pwd, is_active=True)
        db.add(new_admin)
        db.commit()
        print(f"Admin user {email} created successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <email> <password>")
    else:
        create_admin(sys.argv[1], sys.argv[2])
