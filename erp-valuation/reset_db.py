from extensions import db
from app import app, User
from werkzeug.security import generate_password_hash

with app.app_context():
    try:
        db.drop_all()
        db.create_all()
    except Exception as e:
        print("DB INIT ERROR:", e)
    else:
        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            role="manager",
            branch_id=None,
        )
        db.session.add(admin)
        db.session.commit()
        print("Database reset with a fresh admin user")
