from operator import and_
import os, json, re
from datetime import datetime, timedelta, date
import fitz  # PyMuPDF (kept to preserve functionality if used in templates/utilities)
import pytesseract  # OCR (kept to preserve functionality if used elsewhere)
from PIL import Image  # Image handling (kept)
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_, text
from sqlalchemy.exc import OperationalError
from pywebpush import webpush, WebPushException
from docx import Document
from pdf_templates import create_pdf

# ---------------- إعداد Flask ----------------
app = Flask(__name__)
app.secret_key = "secret_key"

# ---------------- إعداد الملفات ----------------
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- إعداد مفاتيح Web Push (VAPID) ----------------
# يمكن ضبطها عبر متغيرات البيئة VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT
app.config["VAPID_PUBLIC_KEY"] = os.environ.get(
    "VAPID_PUBLIC_KEY",
    app.config.get("VAPID_PUBLIC_KEY") or "BFNeZpjEro8pwFxR1H20twlTd2pL5MZtWrDATu4ME2RcbzhN"
)
app.config["VAPID_PRIVATE_KEY"] = os.environ.get("VAPID_PRIVATE_KEY", app.config.get("VAPID_PRIVATE_KEY"))
app.config["VAPID_CLAIMS"] = {
    "sub": os.environ.get("VAPID_SUBJECT", "mailto:your-email@example.com")
}

# ---------------- إعداد قاعدة البيانات ----------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///erp.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
def generate_verification_token() -> str:
    import secrets
    return secrets.token_hex(16)

# -------- أدوات مساعدة للأرقام (تقبل أرقام عربية وفواصل) --------
def parse_float_input(value) -> float:
    """تحويل مدخل نصي إلى رقم عشري مع دعم الأرقام العربية والفواصل.

    أمثلة مدعومة:
    "12,345.67"  "12.345,67"  "١٢٣٤٥٫٦٧"  "١٢٬٣٤٥٫٦٧"
    تعاد 0.0 في حال الفشل.
    """
    if value is None:
        return 0.0
    try:
        s = str(value).strip()
        if not s:
            return 0.0
        # خريطة الأرقام العربية إلى الإنجليزية
        arabic_to_ascii = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        s = s.translate(arabic_to_ascii)
        # رموز الفواصل العربية
        arabic_thousands = "\u066C"  # ٬
        arabic_decimal   = "\u066B"  # ٫
        # إزالة المسافات وأنواع المسافات غير القابلة للكسر
        s = s.replace(" ", "").replace("\u00A0", "").replace("\u202F", "")
        # أزل فواصل الآلاف (عربية أو إنجليزية)
        s = s.replace(",", "").replace(arabic_thousands, "")
        # وحّد الفاصلة العشرية إلى نقطة
        s = s.replace(arabic_decimal, ".")
        return float(s)
    except Exception:
        return 0.0


# ---------------- النماذج ----------------
class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    users = db.relationship("User", backref="branch", lazy=True)
    transactions = db.relationship("Transaction", backref="branch", lazy=True)

class Bank(db.Model):
    __tablename__ = "bank"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    # علاقة واحدة فقط، وما نكررها في Transaction
    transactions = db.relationship("Transaction", backref="bank", lazy=True)

class User(db.Model):
    __tablename__ = "user"
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role     = db.Column(db.String(20), nullable=False)  # manager/employee/visit/engineer/finance
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)

class Transaction(db.Model):
    __tablename__ = "transaction"
    id              = db.Column(db.Integer, primary_key=True)
    client          = db.Column(db.String(100))
    employee        = db.Column(db.String(50))
    date            = db.Column(db.DateTime, default=datetime.utcnow)
    status          = db.Column(db.String(30), default="معلقة")
    fee             = db.Column(db.Float, default=0)
    land_value      = db.Column(db.Float, default=0)
    building_value  = db.Column(db.Float, default=0)
    total_estimate  = db.Column(db.Float, default=0)
    files           = db.Column(db.Text)
    # ملفات أُرسلت للبنك بواسطة الموظف (قائمة أسماء مفصولة بفواصل)
    bank_sent_files = db.Column(db.Text)
    area            = db.Column(db.Float, default=0)
    building_area   = db.Column(db.Float, default=0)
    building_age    = db.Column(db.Integer, default=0)
    report_file     = db.Column(db.String(200))
    report_number   = db.Column(db.String(50))
    sent_to_engineer_at = db.Column(db.DateTime, nullable=True)
    engineer_report = db.Column(db.Text, nullable=True)  # تقرير المهندس
    transaction_type = db.Column(db.String(50), default="real_estate")  
    vehicle_type  = db.Column(db.String(100))
    vehicle_model = db.Column(db.String(100))
    vehicle_year  = db.Column(db.String(20))
    type = db.Column(db.String(50))          # نوع المعاملة (عقار، سيارة …)
    valuation_amount = db.Column(db.Float)   # مبلغ التثمين
    state = db.Column(db.String(100), nullable=True)   # الولاية
    region = db.Column(db.String(100), nullable=True)  # المنطقة
    
    # 👇 هنا فقط مفتاح خارجي يربط بالجدول Bank
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=True)
    # 👇 اسم فرع البنك المرتبط بالمعاملة
    bank_branch = db.Column(db.String(120), nullable=True)

    price = db.Column(db.Float, nullable=True)   # سعر التثمين (اختياري)

    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    branch_id   = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=False)

    payment_status  = db.Column(db.String(20), default="غير مدفوعة")

    # رمز تحقق عام للباركود/QR
    verification_token = db.Column(db.String(64), nullable=True, unique=True)

    payments = db.relationship("Payment", backref="transaction", lazy=True)


class NotificationSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subscription_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class LandPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(120))      # الولاية
    region = db.Column(db.String(120))     # المنطقة
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"))
    price_per_meter = db.Column(db.Float)  # سعر المتر
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = "payment"
    id             = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    amount         = db.Column(db.Float, default=0)
    date_received  = db.Column(db.DateTime, default=datetime.utcnow)
    received_by    = db.Column(db.String(50))
    method         = db.Column(db.String(20))   # كاش / تحويل
    receipt_file   = db.Column(db.String(200))  # صورة أو ملف الإيصال


class ReportTemplate(db.Model):
    __tablename__ = "report_template"
    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50), nullable=False)  # real_estate / vehicle
    content = db.Column(db.Text, nullable=True)
    title = db.Column(db.String(150), nullable=True)
    file = db.Column(db.String(255), nullable=True)  # مسار ملف DOCX المرفوع إن وُجد


# فواتير البنك بمراحلها
class BankInvoice(db.Model):
    __tablename__ = "bank_invoice"
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=True)
    amount = db.Column(db.Float, default=0)
    issued_at = db.Column(db.DateTime, nullable=True)     # المرحلة 1: إصدار
    delivered_at = db.Column(db.DateTime, nullable=True)  # المرحلة 2: تسليم
    received_at = db.Column(db.DateTime, nullable=True)   # المرحلة 3: استلام المبلغ
    note = db.Column(db.String(255))

class Quote(db.Model):
    __tablename__ = "quote"
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=True)
    amount = db.Column(db.Float, default=0)
    valid_until = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class CustomerInvoice(db.Model):
    __tablename__ = "customer_invoice"
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, default=0)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=True)
    note = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class CustomerQuote(db.Model):
    __tablename__ = "customer_quote"
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, default=0)
    valid_until = db.Column(db.DateTime, nullable=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transaction.id"), nullable=True)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

# ---------------- تنظيف عروض الأسعار منتهية الصلاحية ----------------
# ملاحظة: نستخدم خانة global لتقليل تكرار التنفيذ على كل طلب
last_quotes_purge_at = None
PURGE_INTERVAL_SECONDS = 600  # 10 دقائق

def purge_expired_quotes() -> None:
    """يحذف كافة عروض الأسعار التي انتهى تاريخ صلاحيتها.

    يُعتبر العرض منتهيًا إذا كانت له قيمة valid_until وأصبحت أقل من الآن (UTC).
    تنطبق العملية على جدولي Quote و CustomerQuote.
    """
    now_utc = datetime.utcnow()
    try:
        deleted_quotes = Quote.query \
            .filter(Quote.valid_until != None, Quote.valid_until < now_utc) \
            .delete(synchronize_session=False)

        deleted_customer_quotes = CustomerQuote.query \
            .filter(CustomerQuote.valid_until != None, CustomerQuote.valid_until < now_utc) \
            .delete(synchronize_session=False)

        if (deleted_quotes or 0) > 0 or (deleted_customer_quotes or 0) > 0:
            db.session.commit()
    except Exception:
        # في حال حدوث أي خطأ، نرجع المعاملة لحالتها السابقة
        db.session.rollback()

@app.before_request
def auto_purge_expired_quotes():
    global last_quotes_purge_at
    now_utc = datetime.utcnow()
    if last_quotes_purge_at is None or (now_utc - last_quotes_purge_at).total_seconds() >= PURGE_INTERVAL_SECONDS:
        purge_expired_quotes()
        last_quotes_purge_at = now_utc

class ValuationMemory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(100), nullable=False)   # الولاية
    region = db.Column(db.String(100), nullable=False)  # المنطقة
    bank_id = db.Column(db.Integer, nullable=False)     # البنك
    price_per_meter = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Expense(db.Model):
    __tablename__ = "expense"
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file   = db.Column(db.String(200))
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"))
    branch = db.relationship("Branch", backref="expenses")

class BranchDocument(db.Model):
    __tablename__ = "branch_document"
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    doc_type = db.Column(db.String(100), nullable=True)
    file = db.Column(db.String(255), nullable=True)
    issued_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    branch = db.relationship("Branch", backref="documents")

# ✅ مستندات عامة مرسلة إلى البنوك (غير مرتبطة بمعاملة)
class BankDocument(db.Model):
    __tablename__ = "bank_document"
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    doc_type = db.Column(db.String(100), nullable=True)  # رسالة، سيرة ذاتية، ...
    file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)

# ✅ جدول بسيط لحفظ العملاء (اسم ورقم)
class Customer(db.Model):
    __tablename__ = "customer"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), nullable=False)

# ✅ حفظ ملفات قوالب الوورد للفواتير وعروض الأسعار
class TemplateDoc(db.Model):
    __tablename__ = "template_doc"
    id = db.Column(db.Integer, primary_key=True)
    doc_type = db.Column(db.String(50), nullable=False)  # invoice | quote
    filename = db.Column(db.String(255), nullable=False)  # اسم الملف داخل uploads
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 🆕 قالب خاص بفرع معين (اختياري). لو كانت NULL فهو قالب عام
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)

def replace_placeholders_in_docx(doc: Document, replacements: dict) -> None:
    # يدعم الاستبدال حتى لو وُجدت مسافات/علامات RTL داخل الأقواس
    # نبني خريطة بالاسم بدون الأقواس وبحروف كبيرة
    import re
    zero_width = "\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
    def strip_braces_and_controls(s: str) -> str:
        s = str(s)
        s = s.replace("{", "").replace("}", "")
        s = re.sub(rf"[{zero_width}]", "", s)
        return s

    # ابنِ قاموسًا بمتغيرات متعددة الأشكال لنفس المفتاح
    token_to_value = {}
    for k, v in replacements.items():
        base = strip_braces_and_controls(k).strip()
        variants = set()
        variants.add(base)
        variants.add(base.replace(" ", ""))
        variants.add(base.replace("_", " "))
        variants.add(base.replace("_", ""))
        for var in variants:
            token_to_value[var.upper()] = str(v)
    # نمط يلتقط { TOKEN } مع احتمالية وجود مسافات/علامات اتجاه داخل الأقواس
    # يدعم {TOKEN} و {{TOKEN}} ويستثني الأقواس داخل الاسم
    # ملاحظة: نتجنب استخدام f-string هنا بسبب الأقواس المتداخلة في regex
    token_pattern = re.compile(
        r"\{{{1,2}}[\s" + zero_width + r"]*([^{}]+?)[\s" + zero_width + r"]*\}}{{{1,2}}"
    )

    def replace_in_paragraph(paragraph) -> None:
        combined_text = "".join(run.text for run in paragraph.runs) or paragraph.text
        if not combined_text:
            return
        def _repl(m):
            raw_name = strip_braces_and_controls(m.group(1)).strip().upper()
            return (
                token_to_value.get(raw_name)
                or token_to_value.get(raw_name.replace(" ", ""))
                or token_to_value.get(raw_name.replace(" ", "_"))
                or token_to_value.get(raw_name.replace("_", ""))
                or m.group(0)
            )
        new_text = token_pattern.sub(_repl, combined_text)
        # تمرير احتياطي: استبدال مباشر لأي مفاتيح مقدَّمة كما هي
        if new_text == combined_text:
            for raw_key, raw_val in replacements.items():
                if raw_key and isinstance(raw_key, str) and raw_key in new_text:
                    new_text = new_text.replace(raw_key, str(raw_val))
        if new_text != combined_text:
            paragraph.text = new_text

    def replace_in_table(table) -> None:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_in_paragraph(p)
                for nested in getattr(cell, "tables", []):
                    replace_in_table(nested)

    for paragraph in doc.paragraphs:
        replace_in_paragraph(paragraph)

    for table in doc.tables:
        replace_in_table(table)

    for section in getattr(doc, "sections", []):
        header = getattr(section, "header", None)
        if header:
            for p in header.paragraphs:
                replace_in_paragraph(p)
            for t in header.tables:
                replace_in_table(t)
        footer = getattr(section, "footer", None)
        if footer:
            for p in footer.paragraphs:
                replace_in_paragraph(p)
            for t in footer.tables:
                replace_in_table(t)

def ensure_template_doc_branch_column():
    # إضافة العمود branch_id إن لم يكن موجودًا (SQLite: ALTER TABLE ADD COLUMN)
    try:
        if not column_exists("template_doc", "branch_id"):
            db.session.execute(text("ALTER TABLE template_doc ADD COLUMN branch_id INTEGER"))
            db.session.commit()
    except Exception:
        db.session.rollback()

def get_template_filename(doc_type: str, branch_id: int | None = None) -> str | None:
    # يفضّل القالب الخاص بالفرع إن وجد، ثم يعود للقالب العام
    ensure_template_doc_branch_column()
    base_q = TemplateDoc.query.filter(TemplateDoc.doc_type == doc_type)
    if branch_id is not None:
        rec = base_q.filter(TemplateDoc.branch_id == branch_id).order_by(TemplateDoc.uploaded_at.desc()).first()
        if rec:
            return rec.filename
    rec = base_q.filter(TemplateDoc.branch_id == None).order_by(TemplateDoc.uploaded_at.desc()).first()
    return rec.filename if rec else None

# ---------------- دوال مساعدة ----------------
def save_price(state, region, bank, price):
    record = ValuationMemory.query.filter_by(
        state=state, region=region, bank_id=bank
    ).first()
    if record:
        record.price_per_meter = price
        record.updated_at = datetime.utcnow()
    else:
        record = ValuationMemory(state=state, region=region, bank_id=bank, price_per_meter=price)
        db.session.add(record)
    db.session.commit()




