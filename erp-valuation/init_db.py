from app import db, User, app

with app.app_context():
    # إنشاء الجداول
    db.create_all()

    # إضافة مستخدمين افتراضيين إذا ما كانوا موجودين
    if not User.query.filter_by(username="manager").first():
        manager  = User(username="manager", password="admin", role="manager")
        employee = User(username="employee", password="123", role="employee")
        visit    = User(username="visit", password="456", role="visit")
        engineer = User(username="engineer", password="789", role="engineer")
        finance  = User(username="finance", password="000", role="finance")

        db.session.add_all([manager, employee, visit, engineer, finance])
        db.session.commit()
        print("✅ Database initialized with default users")
    else:
        print("ℹ️ Database already initialized")
