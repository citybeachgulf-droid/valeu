from app import db, app, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()   # يحذف كل الجداول
    db.create_all() # ينشئها من جديد

    # إضافة مدير افتراضي
    admin = User(
        username="admin",
        password=generate_password_hash("admin123"),
        role="manager",
        branch_id=None
    )
    db.session.add(admin)
    db.session.commit()
    print("✅ قاعدة البيانات أُعيد إنشاؤها بنجاح")