def send_notification(user_id, title, body):
    subs = NotificationSubscription.query.filter_by(user_id=user_id).all()
    vapid_private = app.config.get("VAPID_PRIVATE_KEY") or os.environ.get("VAPID_PRIVATE_KEY")
    vapid_claims = app.config.get("VAPID_CLAIMS", {"sub": "mailto:your-email@example.com"})
    if not vapid_private:
        # لا يوجد مفتاح خاص للإرسال، نتجاوز حتى لا نفشل التطبيق
        return
    for sub in subs:
        try:
            webpush(
                subscription_info=json.loads(sub.subscription_json),
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=vapid_private,
                vapid_claims=vapid_claims
            )
        except WebPushException as e:
            print("❌ إشعار فشل:", e)





def get_last_price(state, region, bank):
    record = ValuationMemory.query.filter_by(
        state=state, region=region, bank_id=bank
    ).order_by(ValuationMemory.updated_at.desc()).first()
    return record.price_per_meter if record else None


# فحص وجود عمود داخل جدول (لمشاكل الإصدارات القديمة)
def column_exists(table_name: str, column_name: str) -> bool:
    try:
        res = db.session.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
        cols = {r["name"] for r in res}
        return column_name in cols
    except Exception:
        return False

# ---------------- فِلتر جينجا: "كم مضى" بالعربية ----------------
@app.template_filter('ago')
def naturaltime_ar(dt):
    if not dt:
        return "لم يتم الإرسال"
    delta = datetime.utcnow() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "منذ ثوانٍ"
    minutes = seconds // 60
    if minutes < 60:
        if minutes == 1:
            return "منذ دقيقة"
        elif minutes == 2:
            return "منذ دقيقتين"
        elif 3 <= minutes <= 10:
            return f"منذ {minutes} دقائق"
        else:
            return f"منذ {minutes} دقيقة"
    hours = minutes // 60
    if hours < 24:
        if hours == 1:
            return "منذ ساعة"
        elif hours == 2:
            return "منذ ساعتين"
        elif 3 <= hours <= 10:
            return f"منذ {hours} ساعات"
        else:
            return f"منذ {hours} ساعة"
    days = hours // 24
    if days < 30:
        if days == 1:
            return "منذ يوم"
        elif days == 2:
            return "منذ يومين"
        else:
            return f"منذ {days} أيام"
    months = days // 30
    if months < 12:
        if months == 1:
            return "منذ شهر"
        elif months == 2:
            return "منذ شهرين"
        else:
            return f"منذ {months} أشهر"
    years = months // 12
    if years == 1:
        return "منذ سنة"
    elif years == 2:
        return "منذ سنتين"
    else:
        return f"منذ {years} سنوات"

# ---------------- حالة مستند حسب تاريخ الانتهاء ----------------
def document_status(doc):
    try:
        exp = getattr(doc, "expires_at", None)
        if not exp:
            return "بدون انتهاء"
        delta_days = (exp - datetime.utcnow()).days
        if delta_days < 0:
            return "منتهي"
        if delta_days <= 30:
            return "قريب الانتهاء"
        return "ساري"
    except Exception:
        return "بدون انتهاء"

# ---------------- المسارات ----------------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session.get("role")
    if role == "manager":
        return redirect(url_for("manager_dashboard"))
    elif role == "employee":
        return redirect(url_for("employee_dashboard"))
    elif role == "engineer":
        return redirect(url_for("engineer_dashboard"))
    elif role == "finance":
        return redirect(url_for("finance_dashboard"))
    return redirect(url_for("login"))

# ---------------- تسجيل الدخول ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["role"] = user.role
            session["username"] = user.username  # نحتاجه للتقارير والاستلام
            return redirect(url_for("index"))
        else:
            flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- لوحة الموظف ----------------
VAPID_PUBLIC_KEY = "BFNeZpjEro8pwFxR1H20twlTd2pL5MZtWrDATu4ME2RcbzhN"  # المفتاح اللي ولدته

@app.route("/employee")
def employee_dashboard():
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    transactions = Transaction.query.filter_by(assigned_to=session.get("user_id")).all()
    banks = Bank.query.all()

    # مستندات الفرع الخاصة بالموظف
    user = User.query.get(session.get("user_id"))
    branch_docs = []
    if user and getattr(user, "branch_id", None):
        try:
            branch_docs = BranchDocument.query.filter_by(branch_id=user.branch_id)\
                .order_by(BranchDocument.expires_at.asc().nulls_last()).all()
        except Exception:
            branch_docs = BranchDocument.query.filter_by(branch_id=user.branch_id).all()

    # تمرير السعر الافتراضي (لو ما فيه ذاكرة نخليه صفر)
    price_per_meter = 0.0  

    return render_template(
        "employee.html",
        transactions=transactions,
        banks=banks,
        vapid_public_key=VAPID_PUBLIC_KEY,
        price_per_meter=price_per_meter,
        docs=branch_docs,
        status_for=document_status
    )

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    if session.get("role") != "employee":
        return redirect(url_for("login"))
    
    user = User.query.get(session["user_id"])
    transaction_type = request.form.get("transaction_type")  # ✅ نحدد نوع المعاملة
    client_name = (request.form.get("client_name") or "").strip()
    client_phone = (request.form.get("client_phone") or "").strip()
    fee = float(request.form.get("fee") or 0)

    t = None  # المعاملة

    # ✅ تحقق من رقم العميل
    if not client_phone:
        flash("⚠️ يجب إدخال رقم العميل", "danger")
        return redirect(url_for("employee_dashboard"))

    # 🧾 حفظ/تحديث العميل في جدول العملاء
    existing_customer = Customer.query.filter_by(phone=client_phone).first()
    if existing_customer:
        # نحدّث الاسم إذا كان مختلفًا
        if client_name and existing_customer.name != client_name:
            existing_customer.name = client_name
    else:
        db.session.add(Customer(name=client_name or "-", phone=client_phone))
        db.session.flush()

    # 🏠 معاملة عقار
    if transaction_type == "real_estate":
        state = request.form.get("state")
        region = request.form.get("region")
        bank_id = request.form.get("bank_id")
        bank_branch = (request.form.get("bank_branch") or "").strip()
        try:
            bank_id = int(bank_id) if bank_id else None
        except Exception:
            bank_id = None

        # ✅ البحث في ValuationMemory
        vm = None
        if state and region and bank_id:
            vm = ValuationMemory.query.filter_by(
                state=state, region=region, bank_id=bank_id
            ).order_by(ValuationMemory.updated_at.desc()).first()

        if vm:
            price_per_meter = vm.price_per_meter
        else:
            lp = LandPrice.query.filter_by(state=state, region=region, bank_id=bank_id).first()
            price_per_meter = lp.price_per_meter if lp else 0.0

        # 📏 البيانات
        area          = float(request.form.get("area") or 0)
        building_area = float(request.form.get("building_area") or 0)
        building_age  = int(request.form.get("building_age") or 0)

        # ✅ حساب التثمين
        land_value = area * price_per_meter if price_per_meter else 0.0
        building_value = 0
        if building_area > 0 and building_age > 0:
            building_value = building_area * (185 / 50) * building_age

        total_estimate = land_value + building_value

        # تحقق أساسي: البنك وفرع البنك مطلوبان
        if not bank_id or not bank_branch:
            flash("⚠️ يرجى اختيار البنك وكتابة فرع البنك", "danger")
            return redirect(url_for("employee_dashboard"))

        t = Transaction(
            client=client_name,
            employee=user.username,
            date=datetime.utcnow(),
            status="بانتظار المهندس",
            fee=fee,
            branch_id=user.branch_id,
            land_value=land_value,
            building_value=building_value,
            total_estimate=total_estimate,
            valuation_amount=total_estimate,  # 👈 نخزن التثمين هنا
            area=area,
            building_area=building_area,
            building_age=building_age,
            state=state,
            region=region,
            bank_id=bank_id,
            bank_branch=bank_branch,
            created_by=user.id,
            payment_status="غير مدفوعة",
            transaction_type="real_estate",
            assigned_to=None
        )

    # 🚗 معاملة مركبة
    elif transaction_type == "vehicle":
        vehicle_type  = request.form.get("vehicle_type")
        vehicle_model = request.form.get("vehicle_model")
        vehicle_year  = request.form.get("vehicle_year")
        vehicle_value = float(request.form.get("vehicle_value") or 0)

        # تحقق أساسي: البنك وفرع البنك مطلوبان لمعاملات المركبات أيضًا
        bank_id = request.form.get("bank_id")
        bank_branch = (request.form.get("bank_branch") or "").strip()
        if not bank_id or not bank_branch:
            flash("⚠️ يرجى اختيار البنك وكتابة فرع البنك", "danger")
            return redirect(url_for("employee_dashboard"))

        t = Transaction(
    client=client_name,
    employee=user.username,
    date=datetime.utcnow(),
    status="بانتظار المهندس",  # ✅ بدون همزة
    fee=fee,
    branch_id=user.branch_id,
    total_estimate=vehicle_value,
    created_by=user.id,
    payment_status="غير مدفوعة",
    transaction_type="vehicle",
    vehicle_type=vehicle_type,
    vehicle_model=vehicle_model,
    vehicle_year=vehicle_year,
    state=None,
    region=None,
    bank_id=bank_id,
    bank_branch=bank_branch,
    assigned_to=None   # ✅
)


        # 👨‍🔧 تعيين مباشر للمهندس (مثال: أول مهندس مسجل)
        engineer = User.query.filter_by(role="engineer").first()
        if engineer:
            t.assigned_to = engineer.id

        # 👨‍🔧 تعيين مباشر للمهندس (أول مهندس في نفس الفرع إن وجد)
        engineer = User.query.filter_by(role="engineer", branch_id=user.branch_id).first()
        if engineer:
            t.assigned_to = engineer.id

    # رفع الملفات
    files = request.files.getlist("files")
    saved_files = []
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            saved_files.append(filename)
    t.files = ",".join(saved_files)

    db.session.add(t)
    db.session.commit()

    # 🔔 إشعار جميع مهندسي نفس الفرع بوجود معاملة جديدة
    try:
        engineers = User.query.filter_by(role="engineer", branch_id=user.branch_id).all()
        for eng in engineers:
            send_notification(eng.id, "📋 معاملة جديدة", f"تمت إضافة معاملة رقم {t.id}")
    except Exception:
        pass
    flash("✅ تم إضافة المعاملة بنجاح", "success")
    return redirect(url_for("employee_dashboard"))


# 🏢 إدارة الفروع
@app.route("/manage_branches", methods=["GET", "POST"])
def manage_branches():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("⚠️ يجب إدخال اسم الفرع", "danger")
        else:
            existing = Branch.query.filter_by(name=name).first()
            if existing:
                flash("⚠️ الفرع موجود مسبقاً", "warning")
            else:
                branch = Branch(name=name)
                db.session.add(branch)
                db.session.commit()
                flash("✅ تم إضافة الفرع", "success")
                return redirect(url_for("manage_branches"))

    branches = Branch.query.all()
    return render_template("manage_branches.html", branches=branches)

# 🗑 حذف فرع
@app.route("/delete_branch/<int:bid>")
def delete_branch(bid):
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    branch = Branch.query.get_or_404(bid)

    # تحقق إذا الفرع مرتبط بموظفين
    if branch.users:
        flash("🚫 لا يمكن حذف فرع مرتبط بموظفين", "danger")
        return redirect(url_for("manage_branches"))

    db.session.delete(branch)
    db.session.commit()
    flash("✅ تم حذف الفرع", "success")
    return redirect(url_for("manage_branches"))

# ✅ صفحة العمولات
@app.route("/commission", methods=["GET", "POST"])
def commissions_page():
    role = session.get("role")
    if not role:
        return redirect(url_for("login"))

    # 🔹 إذا كان المدير → يقدر يفلتر بالموظفين
    selected_user_id = None
    if role == "manager":
        if request.method == "POST":
            selected_user_id = request.form.get("user_id")
        users = User.query.filter(User.role == "employee").all()
    else:
        # الموظف يشوف بياناته فقط
        selected_user_id = session["user_id"]
        users = []

    query = Transaction.query.filter(Transaction.payment_status == "مدفوعة")

    if selected_user_id:
        query = query.filter(Transaction.created_by == int(selected_user_id))

    transactions = query.all()

    # 🔹 حساب العقارات
    real_estate_txns = [t for t in transactions if t.transaction_type == "real_estate"]
    real_estate_income = sum(t.fee for t in real_estate_txns)
    # كل 50 ريال = 1 معاملة
    real_estate_count = sum(max(1, int(t.fee // 50)) for t in real_estate_txns)

    # 🔹 حساب السيارات
    vehicle_txns = [t for t in transactions if t.transaction_type == "vehicle"]
    vehicle_income = sum(t.fee for t in vehicle_txns)
    # كل 3 سيارات = 1 معاملة
    vehicle_count = len(vehicle_txns) // 3

    # 🔹 الإجمالي
    total_income = real_estate_income + vehicle_income
    total_count = real_estate_count + vehicle_count

    # 🔹 العمولة (بعد 30 معاملة)
    commission_count = max(0, total_count - 30)
    commission = commission_count * 15

    return render_template(
        "commission.html",
        users=users,
        role=role,
        selected_user_id=selected_user_id,
        real_estate_count=real_estate_count,
        real_estate_income=real_estate_income,
        vehicle_count=vehicle_count,
        vehicle_income=vehicle_income,
        total_income=total_income,
        total_count=total_count,
        commission=commission
    )


# ---------------- لوحة المدير ----------------
VAPID_PUBLIC_KEY = "BFNeZpjEro8pwFxR1H20twlTd2pL5MZtWrDATu4ME2RcbzhN"  # المفتاح اللي ولدته
# 📌 لوحة المدير
@app.route("/manager")
def manager_dashboard():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    now = datetime.utcnow()
    hidden_statuses =     "in_progress"   ,  "بإنتظار المهندس" , "قيد المعاينة", "📑 تقرير مرفوع" ,  "بانتظار المهندس",
    VAPID_PUBLIC_KEY = "BFNeZpjEro8pwFxR1H20twlTd2pL5MZtWrDATu4ME2RcbzhN"  # المفتاح اللي ولدته

    # ✅ فقط معاملات العقارات تظهر عند المدير + استبعاد الحالات المخفية
    transactions = Transaction.query.filter(
        Transaction.transaction_type == "real_estate",
        ~Transaction.status.in_(hidden_statuses),
        Transaction.status.notin_(["مرفوضة",  "بانتظار المالية"  , "مكتملة", "منجزة"])
    ).order_by(Transaction.id.desc()).all()
    
    users = User.query.all()

    branches_data = []
    branches = Branch.query.all()
    for b in branches:
        income = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))\
            .join(Transaction, Payment.transaction_id == Transaction.id)\
            .filter(Transaction.branch_id == b.id)\
            .scalar() or 0.0
        expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0))\
            .filter(Expense.branch_id == b.id)\
            .scalar() or 0.0
        profit = income - expenses

        # ✅ إحصائية البنوك (الشهر الحالي) لكن فقط للعقارات
        banks_stats = (
            db.session.query(Bank.name, func.count(Transaction.id))
            .join(Transaction, Transaction.bank_id == Bank.id)
            .filter(Transaction.branch_id == b.id)
            .filter(Transaction.transaction_type == "real_estate")   # 🚫 استبعاد السيارات
            .filter(func.strftime("%m", Transaction.date) == now.strftime("%m"))
            .filter(func.strftime("%Y", Transaction.date) == now.strftime("%Y"))
            .group_by(Bank.name)
            .all()
        )
        banks_list = [{"name": x[0], "count": x[1]} for x in banks_stats]

        branches_data.append({
            "name": b.name,
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "banks": banks_list
        })

    # 🔔 مستندات على وشك الانتهاء خلال 30 يومًا (كل الفروع)
    expiring_docs = BranchDocument.query.filter(
        BranchDocument.expires_at != None,
        BranchDocument.expires_at <= (now + timedelta(days=30))
    ).order_by(BranchDocument.expires_at.asc()).all()

    # بيانات مساعدة لرفع قوالب الفواتير مباشرة من لوحة المدير
    current_user = User.query.get(session.get("user_id"))
    current_branch_id = getattr(current_user, "branch_id", None)
    template_branches = Branch.query.order_by(Branch.name.asc()).all()

    return render_template(
        "manager_dashboard.html",
        transactions=transactions,
        users=users,
        branches=branches_data,
        vapid_public_key=VAPID_PUBLIC_KEY,
        net_profit=sum(b["profit"] for b in branches_data),
        expiring_docs=expiring_docs,
        template_branches=template_branches,
        current_branch_id=current_branch_id
    )


