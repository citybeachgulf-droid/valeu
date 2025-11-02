from extensions import db
from app import User, app
from werkzeug.security import generate_password_hash

with app.app_context():
    # إنشاء الجداول
    db.create_all()

    # إضافة مستخدمين افتراضيين إذا ما كانوا موجودين
    if not User.query.filter_by(username="manager").first():
        manager  = User(username="manager", password=generate_password_hash("admin"), role="manager")
        employee = User(username="employee", password=generate_password_hash("123"), role="employee")
        visit    = User(username="visit", password=generate_password_hash("456"), role="visit")
        engineer = User(username="engineer", password=generate_password_hash("789"), role="engineer")
        finance  = User(username="finance", password=generate_password_hash("000"), role="finance")
        hr_user  = User(username="hr", password=generate_password_hash("hr123"), role="hr")

        db.session.add_all([manager, employee, visit, engineer, finance, hr_user])
        db.session.commit()
        print("✅ Database initialized with default users")
    else:
        print("ℹ️ Database already initialized")