# ✅ تحديث حالة المعاملة
@app.route("/update_status/<int:tid>/<status>")
def update_status(tid, status):
    role = session.get("role")
    if not role:
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)

    # ✅ المدير ما يقدر يرسل للمالية
    if role == "manager" and status == "بانتظار الدفع":
        flash("⚠️ لا يمكن للمدير إرسال المعاملة للمالية. فقط المهندس.", "danger")
        return redirect(url_for("manager_dashboard"))

    # ✅ المهندس فقط يرسل للمالية
    if role == "engineer" and status == "بانتظار الدفع":
        if not t.engineer_report:  # تتأكد إنه كتب التقرير
            flash("⚠️ لا يمكنك إرسال المعاملة للمالية بدون تقرير.", "danger")
            return redirect(url_for("engineer_dashboard"))

    t.status = status
    db.session.commit()
      # بعد db.session.commit() في send_to_visit أو update_status
    engineer = User.query.filter_by(role="engineer").first()
    if engineer:
        send_notification(engineer.id, "📩 معاملة جديدة", f"تم إرسال معاملة رقم {t.id} إليك")


    if role == "manager":
        return redirect(url_for("manager_dashboard"))
    elif role == "engineer":
        return redirect(url_for("engineer_dashboard"))
    elif role == "employee":
        return redirect(url_for("employee_dashboard"))
    return redirect(url_for("login"))


# راوت اعتماد من المدير
@app.route("/approve_transaction/<int:tid>")
def approve_transaction(tid):
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    transaction = Transaction.query.get_or_404(tid)
    transaction.status = "بانتظار المهندس"   # 👈 كل مهندس بالفرع بيشوفها
    db.session.commit()

    flash("✅ تم اعتماد المعاملة وإرسالها لجميع مهندسي الفرع", "success")
    return redirect(url_for("manager_dashboard"))





# 🏢 إضافة فرع جديد
@app.route("/add_branch", methods=["POST"])
def add_branch():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    name = request.form.get("name")
    if name:
        db.session.add(Branch(name=name))
        db.session.commit()
        flash("✅ تم إضافة الفرع بنجاح", "success")
    else:
        flash("⚠️ يجب إدخال اسم الفرع", "danger")
    return redirect(url_for("manager_dashboard"))


# 🏦 إضافة بنك جديد
@app.route("/add_bank", methods=["GET", "POST"])
def add_bank():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            db.session.add(Bank(name=name))
            db.session.commit()
            flash("✅ تم إضافة البنك بنجاح", "success")
            return redirect(url_for("manager_dashboard"))
        else:
            flash("⚠️ يجب إدخال اسم البنك", "danger")
    
    return render_template("add_bank.html")

@app.route("/transaction/<int:tid>")
def transaction_detail(tid):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    t = Transaction.query.get_or_404(tid)
    return render_template("transaction_detail.html", t=t)

# ✅ توليد رقم التقرير
def generate_report_number():
    last_number = db.session.query(Transaction.report_number) \
        .filter(Transaction.report_number.isnot(None)) \
        .order_by(Transaction.report_number.desc()) \
        .first()
    if last_number and last_number[0]:
        match = re.search(r"(\d+)", last_number[0])
        if match:
            return f"ref{int(match.group(1)) + 1}"
    return "ref1001"

# ✅ نقل التثمين إلى المهندس
@app.route("/engineer/valuate/<int:tid>", methods=["POST"])
def engineer_valuate_transaction(tid):
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)

    if t.transaction_type == "real_estate":
        land_value     = parse_float_input(request.form.get("land_value", 0))
        building_value = parse_float_input(request.form.get("building_value", 0))
        total_estimate = land_value + building_value

        t.land_value      = land_value
        t.building_value  = building_value
        t.total_estimate  = total_estimate
        t.valuation_amount = total_estimate
        t.status          = "قيد المعاينة"

        # ✅ تحديث ذاكرة التثمين
        memory = ValuationMemory.query.filter_by(
            state=t.state, region=t.region, bank_id=t.bank_id
        ).first()
        if memory:
            memory.price_per_meter = land_value / t.area if t.area > 0 else 0
            memory.updated_at = datetime.utcnow()
        else:
            memory = ValuationMemory(
                state=t.state,
                region=t.region,
                bank_id=t.bank_id,
                price_per_meter=land_value / t.area if t.area > 0 else 0
            )
            db.session.add(memory)

    elif t.transaction_type == "vehicle":
        vehicle_value = parse_float_input(request.form.get("vehicle_value", 0))
        t.total_estimate = vehicle_value
        t.valuation_amount = vehicle_value
        t.status = "قيد المعاينة"

    # ✅ إضافة رقم مرجعي إذا ما كان موجود
    if not t.report_number:
        last_txn = Transaction.query.filter(
            Transaction.report_number != None
        ).order_by(Transaction.id.desc()).first()

        if last_txn and last_txn.report_number.startswith("ref"):
            last_num = int(last_txn.report_number.replace("ref", ""))
            t.report_number = f"ref{last_num + 1}"
        else:
            t.report_number = "ref1001"

    db.session.commit()
    flash("✅ تم حفظ التثمين بواسطة المهندس", "success")
    return redirect(url_for("engineer_transaction_details", tid=tid))




@app.route("/save-subscription", methods=["POST"])
def save_subscription():
    if not session.get("user_id"):
        return {"error": "Unauthorized"}, 401

    data = request.get_json()
    if not data:
        return {"error": "Invalid subscription"}, 400

    # نحذف أي اشتراك قديم لنفس المستخدم
    NotificationSubscription.query.filter_by(user_id=session["user_id"]).delete()

    sub = NotificationSubscription(user_id=session["user_id"],
                                   subscription_json=json.dumps(data))
    db.session.add(sub)
    db.session.commit()
    return {"success": True}


@app.route("/assign_to_engineer/<int:tid>/<int:engineer_id>")
def assign_to_engineer(tid, engineer_id):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    
    transaction = Transaction.query.get_or_404(tid)
    transaction.assigned_to = engineer_id
    transaction.status = "بانتظار المهندس"   # ✅ الآن يقدر يشوفها المهندس
    db.session.commit()

    flash("✅ تم تحويل المعاملة إلى المهندس")
    return redirect(url_for("manager_dashboard"))



@app.route("/new_transaction", methods=["GET", "POST"])
def new_transaction():
    if request.method == "POST":
        state = request.form.get("state")
        region = request.form.get("region")
        bank_id = request.form.get("bank_id")
        price = float(request.form.get("price") or 0)
        try:
            bank_id = int(bank_id) if bank_id else None
        except Exception:
            bank_id = None
        if bank_id is None:
            flash("⚠️ الرجاء اختيار بنك صحيح", "warning")
        else:
            save_price(state, region, bank_id, price)
            flash("تم حفظ المعاملة والسعر في الذاكرة ✅", "success")
        return redirect(url_for("new_transaction"))
    state = request.args.get("state")
    region = request.args.get("region")
    bank_id = request.args.get("bank_id")
    suggested_price = None
    try:
        bank_id_int = int(bank_id) if bank_id else None
    except Exception:
        bank_id_int = None
    if state and region and bank_id_int:
        suggested_price = get_last_price(state, region, bank_id_int)
    banks = Bank.query.order_by(Bank.name.asc()).all()
    return render_template("new_transaction.html", suggested_price=suggested_price, banks=banks)


@app.route("/get_price", methods=["POST"])
def get_price():
    state = request.form.get("state")
    region = request.form.get("region")
    bank_id = request.form.get("bank_id")

    price_per_meter = 0.0
    if state and region and bank_id:
        try:
            bank_id_int = int(bank_id)
        except Exception:
            bank_id_int = None

        vm = None
        if bank_id_int is not None:
            vm = ValuationMemory.query.filter_by(
                state=state, region=region, bank_id=bank_id_int
            ).order_by(ValuationMemory.updated_at.desc()).first()

        if vm:
            price_per_meter = vm.price_per_meter
        else:
            lp = LandPrice.query.filter_by(
                state=state, region=region, bank_id=bank_id_int
            ).first()
            if lp:
                price_per_meter = lp.price_per_meter

    return {"price_per_meter": price_per_meter}





# ---------------- لوحة المهندس ----------------
# 👨‍🔧 لوحة المهندس
@app.route("/engineer")
def engineer_dashboard():
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    engineer_id = session.get("user_id")
    engineer = User.query.get_or_404(engineer_id)

    transactions = Transaction.query.filter(
        Transaction.branch_id == engineer.branch_id,
        or_(
            Transaction.status == "بانتظار المهندس",
            and_(
                Transaction.assigned_to == engineer_id,
                Transaction.status.in_(["قيد المعاينة", "قيد التنفيذ"])
            )
        )
    ).order_by(Transaction.id.desc()).all()
                
    return render_template("engineer.html", transactions=transactions, engineer=engineer, vapid_public_key=VAPID_PUBLIC_KEY)


# ✅ عند استلام المعاملة
@app.route("/engineer_take/<int:tid>")
def engineer_take(tid):
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)
    engineer_id = session.get("user_id")

    # 🆕 تحديد أن المهندس استلم المعاملة
    t.assigned_to = engineer_id
    t.status = "قيد المعاينة"

    # 🆕 تخصيص رسالة حسب نوع المعاملة
    if t.transaction_type == "سيارة":
        flash("🚗 تم استلام معاملة السيارة", "success")
    else:
        flash("🏠 تم استلام معاملة العقار", "success")

    db.session.commit()
    return redirect(url_for("engineer_dashboard"))


# ---------------- قوالب التقارير وإعداد محرر التقرير للمهندس ----------------
def get_template_by_type(template_type: str) -> ReportTemplate | None:
    return ReportTemplate.query.filter_by(template_type=template_type).first()


@app.route("/manager/report_templates", methods=["GET", "POST"])
def manage_report_templates():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    real_estate_tpl = get_template_by_type("real_estate")
    vehicle_tpl = get_template_by_type("vehicle")

    if request.method == "POST":
        # حفظ النصوص فقط (تم تعطيل رفع القوالب)
        re_content = (request.form.get("real_estate_content") or "").strip()
        ve_content = (request.form.get("vehicle_content") or "").strip()

        if re_content:
            if not real_estate_tpl:
                real_estate_tpl = ReportTemplate(template_type="real_estate", content=re_content)
                db.session.add(real_estate_tpl)
            else:
                real_estate_tpl.content = re_content

        if ve_content:
            if not vehicle_tpl:
                vehicle_tpl = ReportTemplate(template_type="vehicle", content=ve_content)
                db.session.add(vehicle_tpl)
            else:
                vehicle_tpl.content = ve_content

        db.session.commit()
        flash("✅ تم حفظ القوالب النصية (تم تعطيل الرفع)", "success")
        return redirect(url_for("manage_report_templates"))

    return render_template(
        "manager_report_templates.html",
        real_estate_content=real_estate_tpl.content if real_estate_tpl else "",
        vehicle_content=vehicle_tpl.content if vehicle_tpl else "",
        real_estate_files=[],
        vehicle_files=[]
    )


def extract_placeholders(template_text: str) -> list[str]:
    if not template_text:
        return []
    return sorted(set(re.findall(r"\{([a-zA-Z0-9_]+)\}", template_text)))


def default_values_for_placeholders(t: Transaction, placeholders: list[str]) -> dict[str, str]:
    mapping = {
        "client_name": t.client or "",
        "sketch_number": "",
        "bank_name": t.bank.name if t.bank else "",
        "bank_branch": t.bank_branch or "",
        "property_state": t.state or "",
        "property_region": t.region or "",
        "area": str(t.area or 0),
        "building_area": str(t.building_area or 0),
        "building_age": str(t.building_age or 0),
        "land_value": str(t.land_value or 0),
        "building_value": str(t.building_value or 0),
        "total_estimate": str(t.total_estimate or 0),
        "vehicle_type": t.vehicle_type or "",
        "vehicle_model": t.vehicle_model or "",
        "vehicle_year": t.vehicle_year or "",
        "vehicle_value": str(t.total_estimate or 0),
        "today": datetime.utcnow().strftime("%Y-%m-%d"),
        "transaction_id": str(t.id),
    }
    return {ph: mapping.get(ph, "") for ph in placeholders}


def fill_template(template_text: str, values: dict[str, str]) -> str:
    def repl(match):
        key = match.group(1)
        return str(values.get(key, match.group(0)))
    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, template_text)


@app.route("/engineer/report_editor/<int:tid>", methods=["GET", "POST"])
def engineer_report_editor(tid):
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)
    template_type = t.transaction_type or "real_estate"
    tpl = get_template_by_type(template_type)
    template_text = tpl.content if tpl else ""

    placeholders = extract_placeholders(template_text)

    if request.method == "POST":
        # جمع القيم
        values = {ph: (request.form.get(ph) or "").strip() for ph in placeholders}
        # توليد النص النهائي
        final_text = fill_template(template_text, values)

        t.engineer_report = final_text
        t.status = "📑 تقرير مبدئي"  # حالة وسطية حتى الرفع النهائي PDF
        db.session.commit()
        flash("✅ تم حفظ نص التقرير من القالب", "success")
        return redirect(url_for("engineer_transaction_details", tid=tid))

    # قيّم افتراضية
    defaults = default_values_for_placeholders(t, placeholders)

    return render_template(
        "engineer_report_editor.html",
        t=t,
        template_text=template_text,
        placeholders=placeholders,
        defaults=defaults,
    )



@app.route("/add_transaction_engineer", methods=["GET", "POST"])
def add_transaction_engineer():
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    banks = Bank.query.all()

    if request.method == "POST":
        transaction_type = request.form.get("transaction_type")
        client_name = (request.form.get("client_name") or "").strip()
        client_phone = (request.form.get("client_phone") or "").strip()
        fee = float(request.form.get("fee") or 0)

        # ✅ تحقق من رقم العميل
        if not client_phone:
            flash("⚠️ يجب إدخال رقم العميل", "danger")
            return redirect(url_for("add_transaction_engineer"))

        # 🧾 حفظ/تحديث العميل في جدول العملاء
        existing_customer = Customer.query.filter_by(phone=client_phone).first()
        if existing_customer:
            if client_name and existing_customer.name != client_name:
                existing_customer.name = client_name
        else:
            db.session.add(Customer(name=client_name or "-", phone=client_phone))
            db.session.flush()

        t = None

        if transaction_type == "real_estate":
            state = request.form.get("state")
            region = request.form.get("region")
            bank_id = request.form.get("bank_id")
            bank_branch = (request.form.get("bank_branch") or "").strip()

            area = float(request.form.get("area") or 0)
            building_area = float(request.form.get("building_area") or 0)
            building_age = int(request.form.get("building_age") or 0)

            # تحقق أساسي: البنك وفرع البنك مطلوبان
            if not bank_id or not bank_branch:
                flash("⚠️ يرجى اختيار البنك وكتابة فرع البنك", "danger")
                return redirect(url_for("add_transaction_engineer"))

            # احسب سعر المتر من الذاكرة أو من جدول الأسعار إن وُجد
            price_per_meter = 0.0
            try:
                bank_id_int = int(bank_id)
            except Exception:
                bank_id_int = None

            if state and region and bank_id_int is not None:
                vm = ValuationMemory.query.filter_by(
                    state=state, region=region, bank_id=bank_id_int
                ).order_by(ValuationMemory.updated_at.desc()).first()
                if vm:
                    price_per_meter = vm.price_per_meter or 0.0
                else:
                    lp = LandPrice.query.filter_by(state=state, region=region, bank_id=bank_id_int).first()
                    if lp:
                        price_per_meter = lp.price_per_meter or 0.0

            # حساب التثمين الابتدائي
            land_value = (area * price_per_meter) if price_per_meter else 0.0
            building_value = 0.0
            if building_area > 0 and building_age > 0:
                building_value = building_area * (185 / 50) * building_age
            total_estimate = land_value + building_value

            t = Transaction(
                client=client_name,
                employee=user.username,
                date=datetime.utcnow(),
                status="بانتظار المهندس",
                fee=fee,
                branch_id=user.branch_id,
                land_value=land_value,
                building_value=building_value,
                total_estimate=total_estimate,
                valuation_amount=total_estimate,
                area=area,
                building_area=building_area,
                building_age=building_age,
                state=state,
                region=region,
                bank_id=bank_id,
                bank_branch=bank_branch,
                created_by=user.id,
                transaction_type="real_estate",
                payment_status="غير مدفوعة",
                assigned_to=None   # ✅ غير مسند

            )

        elif transaction_type == "vehicle":
            vehicle_type  = request.form.get("vehicle_type")
            vehicle_model = request.form.get("vehicle_model")
            vehicle_year  = request.form.get("vehicle_year")
            vehicle_value = float(request.form.get("vehicle_value") or 0)

            # تحقق أساسي: البنك وفرع البنك مطلوبان لمعاملات المركبات أيضًا
            bank_id = request.form.get("bank_id")
            bank_branch = (request.form.get("bank_branch") or "").strip()
            if not bank_id or not bank_branch:
                flash("⚠️ يرجى اختيار البنك وكتابة فرع البنك", "danger")
                return redirect(url_for("add_transaction_engineer"))

            t = Transaction(
                client=client_name,
                employee=user.username,
                date=datetime.utcnow(),
                status="بانتظار المهندس",
                fee=fee,
                branch_id=user.branch_id,
                total_estimate=vehicle_value,
                created_by=user.id,
                transaction_type="vehicle",
                payment_status="غير مدفوعة",
                vehicle_type=vehicle_type,
                vehicle_model=vehicle_model,
                vehicle_year=vehicle_year,
                valuation_amount = vehicle_value,
                bank_id=bank_id,
                bank_branch=bank_branch,

                assigned_to=None   # ✅
            )

        if t:
            db.session.add(t)
            db.session.commit()
            flash("✅ تم إضافة المعاملة بنجاح", "success")
            return redirect(url_for("engineer_dashboard"))

    return render_template("add_transaction_engineer.html", banks=banks)


@app.route("/engineer/transaction/<int:tid>")
def engineer_transaction_details(tid):
    if session.get("role") != "engineer":
        return redirect(url_for("login"))

    engineer_id = session.get("user_id")
    engineer = User.query.get_or_404(engineer_id)

    t = Transaction.query.filter_by(id=tid, branch_id=engineer.branch_id).first_or_404()

    return render_template("engineer_transaction_details.html", t=t, engineer=engineer)


# ✅ عند رفع التقرير (المعتمد فقط)
@app.route("/engineer/upload_report/<int:tid>", methods=["POST"])
def engineer_upload_report(tid):
    if session.get("role") not in ["engineer", "manager"]:
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)

    if "report_file" not in request.files or request.files["report_file"].filename == "":
        flash("⚠️ لم يتم اختيار ملف", "danger")
        return redirect(url_for("engineer_dashboard"))

    file = request.files["report_file"]
    filename = secure_filename(f"{t.id}_{file.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # محاولة ختم التقرير برمز QR يشير إلى رابط التحقق العام
    try:
        verify_url = url_for('verify_report', token=t.verification_token or generate_verification_token(), _external=True)
        # إنشئ QR كصورة مؤقتة
        import qrcode
        from PIL import Image as PILImage
        qr_img = qrcode.make(verify_url)
        qr_path = os.path.join(app.config["UPLOAD_FOLDER"], f"qr_{t.id}.png")
        qr_img.save(qr_path)

        # حاول ختم PDF عبر PyMuPDF (fitz)
        try:
            doc = fitz.open(filepath)
            page = doc[0]
            rect = fitz.Rect(page.rect.width - 150, page.rect.height - 150, page.rect.width - 10, page.rect.height - 10)
            page.insert_image(rect, filename=qr_path)
            # إضافة نص رابط التحقق الصغير أسفل ال QR
            page.insert_text((rect.x0, rect.y1 + 5), verify_url, fontsize=6, color=(0, 0, 1))
            stamped_path = os.path.join(app.config["UPLOAD_FOLDER"], f"stamped_{filename}")
            doc.save(stamped_path)
            doc.close()
            os.replace(stamped_path, filepath)
        except Exception:
            pass
    except Exception:
        # تخطَ أي فشل في الختم ولا تُفشل الرفع
        pass

    t.report_file = filename
    t.status = "📑 تقرير مرفوع"

    if not t.report_number:
        last_txn = Transaction.query.filter(
            Transaction.report_number != None
        ).order_by(Transaction.id.desc()).first()

        if last_txn and last_txn.report_number.startswith("ref"):
            last_num = int(last_txn.report_number.replace("ref", ""))
            t.report_number = f"ref{last_num + 1}"
        else:
            t.report_number = "ref1001"

    # توليد رمز تحقق إن لم يوجد
    if not t.verification_token:
        t.verification_token = generate_verification_token()
    db.session.commit()

    # بعد db.session.commit() في upload_report
    finance = User.query.filter_by(role="finance").first()
    employee = User.query.filter_by(username=t.employee).first()

    if finance:
        send_notification(finance.id, "📄 تقرير جديد", f"تم رفع تقرير للمعاملة رقم {t.id}")
    if employee:
        send_notification(employee.id, "📄 تقرير جاهز", f"تم رفع التقرير للمعاملة رقم {t.id}")

    flash(f"✅ تم رفع التقرير (الرقم المرجعي: {t.report_number})", "success")

    role = session.get("role")
    if role == "engineer":
        return redirect(url_for("engineer_transaction_details", tid=tid))
    else:
        return redirect(url_for("reports_page"))

@app.route("/reports", endpoint="reports_page")
def reports():

    if session.get("role") not in ["manager", "admin", "finance" ,"employee" ,"engineer"]:
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()
    query = Transaction.query

    if q:
        query = query.filter(Transaction.report_number.contains(q))

    reports = query.filter(Transaction.report_file != None).order_by(Transaction.date.desc()).all()

    return render_template("reports.html", reports=reports, q=q)



    
# ---------------- صفحة المالية ----------------
@app.route("/finance", methods=["GET", "POST"])
def finance_dashboard():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # ✅ المعاملات الخاصة بالفرع
    transactions = Transaction.query.filter_by(branch_id=user.branch_id).all()

    # ✅ إضافة مصروف خاص بالفرع
    if request.method == "POST" and "expense_name" in request.form:
        expense_name = request.form["expense_name"]
        amount = float(request.form.get("amount") or 0)
        file = request.files.get("file")
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        e = Expense(
            description=expense_name,
            amount=amount,
            file=filename,
            branch_id=user.branch_id
        )
        db.session.add(e)
        db.session.commit()
        flash("✅ تم تسجيل المصروف", "success")
        return redirect(url_for("finance_dashboard"))

    # ✅ فقط المعاملات غير المدفوعة لهذا الفرع
    unpaid_transactions = Transaction.query.filter_by(
        payment_status="غير مدفوعة",
        branch_id=user.branch_id
    ).all()

    # ✅ المدفوعات الخاصة بمعاملات هذا الفرع
    paid_transactions = Payment.query.join(Transaction).filter(
        Transaction.branch_id == user.branch_id
    ).order_by(Payment.id.desc()).all()

    # ✅ مجموع الدخل للفرع فقط
    total_income = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))\
        .join(Transaction)\
        .filter(Transaction.branch_id == user.branch_id).scalar() or 0.0

    # ✅ مصاريف الفرع فقط
    expenses = Expense.query.filter_by(branch_id=user.branch_id).order_by(Expense.id.desc()).all()

    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0))\
        .filter(Expense.branch_id == user.branch_id).scalar() or 0.0

    net_profit = total_income - total_expenses

    # ✅ بيانات العروض والفواتير للبنوك لعرضها بسرعة في لوحة المالية
    banks = Bank.query.order_by(Bank.name.asc()).all()
    # استبعاد العروض المنتهية من العرض السريع
    now_utc = datetime.utcnow()
    recent_quotes = Quote.query \
        .filter(or_(Quote.valid_until == None, Quote.valid_until >= now_utc)) \
        .order_by(Quote.id.desc()).limit(20).all()
    recent_bank_invoices = BankInvoice.query.order_by(BankInvoice.id.desc()).limit(20).all()
    recent_customer_quotes = CustomerQuote.query \
        .filter(or_(CustomerQuote.valid_until == None, CustomerQuote.valid_until >= now_utc)) \
        .order_by(CustomerQuote.id.desc()).limit(20).all()
    recent_customer_invoices = CustomerInvoice.query.order_by(CustomerInvoice.id.desc()).limit(20).all()

    return render_template(
        "finance.html",
        transactions=unpaid_transactions,
        expenses=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=net_profit,
        banks=banks,
        recent_quotes=recent_quotes,
        recent_bank_invoices=recent_bank_invoices,
        recent_customer_quotes=recent_customer_quotes,
        recent_customer_invoices=recent_customer_invoices,
        vat_default_percent=int(_get_vat_rate() * 100)
    )

# ---------------- صفحة المعاملات المدفوعة (مالية) ----------------
@app.route("/finance/paid")
def finance_paid():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # معاملات هذا الفرع التي لديها مدفوعات
    payments = Payment.query.join(Transaction).filter(
        Transaction.branch_id == user.branch_id
    ).order_by(Payment.id.desc()).all()

    total_income = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))\
        .join(Transaction)\
        .filter(Transaction.branch_id == user.branch_id).scalar() or 0.0

    return render_template("finance_paid.html", payments=payments, total_income=total_income)

# ---------------- إدارة قوالب وورد (مالية) ----------------
@app.route("/finance/templates")
def finance_templates():
    if session.get("role") not in ["finance", "manager"]:
        return redirect(url_for("login"))

    # 🆕 عرض القالب الحالي للفرع الحالي لموظف المالية + العام
    user = User.query.get(session.get("user_id"))
    current_branch_id = getattr(user, "branch_id", None)
    templates = {
        "invoice": get_template_filename("invoice", current_branch_id) or get_template_filename("invoice", None),
        "quote": get_template_filename("quote", current_branch_id) or get_template_filename("quote", None),
    }
    branches = Branch.query.order_by(Branch.name.asc()).all()
    return render_template("finance_templates.html", templates=templates, branches=branches, current_branch_id=current_branch_id)

def _replace_placeholders_in_xml_bytes(xml_bytes: bytes, mapping: dict) -> bytes:
    try:
        text = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = xml_bytes.decode("latin-1")
    for key, value in mapping.items():
        placeholder = "{" + str(key) + "}"
        replacement = str(value)
        if placeholder in text:
            text = text.replace(placeholder, replacement)
    return text.encode("utf-8")


def _fill_docx_from_template_xml(template_path: str, out_path: str, mapping: dict) -> None:
    import zipfile
    with zipfile.ZipFile(template_path, "r") as zin:
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.startswith("word/") and info.filename.lower().endswith(".xml"):
                    data = _replace_placeholders_in_xml_bytes(data, mapping)
                zout.writestr(info, data)


def _set_paragraph_rtl(paragraph, rtl: bool = True) -> None:
    try:
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        pPr = paragraph._p.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        bidi.set(qn('w:val'), '1' if rtl else '0')
        pPr.append(bidi)
    except Exception:
        pass


def _generate_default_docx(doc_type: str, placeholders: dict, out_path: str) -> None:
    # ينشئ ملف DOCX افتراضي عربي منسق كجدول لفاتورة/عرض سعر
    from docx import Document as DocxDocument
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    document = DocxDocument()

    # ترويسة
    header_p = document.add_paragraph()
    header_text = "invoice" if doc_type == "invoice" else "عرض سعر"
    run = header_p.add_run(header_text)
    run.bold = True
    try:
        run.font.size = Pt(16)
        run.font.name = "Arial"
    except Exception:
        pass
    header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_paragraph_rtl(header_p, True)

    document.add_paragraph().add_run(" ")

    # ملخص أساسي
    meta_pairs = [
        ("رقم العملية", placeholders.get("TRANSACTION_ID", "")),
        ("التاريخ", placeholders.get("DATE", "")),
        ("العميل", placeholders.get("CLIENT_NAME", placeholders.get("NAME", ""))),
        ("الموظف", placeholders.get("EMPLOYEE", "")),
        ("البنك", placeholders.get("BANK_NAME", "")),
        ("فرع البنك", placeholders.get("BANK_BRANCH", "")),
    ]

    table = document.add_table(rows=0, cols=2)
    try:
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
    except Exception:
        pass

    for label, value in meta_pairs:
        row_cells = table.add_row().cells
        lc = row_cells[0].paragraphs[0]
        lr = lc.add_run(str(label))
        lr.bold = True
        try:
            lr.font.name = "Arial"; lr.font.size = Pt(11)
        except Exception:
            pass
        _set_paragraph_rtl(lc, True)
        lc.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        rc = row_cells[1].paragraphs[0]
        rr = rc.add_run(str(value))
        try:
            rr.font.name = "Arial"; rr.font.size = Pt(11)
        except Exception:
            pass
        _set_paragraph_rtl(rc, True)
        rc.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    document.add_paragraph().add_run(" ")

    # جدول المبلغ والضريبة والإجمالي
    amounts = [
        ("السعر قبل الضريبة", placeholders.get("PRICE", placeholders.get("AMOUNT", "0.00"))),
        ("الضريبة", placeholders.get("TAX", "0.00")),
        ("الإجمالي بعد الضريبة", placeholders.get("TOTAL_PRICE", placeholders.get("TOTAL", "0.00"))),
    ]

    amt_table = document.add_table(rows=1, cols=3)
    try:
        amt_table.style = 'Table Grid'
        amt_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    except Exception:
        pass

    hdr_cells = amt_table.rows[0].cells
    headers = ["البند", "القيمة", "العملة"]
    for idx, text in enumerate(headers):
        p = hdr_cells[idx].paragraphs[0]
        r = p.add_run(text)
        r.bold = True
        try:
            r.font.name = "Arial"; r.font.size = Pt(11)
        except Exception:
            pass
        _set_paragraph_rtl(p, True)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for label, value in amounts:
        row = amt_table.add_row().cells
        p0 = row[0].paragraphs[0]
        r0 = p0.add_run(label)
        r0.bold = True
        _set_paragraph_rtl(p0, True)
        p0.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        p1 = row[1].paragraphs[0]
        p1.add_run(str(value))
        _set_paragraph_rtl(p1, True)
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER

        p2 = row[2].paragraphs[0]
        p2.add_run("ريال")
        _set_paragraph_rtl(p2, True)
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_paragraph().add_run(" ")

    # تفاصيل إضافية
    details_title = document.add_paragraph()
    dr = details_title.add_run("التفاصيل")
    dr.bold = True
    _set_paragraph_rtl(details_title, True)
    details_title.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    details_p = document.add_paragraph()
    details_p.add_run(placeholders.get("DETAILS", ""))
    _set_paragraph_rtl(details_p, True)
    details_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # أرقام المستند
    ref_p = document.add_paragraph()
    ref_text = placeholders.get("INVOICE_NO") or placeholders.get("QUOTE_NO") or placeholders.get("QUTE_NO")
    if ref_text:
        ref_run = ref_p.add_run(f"المرجع: {ref_text}")
        ref_run.bold = True
    _set_paragraph_rtl(ref_p, True)
    ref_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # حفظ
    document.save(out_path)
def _render_docx_from_template(doc_type: str, placeholders: dict, out_name: str, branch_id: int | None = None):
    template_filename = get_template_filename(doc_type, branch_id)
    output_path = os.path.join(app.config["UPLOAD_FOLDER"], out_name)
    if not template_filename:
        # لا يوجد قالب مرفوع: أنشئ ملف DOCX افتراضي عربي منسق
        try:
            _generate_default_docx(doc_type, placeholders, output_path)
            return send_file(output_path, as_attachment=True, download_name=out_name)
        except Exception:
            flash("⚠️ تعذر إنشاء القالب الافتراضي", "warning")
            return redirect(url_for("finance_templates"))
    else:
        path = os.path.join(app.config["UPLOAD_FOLDER"], template_filename)
        _fill_docx_from_template_xml(path, output_path, placeholders)
        return send_file(output_path, as_attachment=True, download_name=out_name)


def _get_vat_rate() -> float:
    # ثابت: ضريبة قيمة مضافة 5%
    return 0.05


def _compute_tax_and_total(base_amount: float) -> tuple[float, float]:
    vat = _get_vat_rate()
    tax = round((base_amount or 0.0) * vat, 2)
    total = round((base_amount or 0.0) + tax, 2)
    return tax, total


def _sanitize_description(raw_text: str, transaction: Transaction | None = None) -> str:
    """إزالة أي ذكر لحالة المعاملة من الوصف/الملاحظات قبل الطباعة.

    - يحذف صراحة قيمة حالة المعاملة إن توفرت
    - يحذف المقاطع التي تبدأ بـ "الحالة:" أو "حالة المعاملة:" حتى نهاية السطر
    - يحذف أشهر العبارات المستخدمة كحالة
    - ينظف الفواصل الزائدة في النهاية
    """
    if not raw_text:
        return ""
    try:
        text = str(raw_text)
        # إزالة قيمة حالة المعاملة إن وُجدت
        if transaction is not None and getattr(transaction, "status", None):
            status_value = str(transaction.status or "").strip()
            if status_value:
                text = text.replace(status_value, "")

        # إزالة الأنماط النصية الشائعة للحالة
        patterns = [
            r"\bالحالة\s*(?:الحالية)?\s*[:：]\s*.*$",
            r"\bحالة\s*(?:المعاملة|الفاتورة|الطلب)?\s*[:：]\s*.*$",
        ]
        for pat in patterns:
            text = re.sub(pat, "", text).strip()

        # إزالة أشهر قيم الحالة المعروفة في النظام
        known_statuses = (
            "بانتظار المهندس",
            "قيد المعاينة",
            "قيد التنفيذ",
            "مرفوضة",
            "بانتظار الدفع",
            "مكتملة",
            "منجزة",
            "📑 تقرير مرفوع",
            "📑 تقرير مبدئي",
        )
        for s in known_statuses:
            text = text.replace(s, "")

        # تنظيف فواصل/رموز زائدة في نهاية النص
        text = re.sub(r"[\-\|\(\)\[\]·•،،:,\s]+$", "", text).strip()
        return text
    except Exception:
        return str(raw_text)

@app.route("/finance/templates/quote/<int:transaction_id>")
def download_quote_doc(transaction_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    t = Transaction.query.get_or_404(transaction_id)
    bank_name = None
    if t.bank_id:
        bank = Bank.query.get(t.bank_id)
        bank_name = bank.name if bank else None
    amount = float(t.fee or 0)
    # تخصيص الوصف والضريبة
    details_override = (request.args.get("details") or "").strip()
    apply_vat = (request.args.get("apply_vat") or "1") == "1"
    vat_percent = request.args.get("vat")
    if vat_percent is not None:
        try:
            os.environ["VAT_RATE"] = str(float(vat_percent) / 100.0)
        except Exception:
            pass
    tax, total_with_tax = _compute_tax_and_total(amount) if apply_vat else (0.0, amount)
    placeholders = {
        "NAME": t.client or "",
        "CLIENT_NAME": t.client or "",
        "AMOUNT": f"{amount:.2f}",
        "PRICE": f"{amount:.2f}",
        "TAX": f"{tax:.2f}",
        "TOTAL_PRICE": f"{total_with_tax:.2f}",
        # للحفاظ على التوافق مع القوالب القديمة
        "TOTAL": f"{amount:.2f}",
        "DATE": datetime.utcnow().strftime("%Y-%m-%d"),
        "DETAILS": details_override or "رسوم التثمين",
        "QUOTE_NO": f"QUOTE-{t.id}",
        "QUTE_NO": f"QUOTE-{t.id}",
        "TRANSACTION_ID": str(t.id),
        "EMPLOYEE": t.employee or "",
        "BANK_NAME": bank_name or "",
        "BANK_BRANCH": t.bank_branch or "",
        "STATE": t.state or "",
        "REGION": t.region or "",
        "AREA": str(t.area or 0),
        "BUILDING_AREA": str(t.building_area or 0),
        "BUILDING_AGE": str(t.building_age or 0),
        "LAND_VALUE": f"{float(t.land_value or 0):.2f}",
        "BUILDING_VALUE": f"{float(t.building_value or 0):.2f}",
        "TOTAL_ESTIMATE": f"{float(t.total_estimate or 0):.2f}",
    }
    out_name = f"quote_{t.id}.docx"
    return _render_docx_from_template(
        "quote",
        placeholders,
        out_name,
        branch_id=t.branch_id,
    )

@app.route("/finance/templates/invoice/<int:transaction_id>")
def download_invoice_doc(transaction_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    t = Transaction.query.get_or_404(transaction_id)
    bank_name = None
    if t.bank_id:
        bank = Bank.query.get(t.bank_id)
        bank_name = bank.name if bank else None
    amount = float(t.fee or 0)
    # تخصيص الوصف والضريبة
    details_override = (request.args.get("details") or "").strip()
    apply_vat = (request.args.get("apply_vat") or "1") == "1"
    vat_percent = request.args.get("vat")
    if vat_percent is not None:
        try:
            os.environ["VAT_RATE"] = str(float(vat_percent) / 100.0)
        except Exception:
            pass
    tax, total_with_tax = _compute_tax_and_total(amount) if apply_vat else (0.0, amount)
    placeholders = {
        "NAME": t.client or "",
        "CLIENT_NAME": t.client or "",
        "AMOUNT": f"{amount:.2f}",
        "PRICE": f"{amount:.2f}",
        "TAX": f"{tax:.2f}",
        "TOTAL_PRICE": f"{total_with_tax:.2f}",
        # للتوافق مع القوالب القديمة
        "TOTAL": f"{amount:.2f}",
        "DATE": datetime.utcnow().strftime("%Y-%m-%d"),
        "DETAILS": _sanitize_description(details_override or "رسوم التثمين", t),
        "INVOICE_NO": f"INV-{t.id}",
        "TRANSACTION_ID": str(t.id),
        "EMPLOYEE": t.employee or "",
        "BANK_NAME": bank_name or "",
        "BANK_BRANCH": t.bank_branch or "",
        "STATE": t.state or "",
        "REGION": t.region or "",
        "AREA": str(t.area or 0),
        "BUILDING_AREA": str(t.building_area or 0),
        "BUILDING_AGE": str(t.building_age or 0),
        "LAND_VALUE": f"{float(t.land_value or 0):.2f}",
        "BUILDING_VALUE": f"{float(t.building_value or 0):.2f}",
        "TOTAL_ESTIMATE": f"{float(t.total_estimate or 0):.2f}",
    }
    out_name = f"invoice_{t.id}.docx"
    return _render_docx_from_template(
        "invoice",
        placeholders,
        out_name,
        branch_id=t.branch_id,
    )

# ✅ طباعة فاتورة HTML احترافية للمعاملة
@app.route("/finance/print/invoice/<int:transaction_id>")
def print_invoice_html(transaction_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    t = Transaction.query.get_or_404(transaction_id)
    bank_name = None
    if t.bank_id:
        bank = Bank.query.get(t.bank_id)
        bank_name = bank.name if bank else None

    amount = float(t.fee or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)
    details_override = (request.args.get("details") or "").strip()

    # معلومات المؤسسة الافتراضية (يمكن لاحقًا ربطها من الإعدادات/الفرع)
    org_name = "شركة التثمين"
    org_meta = "العنوان · الهاتف · البريد الإلكتروني"

    return render_template(
        "print_invoice.html",
        transaction=t,
        bank_name=bank_name,
        amount=amount,
        tax=tax,
        total_with_tax=total_with_tax,
        vat_rate=_get_vat_rate(),
        date_str=(datetime.utcnow().strftime("%Y-%m-%d")),
        org_name=org_name,
        org_meta=org_meta,
        notes=_sanitize_description(details_override, t),
    )

# ✅ طباعة فاتورة بنك HTML بنفس تصميم الطباعة
@app.route("/finance/print/bank_invoice/<int:invoice_id>")
def print_bank_invoice_html(invoice_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    inv = BankInvoice.query.get_or_404(invoice_id)
    bank = Bank.query.get(inv.bank_id) if inv.bank_id else None
    transaction = Transaction.query.get(inv.transaction_id) if inv.transaction_id else None

    bank_name = bank.name if bank else None
    amount = float(inv.amount or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)
    details_override = (request.args.get("details") or "").strip()

    org_name = "شركة التثمين"
    org_meta = "العنوان · الهاتف · البريد الإلكتروني"

    return render_template(
        "print_invoice.html",
        # unified template
        transaction=transaction,
        bank_name=bank_name,
        amount=amount,
        tax=tax,
        total_with_tax=total_with_tax,
        vat_rate=_get_vat_rate(),
        date_str=(inv.issued_at or datetime.utcnow()).strftime("%Y-%m-%d"),
        org_name=org_name,
        org_meta=org_meta,
        notes=_sanitize_description(details_override or (inv.note or ""), transaction),
        # metadata for header
        badge_label="فاتورة",
        invoice_code=f"INV-BANK-{inv.id}",
        reference_code="INV-BANK",
        client_name=(transaction.client if transaction else (bank_name or "")),
        employee_name=(transaction.employee if transaction else "-"),
    )

# ✅ طباعة فاتورة عميل HTML بنفس تصميم الطباعة
@app.route("/finance/print/customer_invoice/<int:invoice_id>")
def print_customer_invoice_html(invoice_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    inv = CustomerInvoice.query.get_or_404(invoice_id)
    transaction = Transaction.query.get(inv.transaction_id) if inv.transaction_id else None

    bank_name = None
    if transaction and transaction.bank_id:
        bank = Bank.query.get(transaction.bank_id)
        bank_name = bank.name if bank else None

    amount = float(inv.amount or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)
    details_override = (request.args.get("details") or "").strip()

    org_name = "شركة التثمين"
    org_meta = "العنوان · الهاتف · البريد الإلكتروني"

    return render_template(
        "print_invoice.html",
        # unified template
        transaction=transaction,
        bank_name=bank_name,
        amount=amount,
        tax=tax,
        total_with_tax=total_with_tax,
        vat_rate=_get_vat_rate(),
        date_str=(inv.issued_at or datetime.utcnow()).strftime("%Y-%m-%d"),
        org_name=org_name,
        org_meta=org_meta,
        notes=_sanitize_description(details_override or (inv.note or ""), transaction),
        # metadata for header
        badge_label="فاتورة",
        invoice_code=f"INV-CUST-{inv.id}",
        reference_code="INV-CUST",
        client_name=(inv.customer_name or (transaction.client if transaction else "")),
        employee_name=(transaction.employee if transaction else "-"),
    )

# ✅ طباعة عرض سعر عميل HTML بنفس تصميم الطباعة
@app.route("/finance/print/customer_quote/<int:quote_id>")
def print_customer_quote_html(quote_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    q = CustomerQuote.query.get_or_404(quote_id)
    transaction = Transaction.query.get(q.transaction_id) if q.transaction_id else None

    bank_name = None
    if transaction and transaction.bank_id:
        bank = Bank.query.get(transaction.bank_id)
        bank_name = bank.name if bank else None

    amount = float(q.amount or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)

    org_name = "شركة التثمين"
    org_meta = "العنوان · الهاتف · البريد الإلكتروني"

    return render_template(
        "print_invoice.html",
        # unified template
        transaction=transaction,
        bank_name=bank_name,
        amount=amount,
        tax=tax,
        total_with_tax=total_with_tax,
        vat_rate=_get_vat_rate(),
        date_str=(q.valid_until or datetime.utcnow()).strftime("%Y-%m-%d"),
        org_name=org_name,
        org_meta=org_meta,
        notes=q.note or "",
        # metadata for header
        badge_label="عرض سعر",
        invoice_code=f"QUOTE-CUST-{q.id}",
        reference_code="QUOTE-CUST",
        client_name=(q.customer_name or (transaction.client if transaction else "")),
        employee_name=(transaction.employee if transaction else "-"),
    )

# ✅ تنزيل فاتورة بنك (من جدول BankInvoice)
@app.route("/finance/download/bank_invoice/<int:invoice_id>")
def download_bank_invoice_doc(invoice_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    inv = BankInvoice.query.get_or_404(invoice_id)
    bank = Bank.query.get(inv.bank_id)
    # اختيار الفرع: إن وجدت معاملة مرتبطة نستخدم فرعها، وإلا فرع موظف المالية
    preferred_branch_id = None
    transaction = None
    if inv.transaction_id:
        transaction = Transaction.query.get(inv.transaction_id)
        preferred_branch_id = transaction.branch_id if transaction else None
    if preferred_branch_id is None:
        user = User.query.get(session.get("user_id"))
        preferred_branch_id = getattr(user, "branch_id", None)

    amount = float(inv.amount or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)
    placeholders = {
        "NAME": (bank.name if bank else f"Bank #{inv.bank_id}"),
        "CLIENT_NAME": (bank.name if bank else f"Bank #{inv.bank_id}"),
        "AMOUNT": f"{amount:.2f}",
        "PRICE": f"{amount:.2f}",
        "TAX": f"{tax:.2f}",
        "TOTAL_PRICE": f"{total_with_tax:.2f}",
        # توافق قديم
        "TOTAL": f"{amount:.2f}",
        "DATE": (inv.issued_at or datetime.utcnow()).strftime("%Y-%m-%d"),
        "DETAILS": _sanitize_description(inv.note or "", transaction),
        "INVOICE_NO": f"INV-BANK-{inv.id}",
        "TRANSACTION_ID": str(inv.transaction_id or ""),
        "BANK_NAME": (bank.name if bank else ""),
    }
    # لو عندنا معاملة، نضيف تفاصيل إضافية
    if transaction:
        placeholders.update({
            "CLIENT_NAME": transaction.client or placeholders.get("CLIENT_NAME", ""),
            "BANK_BRANCH": transaction.bank_branch or "",
            "EMPLOYEE": transaction.employee or "",
            "STATE": transaction.state or "",
            "REGION": transaction.region or "",
            "AREA": str(transaction.area or 0),
            "BUILDING_AREA": str(transaction.building_area or 0),
            "BUILDING_AGE": str(transaction.building_age or 0),
            "LAND_VALUE": f"{float(transaction.land_value or 0):.2f}",
            "BUILDING_VALUE": f"{float(transaction.building_value or 0):.2f}",
            "TOTAL_ESTIMATE": f"{float(transaction.total_estimate or 0):.2f}",
        })

    out_name = f"bank_invoice_{inv.id}.docx"
    return _render_docx_from_template(
        "invoice",
        placeholders,
        out_name,
        branch_id=preferred_branch_id,
    )

# ✅ تنزيل فاتورة عميل (من جدول CustomerInvoice)
@app.route("/finance/download/customer_invoice/<int:invoice_id>")
def download_customer_invoice_doc(invoice_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    inv = CustomerInvoice.query.get_or_404(invoice_id)
    preferred_branch_id = None
    transaction = None
    if inv.transaction_id:
        transaction = Transaction.query.get(inv.transaction_id)
        preferred_branch_id = transaction.branch_id if transaction else None
    if preferred_branch_id is None:
        user = User.query.get(session.get("user_id"))
        preferred_branch_id = getattr(user, "branch_id", None)

    amount = float(inv.amount or 0)
    tax, total_with_tax = _compute_tax_and_total(amount)
    placeholders = {
        "NAME": inv.customer_name or "",
        "CLIENT_NAME": inv.customer_name or "",
        "AMOUNT": f"{amount:.2f}",
        "PRICE": f"{amount:.2f}",
        "TAX": f"{tax:.2f}",
        "TOTAL_PRICE": f"{total_with_tax:.2f}",
        # توافق قديم
        "TOTAL": f"{amount:.2f}",
        "DATE": (inv.issued_at or datetime.utcnow()).strftime("%Y-%m-%d"),
        "DETAILS": _sanitize_description(inv.note or "", transaction),
        "INVOICE_NO": f"INV-CUST-{inv.id}",
        "TRANSACTION_ID": str(inv.transaction_id or ""),
    }
    if transaction:
        bank_name = None
        if transaction.bank_id:
            bank = Bank.query.get(transaction.bank_id)
            bank_name = bank.name if bank else None
        placeholders.update({
            "BANK_NAME": bank_name or "",
            "BANK_BRANCH": transaction.bank_branch or "",
            "STATE": transaction.state or "",
            "REGION": transaction.region or "",
            "AREA": str(transaction.area or 0),
            "BUILDING_AREA": str(transaction.building_area or 0),
            "BUILDING_AGE": str(transaction.building_age or 0),
            "LAND_VALUE": f"{float(transaction.land_value or 0):.2f}",
            "BUILDING_VALUE": f"{float(transaction.building_value or 0):.2f}",
            "TOTAL_ESTIMATE": f"{float(transaction.total_estimate or 0):.2f}",
        })

    out_name = f"customer_invoice_{inv.id}.docx"
    return _render_docx_from_template(
        "invoice",
        placeholders,
        out_name,
        branch_id=preferred_branch_id,
    )

# ✅ تنزيل عرض سعر عميل (من جدول CustomerQuote)
@app.route("/finance/download/customer_quote/<int:quote_id>")
def download_customer_quote_doc(quote_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))
    q = CustomerQuote.query.get_or_404(quote_id)
    preferred_branch_id = None
    transaction = None
    if q.transaction_id:
        transaction = Transaction.query.get(q.transaction_id)
        preferred_branch_id = transaction.branch_id if transaction else None
    if preferred_branch_id is None:
        user = User.query.get(session.get("user_id"))
        preferred_branch_id = getattr(user, "branch_id", None)

    placeholders = {
        "NAME": q.customer_name or "",
        "CLIENT_NAME": q.customer_name or "",
        "AMOUNT": f"{float(q.amount or 0):.2f}",
        "PRICE": f"{float(q.amount or 0):.2f}",
        "TOTAL": f"{float(q.amount or 0):.2f}",
        "DATE": datetime.utcnow().strftime("%Y-%m-%d"),
        "DETAILS": q.note or "",
        "QUOTE_NO": f"QUOTE-CUST-{q.id}",
        "QUTE_NO": f"QUOTE-CUST-{q.id}",
        "TRANSACTION_ID": str(q.transaction_id or ""),
        "VALID_UNTIL": q.valid_until.strftime("%Y-%m-%d") if q.valid_until else "",
    }
    if transaction:
        bank_name = None
        if transaction.bank_id:
            bank = Bank.query.get(transaction.bank_id)
            bank_name = bank.name if bank else None
        placeholders.update({
            "BANK_NAME": bank_name or "",
            "BANK_BRANCH": transaction.bank_branch or "",
            "STATE": transaction.state or "",
            "REGION": transaction.region or "",
            "AREA": str(transaction.area or 0),
            "BUILDING_AREA": str(transaction.building_area or 0),
            "BUILDING_AGE": str(transaction.building_age or 0),
            "LAND_VALUE": f"{float(transaction.land_value or 0):.2f}",
            "BUILDING_VALUE": f"{float(transaction.building_value or 0):.2f}",
            "TOTAL_ESTIMATE": f"{float(transaction.total_estimate or 0):.2f}",
        })

    out_name = f"customer_quote_{q.id}.docx"
    return _render_docx_from_template(
        "quote",
        placeholders,
        out_name,
        branch_id=preferred_branch_id,
    )

# ✅ إضافة دفعة جديدة
@app.route("/add_payment/<int:tid>", methods=["POST"])
def add_payment(tid):
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    transaction = Transaction.query.get_or_404(tid)

    # 🚨 منع التلاعب: لازم تكون المعاملة لنفس فرع موظف المالية
    if transaction.branch_id != user.branch_id:
        flash("⛔ غير مسموح تعديل معاملات من فرع آخر", "danger")
        return redirect(url_for("finance_dashboard"))

    amount = float(request.form.get("amount") or 0)
    if amount > 0:
        receipt = request.files.get("receipt_file")
        filename = None
        if receipt and receipt.filename:
            filename = secure_filename(receipt.filename)
            receipt.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        payment = Payment(
            transaction_id=transaction.id,
            amount=amount,
            method=request.form.get("method"),
            receipt_file=filename,
            date_received=datetime.utcnow(),
            received_by=session.get("username")
        )
        db.session.add(payment)
        db.session.commit()

        total_paid = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))\
                               .filter_by(transaction_id=transaction.id).scalar() or 0.0
        transaction.payment_status = "مدفوعة" if total_paid >= transaction.fee else "غير مدفوعة"
        db.session.commit()
        flash("✅ تم تسجيل الدفعة بنجاح", "success")
    return redirect(url_for("finance_dashboard"))

# ✅ إنشاء عرض سعر للبنك (من المالية)
@app.route("/finance/quotes", methods=["POST"])
def finance_create_quote():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    bank_id = int(request.form.get("bank_id"))
    amount = float(request.form.get("amount") or 0)
    valid_until_str = request.form.get("valid_until")
    note = request.form.get("note")
    transaction_id = request.form.get("transaction_id")

    valid_until_dt = None
    if valid_until_str:
        try:
            valid_until_dt = datetime.fromisoformat(valid_until_str)
        except Exception:
            valid_until_dt = None

    q = Quote(
        bank_id=bank_id,
        amount=amount,
        valid_until=valid_until_dt,
        note=note,
        transaction_id=int(transaction_id) if transaction_id else None,
        created_by=session.get("user_id"),
    )
    db.session.add(q)
    db.session.commit()
    flash("✅ تم إنشاء عرض السعر", "success")
    return redirect(url_for("download_customer_quote_doc", quote_id=q.id))

# ✅ إنشاء فاتورة بنك بمبلغ محدد (مرحلة الإصدار)
@app.route("/finance/bank_invoices", methods=["POST"])
def finance_create_bank_invoice():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    bank_id = int(request.form.get("bank_id"))
    amount = float(request.form.get("amount") or 0)
    transaction_id = request.form.get("transaction_id")
    note = request.form.get("note")

    inv = BankInvoice(
        bank_id=bank_id,
        amount=amount,
        transaction_id=int(transaction_id) if transaction_id else None,
        note=note,
        issued_at=datetime.utcnow(),
    )
    db.session.add(inv)
    db.session.commit()
    flash("✅ تم إنشاء فاتورة البنك", "success")
    return redirect(url_for("print_bank_invoice_html", invoice_id=inv.id) + "?auto=1")

# ✅ تحديث حالة فاتورة البنك (تسليم / استلام)
@app.route("/finance/bank_invoices/<int:invoice_id>/status", methods=["POST"])
def finance_update_bank_invoice_status(invoice_id: int):
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    action = (request.form.get("action") or "").strip().lower()
    invoice = BankInvoice.query.get_or_404(invoice_id)

    if action == "deliver":
        invoice.delivered_at = datetime.utcnow()
        db.session.commit()
        flash("✅ تم تحديث حالة الفاتورة: تم التسليم", "success")
    elif action == "receive":
        invoice.received_at = datetime.utcnow()
        db.session.commit()

        # عند تأكيد الاستلام، نسجل الدخل كـ Payment لفرع المعاملة (إن وُجدت)
        created_income = False
        if invoice.transaction_id:
            t = Transaction.query.get(invoice.transaction_id)
            if t:
                # نتجنب التكرار: نتحقق من وجود دفعة بنفس المبلغ والطريقة "بنك"
                existing_payment = Payment.query.filter_by(
                    transaction_id=t.id,
                    amount=invoice.amount,
                    method="بنك",
                ).first()
                if not existing_payment:
                    p = Payment(
                        transaction_id=t.id,
                        amount=invoice.amount,
                        method="بنك",
                        date_received=datetime.utcnow(),
                        received_by=session.get("username"),
                    )
                    db.session.add(p)
                    db.session.commit()
                    created_income = True

                # ✅ بعد تسجيل/تأكيد الدفعة، نعيد احتساب حالة الدفع للمعاملة
                total_paid = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))\
                    .filter_by(transaction_id=t.id).scalar() or 0.0
                t.payment_status = "مدفوعة" if total_paid >= t.fee else "غير مدفوعة"
                db.session.commit()

        if created_income:
            flash("✅ تم تحديث الحالة وإضافة الدخل للفرع", "success")
        else:
            flash("✅ تم تحديث الحالة. ⚠️ لم يُسجل دخل تلقائيًا (لا توجد معاملة مرتبطة)", "warning")
    else:
        flash("⚠️ إجراء غير معروف", "warning")

    return redirect(url_for("finance_dashboard"))

# ✅ إنشاء عرض سعر للعميل (من المالية)
@app.route("/finance/customer_quotes", methods=["POST"])
def finance_create_customer_quote():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    customer_name = (request.form.get("customer_name") or "").strip()
    amount = float(request.form.get("amount") or 0)
    valid_until_str = request.form.get("valid_until")
    note = request.form.get("note")
    transaction_id = request.form.get("transaction_id")

    if not customer_name:
        flash("⛔ اسم العميل مطلوب", "danger")
        return redirect(url_for("finance_dashboard"))

    valid_until_dt = None
    if valid_until_str:
        try:
            valid_until_dt = datetime.fromisoformat(valid_until_str)
        except Exception:
            valid_until_dt = None

    q = CustomerQuote(
        customer_name=customer_name,
        amount=amount,
        valid_until=valid_until_dt,
        note=note,
        transaction_id=int(transaction_id) if transaction_id else None,
        created_by=session.get("user_id"),
    )
    db.session.add(q)
    db.session.commit()
    flash("✅ تم إنشاء عرض السعر للعميل", "success")
    return redirect(url_for("print_customer_quote_html", quote_id=q.id) + "?auto=1")

# ✅ إنشاء فاتورة للعميل (من المالية)
@app.route("/finance/customer_invoices", methods=["POST"])
def finance_create_customer_invoice():
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    customer_name = (request.form.get("customer_name") or "").strip()
    amount = float(request.form.get("amount") or 0)
    note = request.form.get("note")
    transaction_id = request.form.get("transaction_id")

    if not customer_name:
        flash("⛔ اسم العميل مطلوب", "danger")
        return redirect(url_for("finance_dashboard"))

    inv = CustomerInvoice(
        customer_name=customer_name,
        amount=amount,
        note=note,
        transaction_id=int(transaction_id) if transaction_id else None,
        created_by=session.get("user_id"),
    )
    db.session.add(inv)
    db.session.commit()
    flash("✅ تم إنشاء فاتورة العميل", "success")
    return redirect(url_for("print_customer_invoice_html", invoice_id=inv.id) + "?auto=1")

# ---------------- صفحة البنوك: نظرة عامة ----------------
@app.route("/banks")
def banks_overview():
    if session.get("role") not in ["manager", "finance"]:
        return redirect(url_for("login"))

    # فلترة بالتاريخ (اختياري)
    start_date_str = request.args.get("start")
    end_date_str = request.args.get("end")
    start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

    tx_query = db.session.query(Bank.id, Bank.name, func.count(Transaction.id))\
        .outerjoin(Transaction, Transaction.bank_id == Bank.id)
    if start_date:
        tx_query = tx_query.filter(Transaction.date >= start_date)
    if end_date:
        tx_query = tx_query.filter(Transaction.date <= end_date)

    banks_stats = tx_query.group_by(Bank.id, Bank.name)\
        .order_by(Bank.name.asc()).all()

    banks_list = [
        {"id": b_id, "name": b_name, "count": tx_count}
        for (b_id, b_name, tx_count) in banks_stats
    ]

    return render_template("banks.html", banks=banks_list, start=start_date_str, end=end_date_str)


# ---------------- صفحة بنك محدد: تفاصيل وإحصائيات ----------------
@app.route("/banks/<int:bank_id>")
def bank_detail(bank_id):
    if session.get("role") not in ["manager", "finance"]:
        return redirect(url_for("login"))

    bank = Bank.query.get_or_404(bank_id)

    # فلترة بالتاريخ (اختياري)
    start_date_str = request.args.get("start")
    end_date_str = request.args.get("end")
    start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

    # إحصائية عدد المعاملات لكل فرع بنك لهذا البنك
    br_query = db.session.query(
        Transaction.bank_branch.label("bank_branch"),
        func.count(Transaction.id)
    ).filter(
        Transaction.bank_id == bank_id,
        Transaction.bank_branch.isnot(None),
        func.length(func.trim(Transaction.bank_branch)) > 0
    )
    if start_date:
        br_query = br_query.filter(Transaction.date >= start_date)
    if end_date:
        br_query = br_query.filter(Transaction.date <= end_date)
    branch_rows = br_query.group_by(text("bank_branch")).order_by(text("bank_branch ASC")).all()
    branch_stats = [
        {"name": (bname or "غير محدد"), "count": bcount}
        for (bname, bcount) in branch_rows
    ]

    total_tx = sum(b["count"] for b in branch_stats)

    # الفواتير المرتبطة بمعاملات هذا البنك (اعتماداً على جدول Payments)
    pay_query = Payment.query.join(Transaction, Payment.transaction_id == Transaction.id)\
        .filter(Transaction.bank_id == bank_id)
    if start_date:
        pay_query = pay_query.filter(Payment.date_received >= start_date)
    if end_date:
        pay_query = pay_query.filter(Payment.date_received <= end_date)
    payments = pay_query.order_by(Payment.date_received.desc()).all()

    # المستندات المرتبطة بمعاملات هذا البنك
    # ملاحظة: نعرضها دائمًا بدون أي فلترة حسب التاريخ بناءً على طلب المستخدم
    txs = (
        Transaction.query
        .filter(Transaction.bank_id == bank_id)
        .order_by(Transaction.id.desc())
        .all()
    )
    documents = []
    for t in txs:
        # ملفات متعددة محفوظة كسلسلة مفصولة بفواصل
        if t.files:
            for fname in (t.files or "").split(","):
                fname = (fname or "").strip()
                if fname:
                    documents.append({"transaction_id": t.id, "filename": fname})
        # لا نعرض ملفات التقارير هنا حسب الطلب
        # ملفات البنك التي رفعها الموظف
        if getattr(t, "bank_sent_files", None):
            for fname in (t.bank_sent_files or "").split(","):
                fname = (fname or "").strip()
                if fname:
                    documents.append({"transaction_id": t.id, "filename": fname})

    # 📨 مستندات عامة مرسلة للبنك (غير مرتبطة بمعاملة)
    try:
        general_docs = BankDocument.query.filter_by(bank_id=bank_id).order_by(BankDocument.id.desc()).all()
    except Exception:
        general_docs = []

    # فواتير البنك بمراحلها (إن وُجدت)
    inv_query = BankInvoice.query.filter_by(bank_id=bank_id)
    if start_date:
        inv_query = inv_query.filter(
            or_(
                BankInvoice.issued_at >= start_date,
                BankInvoice.delivered_at >= start_date,
                BankInvoice.received_at >= start_date,
            )
        )
    if end_date:
        inv_query = inv_query.filter(
            or_(
                BankInvoice.issued_at <= end_date,
                BankInvoice.delivered_at <= end_date,
                BankInvoice.received_at <= end_date,
            )
        )
    invoices = inv_query.order_by(BankInvoice.id.desc()).all()

    # ✅ ملخص للفواتير والمراحل (للإظهار كملخص عند المدير)
    total_invoices = len(invoices)
    total_amount = sum((inv.amount or 0) for inv in invoices)
    issued_count = sum(1 for inv in invoices if inv.issued_at)
    delivered_count = sum(1 for inv in invoices if inv.delivered_at)
    received_count = sum(1 for inv in invoices if inv.received_at)
    pending_count = total_invoices - received_count

    invoice_summary = {
        "total_invoices": total_invoices,
        "total_amount": total_amount,
        "issued_count": issued_count,
        "delivered_count": delivered_count,
        "received_count": received_count,
        "pending_count": pending_count,
    }

    return render_template(
        "bank_detail.html",
        bank=bank,
        branches=branch_stats,
        total_tx=total_tx,
        payments=payments,
        documents=documents,
        general_docs=general_docs,
        invoices=invoices,
        invoice_summary=invoice_summary,
        start=start_date_str,
        end=end_date_str,
    )


# ---------------- مستندات وفواتير الفروع (عرض فقط للمدير) ----------------
@app.route("/branch_documents", methods=["GET"])
def branch_documents():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    branches = Branch.query.order_by(Branch.name.asc()).all()

    # فلترة اختيارية بالفرع
    selected_branch_id = request.args.get("branch_id")
    q = BranchDocument.query
    if selected_branch_id:
        q = q.filter_by(branch_id=int(selected_branch_id))
    docs = q.order_by(BranchDocument.expires_at.asc().nulls_last()).all()

    # تصنيف المستندات
    now = datetime.utcnow()
    def status_for(doc):
        if not doc.expires_at:
            return "بدون انتهاء"
        delta = (doc.expires_at - now).days
        if delta < 0:
            return "منتهي"
        if delta <= 30:
            return "قريب الانتهاء"
        return "ساري"

    return render_template(
        "branch_documents.html",
        branches=branches,
        docs=docs,
        selected_branch_id=selected_branch_id,
        status_for=status_for,
    )


# تحديث مراحل فاتورة بنك
@app.route("/banks/<int:bank_id>/invoice_stage", methods=["POST"]) 
def update_bank_invoice_stage(bank_id):
    # ✅ حصر إدخال وتحديث مراحل فواتير البنك على قسم المالية فقط
    if session.get("role") != "finance":
        return redirect(url_for("login"))

    action = request.form.get("action")  # issue/deliver/receive
    amount = float(request.form.get("amount") or 0)
    invoice_id = request.form.get("invoice_id")
    transaction_id = request.form.get("transaction_id")
    note = request.form.get("note")

    # أنشئ/حدث سجل الفاتورة
    invoice = None
    if invoice_id:
        invoice = BankInvoice.query.get(invoice_id)
    if not invoice:
        invoice = BankInvoice(bank_id=bank_id)
        if transaction_id:
            invoice.transaction_id = int(transaction_id)
        if amount:
            invoice.amount = amount
        db.session.add(invoice)
        db.session.commit()

    now_ts = datetime.utcnow()
    if action == "issue":
        invoice.issued_at = now_ts
        if amount:
            invoice.amount = amount
    elif action == "deliver":
        invoice.delivered_at = now_ts
    elif action == "receive":
        invoice.received_at = now_ts
    if note:
        invoice.note = note
    db.session.commit()

    flash("✅ تم تحديث مرحلة الفاتورة", "success")
    return redirect(url_for("bank_detail", bank_id=bank_id, start=request.args.get('start'), end=request.args.get('end')))

# ---------------- إدارة الموظفين ----------------
@app.route("/manage_employees", methods=["GET", "POST"])
def manage_employees():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form["password"]
        role = request.form["role"]
        branch_id = request.form.get("branch_id")
        hashed_pw = generate_password_hash(password)
        user = User(username=username, password=hashed_pw, role=role, branch_id=branch_id)
        db.session.add(user)
        db.session.commit()
        flash("✅ تم إضافة الموظف بنجاح", "success")
        return redirect(url_for("manage_employees"))

    users = User.query.all()
    branches = Branch.query.all()
    return render_template("manage_employees.html", users=users, branches=branches)

@app.route("/manager/employees/delete/<int:uid>")
def delete_employee(uid):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    u = User.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    flash("✅ تم حذف الموظف", "success")
    return redirect(url_for("manage_employees"))

@app.route("/assign_branch/<int:uid>", methods=["POST"])
def assign_branch(uid):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    branch_id = request.form.get("branch_id")
    user = User.query.get_or_404(uid)
    if branch_id:
        user.branch_id = branch_id
        db.session.commit()
        flash("✅ تم تحديد فرع الموظف بنجاح", "success")
    return redirect(url_for("manager_dashboard"))

# ---------------- عرض الملفات ----------------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- صفحة التقارير المشتركة ----------------
@app.route("/employee/upload_bank_docs/<int:tid>", methods=["POST"])
def employee_upload_bank_docs(tid):
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    t = Transaction.query.get_or_404(tid)
    user = User.query.get(session["user_id"])
    # منع رفع ملفات لمعاملة من فرع آخر
    if t.branch_id != user.branch_id:
        flash("⛔ لا يمكنك رفع مستندات لمعالجة من فرع آخر", "danger")
        return redirect(url_for("employee_dashboard"))

    # تأكد من وجود بنك مرتبط بالمعاملة قبل قبول ملفات البنك
    if not t.bank_id:
        flash("⚠️ يجب ربط المعاملة ببنك قبل رفع مستندات البنك.", "warning")
        return redirect(url_for("employee_dashboard"))

    uploaded = request.files.getlist("bank_docs")
    saved = []
    for f in uploaded:
        if f and f.filename:
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            saved.append(fname)

    if saved:
        existing = (t.bank_sent_files or "").split(",") if t.bank_sent_files else []
        existing = [x.strip() for x in existing if x.strip()]
        t.bank_sent_files = ",".join(existing + saved)
        db.session.commit()
        flash("✅ تم رفع ملفات البنك وحفظها", "success")
    else:
        flash("⚠️ لم يتم اختيار أي ملف", "warning")

    return redirect(url_for("employee_dashboard"))

# ✅ رفع مستندات البنك بالبحث برقم المعاملة أو باسم العميل
@app.route("/employee/upload_bank_docs_lookup", methods=["POST"])
def employee_upload_bank_docs_lookup():
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    lookup_raw = (request.form.get("lookup") or "").strip()

    # تحويل الأرقام العربية/الفارسية إلى أرقام لاتينية لضمان المطابقة الصحيحة
    def normalize_digits(value: str) -> str:
        translation_table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
        return value.translate(translation_table)

    lookup = normalize_digits(lookup_raw)

    if not lookup:
        flash("⚠️ يرجى إدخال رقم المعاملة أو اسم العميل", "warning")
        return redirect(url_for("employee_dashboard"))

    # محاولة تفسيره كرقم معاملة أولًا (باستخراج الأرقام فقط من النص)
    t = None
    digits_only = "".join(ch for ch in lookup if ch.isdigit())
    if digits_only:
        try:
            tid = int(digits_only)
            t = Transaction.query.get(tid)
        except Exception:
            t = None

    # إن لم يكن رقم، نبحث بالاسم (يطابق جزئيًا أحدث معاملة)
    if not t:
        t = (
            Transaction.query
            .filter(Transaction.client.ilike(f"%{lookup}%"))
            .order_by(Transaction.id.desc())
            .first()
        )

    if not t:
        # تلميح للمستخدم حول الصيغة الصحيحة للبحث
        flash("❌ لم يتم العثور على معاملة بهذا الرقم أو الاسم. جرّب إدخال رقم المعاملة فقط أو اسم العميل الكامل.", "danger")
        return redirect(url_for("employee_dashboard"))

    user = User.query.get(session.get("user_id"))
    if not user:
        return redirect(url_for("login"))

    # منع رفع ملفات لمعاملة من فرع آخر
    if t.branch_id != user.branch_id:
        flash("⛔ لا يمكنك رفع مستندات لمعالجة من فرع آخر", "danger")
        return redirect(url_for("employee_dashboard"))

    # اختيار البنك (اختياري) لتثبيته على المعاملة إن كان فارغًا
    bank_id_form = request.form.get("bank_id")
    try:
        bank_id_val = int(bank_id_form) if bank_id_form else None
    except Exception:
        bank_id_val = None

    # إذا لم تكن المعاملة مرتبطة ببنك ولم يُحدد بنك في النموذج: لا نحفظ وثائق لن تظهر بأي بنك
    if not t.bank_id and not bank_id_val:
        flash("⚠️ المعاملة غير مرتبطة بأي بنك. يرجى اختيار البنك قبل رفع المستندات.", "warning")
        return redirect(url_for("employee_dashboard"))

    uploaded = request.files.getlist("bank_docs")
    saved = []
    for f in uploaded:
        if f and f.filename:
            fname = secure_filename(f.filename)
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            saved.append(fname)

    if saved:
        # في حال تم تحديد بنك في النموذج:
        # - إن لم تكن المعاملة مرتبطة ببنك نثبّت البنك المختار
        # - وإن كانت مرتبطة ببنك مختلف، نحدث الربط للبنك المختار لضمان ظهور المستندات في صفحة البنك الصحيحة
        if bank_id_val and (not t.bank_id or t.bank_id != bank_id_val):
            t.bank_id = bank_id_val
        existing = (t.bank_sent_files or "").split(",") if t.bank_sent_files else []
        existing = [x.strip() for x in existing if x.strip()]
        t.bank_sent_files = ",".join(existing + saved)
        db.session.commit()
        flash("✅ تم رفع ملفات البنك وحفظها", "success")
    else:
        flash("⚠️ لم يتم اختيار أي ملف", "warning")

    return redirect(url_for("employee_dashboard"))

# ✅ رفع مستند/رسالة عامة لبنك (غير مرتبطة بمعاملة)
@app.route("/employee/bank_documents", methods=["POST"])
def employee_add_bank_document():
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    user = User.query.get(session.get("user_id"))
    if not user:
        return redirect(url_for("login"))

    bank_id = request.form.get("bank_id")
    title = (request.form.get("title") or "").strip()
    message = (request.form.get("message") or "").strip()
    doc_type = (request.form.get("doc_type") or "").strip()
    file = request.files.get("file")

    try:
        bank_id_val = int(bank_id) if bank_id else None
    except Exception:
        bank_id_val = None

    if not bank_id_val:
        flash("⚠️ يرجى اختيار البنك", "warning")
        return redirect(url_for("employee_dashboard"))
    if not title:
        flash("⚠️ العنوان مطلوب", "warning")
        return redirect(url_for("employee_dashboard"))

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    try:
        doc = BankDocument(
            bank_id=bank_id_val,
            title=title,
            message=message,
            doc_type=doc_type or None,
            file=filename,
            created_by=user.id,
            branch_id=user.branch_id,
        )
        db.session.add(doc)
        db.session.commit()
        flash("✅ تم إرسال المستند/الرسالة إلى صفحة البنك", "success")
    except Exception as e:
        db.session.rollback()
        flash("❌ فشل الحفظ", "danger")

    return redirect(url_for("employee_dashboard"))

# ---------------- صفحة العملاء (إضافة/قائمة وتصدير CSV) ----------------
@app.route("/customers", methods=["GET", "POST"])
def customers_page():
    if session.get("role") not in ["manager", "employee", "finance"]:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if not name or not phone:
            flash("⚠️ يرجى إدخال الاسم والرقم", "warning")
            return redirect(url_for("customers_page"))
        c = Customer(name=name, phone=phone)
        db.session.add(c)
        db.session.commit()
        flash("✅ تم إضافة العميل", "success")
        return redirect(url_for("customers_page"))

    q = (request.args.get("q") or "").strip()
    query = Customer.query
    if q:
        query = query.filter(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
    customers = query.order_by(Customer.id.desc()).all()
    return render_template("customers.html", customers=customers, q=q)


@app.route("/customers/export.csv")
def customers_export_csv():
    if session.get("role") not in ["manager", "employee", "finance"]:
        return redirect(url_for("login"))
    import csv
    from io import StringIO

    q = (request.args.get("q") or "").strip()
    query = Customer.query
    if q:
        query = query.filter(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
    customers = query.order_by(Customer.id.desc()).all()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["id", "name", "phone"])  # header
    for c in customers:
        writer.writerow([c.id, c.name, c.phone])

    output = si.getvalue().encode("utf-8-sig")  # with BOM for Excel
    from flask import Response
    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=customers.csv"
        },
    )

# ✅ رفع مستندات الشركة بواسطة الموظف لفرعه
@app.route("/employee/branch_documents", methods=["POST"])
def employee_add_branch_document():
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    user = User.query.get(session.get("user_id"))
    if not user or not getattr(user, "branch_id", None):
        flash("⛔ لا يوجد فرع مرتبط بالمستخدم", "danger")
        return redirect(url_for("employee_dashboard"))

    title = (request.form.get("title") or "").strip()
    doc_type = (request.form.get("doc_type") or "").strip()
    issued_at = request.form.get("issued_at")
    expires_at = request.form.get("expires_at")
    file = request.files.get("file")

    if not title:
        flash("⚠️ يجب إدخال عنوان المستند", "warning")
        return redirect(url_for("employee_dashboard"))

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    doc = BranchDocument(
        branch_id=user.branch_id,
        title=title,
        doc_type=doc_type,
        file=filename,
        issued_at=datetime.fromisoformat(issued_at) if issued_at else None,
        expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
    )
    db.session.add(doc)
    db.session.commit()
    flash("✅ تم رفع مستند الفرع", "success")
    return redirect(url_for("employee_dashboard"))

# ✅ تعديل مستند فرع (للموظف ضمن فرعه)
@app.route("/employee/branch_documents/<int:doc_id>/edit", methods=["POST"])
def employee_edit_branch_document(doc_id):
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    user = User.query.get(session.get("user_id"))
    doc = BranchDocument.query.get_or_404(doc_id)
    if not user or doc.branch_id != user.branch_id:
        flash("⛔ غير مسموح تعديل مستندات فرع آخر", "danger")
        return redirect(url_for("employee_dashboard"))

    title = (request.form.get("title") or "").strip()
    doc_type = (request.form.get("doc_type") or "").strip()
    issued_at = request.form.get("issued_at")
    expires_at = request.form.get("expires_at")
    file = request.files.get("file")

    if title:
        doc.title = title
    doc.doc_type = doc_type
    doc.issued_at = datetime.fromisoformat(issued_at) if issued_at else None
    doc.expires_at = datetime.fromisoformat(expires_at) if expires_at else None

    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        doc.file = filename

    db.session.commit()
    flash("✅ تم تحديث المستند", "success")
    return redirect(url_for("employee_dashboard"))

# ✅ حذف مستند فرع (للموظف ضمن فرعه)
@app.route("/employee/branch_documents/<int:doc_id>/delete", methods=["POST"])
def employee_delete_branch_document(doc_id):
    if session.get("role") != "employee":
        return redirect(url_for("login"))

    user = User.query.get(session.get("user_id"))
    doc = BranchDocument.query.get_or_404(doc_id)
    if not user or doc.branch_id != user.branch_id:
        flash("⛔ غير مسموح حذف مستندات فرع آخر", "danger")
        return redirect(url_for("employee_dashboard"))

    try:
        if doc.file:
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], doc.file)
            if os.path.exists(fpath):
                os.remove(fpath)
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()
    flash("✅ تم حذف المستند", "success")
    return redirect(url_for("employee_dashboard"))

@app.route("/reports")
def reports():
    if not session.get("role") in ["employee", "manager", "engineer"]:
        return redirect(url_for("login"))

    reports = Transaction.query.filter_by(status="منجزة").order_by(Transaction.id.desc()).all()
    return render_template("reports.html", reports=reports)


# ---------------- البحث برقم التقرير ----------------
@app.route("/reports/search", methods=["GET", "POST"])
def search_report():
    if session.get("role") not in ["manager", "employee", "engineer"]:
        return redirect(url_for("login"))
    results = []
    search_number = None
    if request.method == "POST":
        search_number = (request.form.get("report_number") or "").strip()
        if search_number:
            results = Transaction.query.filter_by(report_number=search_number).all()
    return render_template("reports.html", reports=results, search_number=search_number)

# --------- تحقق عام من التقرير عبر رمز QR ---------
@app.route("/verify/<token>")
def verify_report(token):
    tx = Transaction.query.filter_by(verification_token=token).first()
    if not tx:
        return render_template("verify.html", ok=False, tx=None)
    return render_template("verify.html", ok=True, tx=tx)

# --------- إنشاء الجداول + ترقيعات متوافقة مع قواعد قديمة ---------
with app.app_context():
    db.create_all()

    # محاولة إضافة عمود sent_to_engineer_at إذا كان الجدول قديم
    try:
        if not column_exists("transaction", "sent_to_engineer_at"):
            db.session.execute(text("ALTER TABLE transaction ADD COLUMN sent_to_engineer_at TIMESTAMP"))
            db.session.commit()
            print("✅ تمت إضافة عمود sent_to_engineer_at")
    except Exception:
        db.session.rollback()

    # محاولة إنشاء جدول فواتير البنك إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM bank_invoice LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS bank_invoice (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_id INTEGER NOT NULL,
                    transaction_id INTEGER,
                    amount FLOAT DEFAULT 0,
                    issued_at TIMESTAMP,
                    delivered_at TIMESTAMP,
                    received_at TIMESTAMP,
                    note VARCHAR(255)
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول bank_invoice")
        except Exception:
            db.session.rollback()

    # محاولة إنشاء جدول عروض الأسعار إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM quote LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS quote (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_id INTEGER NOT NULL,
                    transaction_id INTEGER,
                    amount FLOAT DEFAULT 0,
                    valid_until TIMESTAMP,
                    note VARCHAR(255),
                    created_at TIMESTAMP,
                    created_by INTEGER
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول quote")
        except Exception:
            db.session.rollback()

    # محاولة إنشاء جدول customer_quote إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM customer_quote LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS customer_quote (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name VARCHAR(150) NOT NULL,
                    amount FLOAT DEFAULT 0,
                    valid_until TIMESTAMP,
                    transaction_id INTEGER,
                    note VARCHAR(255),
                    created_at TIMESTAMP,
                    created_by INTEGER
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول customer_quote")
        except Exception:
            db.session.rollback()

    # محاولة إنشاء جدول customer_invoice إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM customer_invoice LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS customer_invoice (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name VARCHAR(150) NOT NULL,
                    amount FLOAT DEFAULT 0,
                    issued_at TIMESTAMP,
                    transaction_id INTEGER,
                    note VARCHAR(255),
                    created_by INTEGER
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول customer_invoice")
        except Exception:
            db.session.rollback()

    # محاولة إضافة عمود bank_branch للمعاملات إذا كان الجدول قديم
    # محاولة إضافة عمود bank_sent_files إذا كان الجدول قديم
    try:
        if not column_exists("transaction", "bank_sent_files"):
            db.session.execute(text("ALTER TABLE transaction ADD COLUMN bank_sent_files TEXT"))
            db.session.commit()
            print("✅ تمت إضافة عمود bank_sent_files")
    except Exception:
        db.session.rollback()

    try:
        if not column_exists("transaction", "bank_branch"):
            db.session.execute(text("ALTER TABLE transaction ADD COLUMN bank_branch VARCHAR(120)"))
            db.session.commit()
            print("✅ تمت إضافة عمود bank_branch")
    except Exception:
        db.session.rollback()

    # محاولة إنشاء جدول report_template إن لم يكن موجودًا
    try:
        db.session.execute(text("SELECT 1 FROM report_template LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS report_template (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_type VARCHAR(50) NOT NULL,
                    content TEXT,
                    title VARCHAR(150),
                    file VARCHAR(255)
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول report_template")
        except Exception:
            db.session.rollback()

    # محاولة إنشاء جدول bank_document إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM bank_document LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS bank_document (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_id INTEGER NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    message TEXT,
                    doc_type VARCHAR(100),
                    file VARCHAR(255),
                    created_at TIMESTAMP,
                    created_by INTEGER,
                    branch_id INTEGER
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول bank_document")
        except Exception:
            db.session.rollback()

    # إنشاء مدير افتراضي إن أمكن (تجنب الأعمدة الناقصة)
    # محاولة إنشاء جدول branch_document إذا غير موجود
    try:
        db.session.execute(text("SELECT 1 FROM branch_document LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS branch_document (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch_id INTEGER NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    doc_type VARCHAR(100),
                    file VARCHAR(255),
                    issued_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP
                )
                """
            ))
            db.session.commit()
            print("✅ تم إنشاء جدول branch_document")
        except Exception:
            db.session.rollback()

    try:
        mgr = User.query.filter_by(role="manager").first()
    except OperationalError:
        mgr = None
    if not mgr:
        admin = User(username="admin", password=generate_password_hash("1234"), role="manager")
        db.session.add(admin)
        db.session.commit()
        print("✅ تم إنشاء حساب المدير الافتراضي (username=admin, password=1234)")

    # ✅ إنشاء حساب افتراضي لقسم المالية إن لم يكن موجودًا
    try:
        fin = User.query.filter_by(role="finance").first()
    except OperationalError:
        fin = None
    if not fin:
        # ربطه بأول فرع إن وجد
        first_branch = Branch.query.first()
        finance_user = User(
            username="finance",
            password=generate_password_hash("1234"),
            role="finance",
            branch_id=first_branch.id if first_branch else None
        )
        db.session.add(finance_user)
        db.session.commit()
        print("✅ تم إنشاء حساب المالية الافتراضي (username=finance, password=1234)")

    # محاولة إضافة عمود verification_token إذا كان الجدول قديم
    try:
        if not column_exists("transaction", "verification_token"):
            db.session.execute(text("ALTER TABLE transaction ADD COLUMN verification_token VARCHAR(64)"))
            db.session.commit()
            print("✅ تمت إضافة عمود verification_token")
    except Exception:
        db.session.rollback()

# ---------------- تقرير دخل موظف ----------------
@app.route("/employee_income", methods=["GET", "POST"])
def employee_income():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    employees = User.query.all()
    income = None
    report_data = []
    selected_emp = None
    start_date = None
    end_date = None

    if request.method == "POST":
        emp_id = request.form.get("employee_id")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

        employee = User.query.get(emp_id)
        selected_emp = employee.username if employee else None

        query = Transaction.query.filter_by(employee=selected_emp)
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        transactions = query.all()
        income = 0.0

        for t in transactions:
            payments = Payment.query.filter_by(transaction_id=t.id).all()
            paid_amount = sum(p.amount for p in payments)
            status_payment = "مدفوعة" if paid_amount > 0 else "غير مدفوعة"
            report_data.append({
                "id": t.id,
                "client": t.client,
                "date": t.date,
                "status": t.status,
                "fee": paid_amount,
                "payment_status": status_payment
            })
            income += paid_amount

    return render_template(
        "employee_income.html",
        employees=employees,
        selected_emp=selected_emp,
        transactions=report_data,
        income=income,
        start_date=start_date,
        end_date=end_date
    )



app.config["BFNeZpjEro8pwFxR1H20twlTd2pL5MZtWrDATu4ME2RcbzhN-PBHcpk_jYrRlDUrn4SUxHJ5TOEF796OXs-NN"] = "🔑_ضع_المفتاح_العام"
app.config["Gv_NJwUe_M5R6seQItCoivxv3mTp6JiJQmkcrQmICuk="] = "🔐_ضع_المفتاح_الخاص"
app.config["VAPID_CLAIMS"] = {
    "sub": "mailto:your-email@example.com"
}




if __name__ == "__main__":
    app.run(debug=True)
