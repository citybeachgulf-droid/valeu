from __future__ import annotations

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import secrets
import json
import smtplib
from email.message import EmailMessage

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    current_app,
)
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash

from extensions import db
from consulting.projects.models import ConsultingProject
from .models import Engineer, Task, Department
from .forms import (
    ENGINEER_SPECIALTIES,
    ENGINEER_STATUSES,
    TASK_STATUSES,
    validate_engineer_form,
    validate_new_task_form,
    validate_update_task_form,
)


hr_bp = Blueprint(
    "consulting_hr",
    __name__,
    url_prefix="/consulting/hr",
    template_folder="templates",
)


# ---------- Helpers ----------

def _require_roles(allowed: List[str]) -> Optional[None]:
    role = session.get("role")
    if role not in allowed:
        return redirect(url_for("login"))
    return None


def _create_limited_user(username_hint: str | None, role: str):
    """ينشئ مستخدمًا محدود الصلاحيات بالدور المحدد.

    تعاد (user, raw_password) بحيث يمكن للنداء اللاحق ربط الحساب
    بالموظف أو المهندس وإرسال بيانات الدخول المؤقتة.
    """
    # تجنّب الاستيراد الدائري: نستورد User داخل الدالة
    from app import User

    base_username = (username_hint or "").strip().lower()
    if base_username:
        # نظّف المسافة وأنواع الحروف الشائعة في الهواتف/الايميل
        base_username = base_username.replace(" ", "").replace("+", "").replace("(", "").replace(")", "").replace("-", "")
    # اختر بادئة حسب الدور
    prefix = "emp" if role == "employee" else ("eng" if role == "engineer" else "user")

    # ابنِ اسم مستخدم فريد
    candidate = base_username or f"{prefix}"
    suffix = 0
    while True:
        username = candidate if suffix == 0 else f"{candidate}{suffix}"
        if not User.query.filter_by(username=username).first():
            break
        suffix += 1

    # كلمة مرور افتراضية قوية يسهل تسليمها: 8 خانات مع حروف وأرقام
    raw_password = f"{prefix}123456" if suffix == 0 else f"{prefix}{suffix:02d}123"
    password_hash = generate_password_hash(raw_password)

    user = User(username=username, password=password_hash, role=role)
    db.session.add(user)
    db.session.flush()  # للحصول على id إن لزم قبل commit

    return user, raw_password


def _send_invitation_email(recipient: str, subject: str, body: str) -> bool:
    """يحاول إرسال بريد إلكتروني بسيط ويعيد نجاح العملية."""
    if not recipient:
        return False
    try:
        smtp_host = current_app.config.get("SMTP_HOST")
        if not smtp_host:
            return False
        smtp_port = current_app.config.get("SMTP_PORT", 587)
        smtp_user = current_app.config.get("SMTP_USERNAME")
        smtp_password = current_app.config.get("SMTP_PASSWORD")
        use_tls = current_app.config.get("SMTP_USE_TLS", True)
        sender = current_app.config.get("SMTP_SENDER") or smtp_user
        if not sender:
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return True
    except Exception as exc:
        current_app.logger.warning("Failed to send invitation email: %s", exc, exc_info=True)
        return False


def _create_employee_invitation(employee, user, raw_password):
    """ينشئ سجل دعوة لموظف ويعيد (invitation, url, email_sent)."""
    from app import UserInvitation

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    invitation = UserInvitation(
        user_id=user.id,
        employee_id=employee.id,
        token=token,
        raw_password=raw_password,
        expires_at=expires_at,
        delivery_method="manual",
    )

    invitation_url = url_for("complete_invitation", token=token, _external=True)
    email_sent = False
    if employee.email:
        subject = "دعوة إنشاء حسابك في نظام الشركة"
        body = (
            f"مرحبًا {employee.full_name},\n\n"
            f"تمت إضافتك إلى نظام الموارد البشرية. لإنشاء حسابك واختيار اسم مستخدم وكلمة مرور، "
            f"الرجاء الضغط على الرابط التالي:\n\n{invitation_url}\n\n"
            f"اسم المستخدم المقترح: {user.username}\n"
            f"كلمة المرور المؤقتة: {raw_password}\n\n"
            f"سينتهي هذا الرابط في {expires_at.strftime('%Y-%m-%d')}.\n"
            f"مع التحية."
        )
        email_sent = _send_invitation_email(employee.email, subject, body)
        if email_sent:
            invitation.delivery_method = "email"
            invitation.sent_at = datetime.utcnow()

    db.session.add(invitation)
    return invitation, invitation_url, email_sent


def _get_branch_choices() -> tuple[List[dict], dict]:
    """إرجاع قائمة الفروع مع الأقسام، وخريطة للأقسام حسب الفرع."""
    try:
        from app import Branch, BranchSection  # type: ignore import-error
    except Exception:
        return [], {}

    branches = Branch.query.order_by(Branch.name).all()
    sections_by_branch: Dict[int, List] = {}
    for section in BranchSection.query.order_by(BranchSection.name).all():
        sections_by_branch.setdefault(section.branch_id, []).append(section)

    branch_list: List[dict] = []
    sections_map: dict = {}
    for branch in branches:
        sections = sections_by_branch.get(branch.id, [])
        serialized_sections = [
            {"id": sec.id, "name": sec.name} for sec in sections
        ]
        branch_list.append(
            {
                "id": branch.id,
                "name": branch.name,
                "sections": serialized_sections,
            }
        )
        sections_map[str(branch.id)] = serialized_sections
    return branch_list, sections_map


# Ensure there are some baseline departments so forms can render choices
def _ensure_default_departments() -> None:
    """Create a few default departments if none exist.

    This prevents empty department dropdowns on employee/engineer creation forms
    in fresh databases where HR departments haven't been set up yet.
    """
    existing_count = Department.query.count()
    if existing_count and existing_count > 0:
        return

    defaults: List[dict] = [
        {"name": "التثمين", "code": "valuation", "description": "قسم التثمين"},
        {"name": "الاستشارات", "code": "consultations", "description": "قسم الاستشارات"},
        {"name": "إدارة الممتلكات", "code": "property", "description": "قسم إدارة الممتلكات"},
        {"name": "الموارد البشرية", "code": "hr", "description": "قسم الموارد البشرية"},
        {"name": "المالية", "code": "finance", "description": "قسم المالية"},
    ]

    # Avoid unique constraint conflicts if codes/names already partially exist
    existing_names = {d.name for d in Department.query.all()}
    existing_codes = {d.code for d in Department.query.all() if d.code}

    created = False
    for d in defaults:
        if d["name"] in existing_names or d["code"] in existing_codes:
            continue
        db.session.add(Department(**d))
        created = True

    if created:
        db.session.commit()

# ---------- Pages ----------

# تم نقل وظيفة dashboard القديمة إلى hr_dashboard الموحدة أدناه


@hr_bp.route("/engineers")
def list_engineers():
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "hr"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    specialty = (request.args.get("specialty") or "").strip()
    status = (request.args.get("status") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Engineer.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Engineer.name.ilike(like), Engineer.phone.ilike(like), Engineer.email.ilike(like)))
    if specialty:
        query = query.filter(Engineer.specialty == specialty)
    if status:
        query = query.filter(Engineer.status == status)

    query = query.order_by(Engineer.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Build quick stats for overdue tasks per engineer (lightweight for small pages)
    overdue_counts: Dict[int, int] = {}
    open_counts: Dict[int, int] = {}
    for eng in pagination.items:
        overdue_counts[eng.id] = sum(1 for t in eng.tasks if t.is_overdue())
        open_counts[eng.id] = sum(1 for t in eng.tasks if t.status != "مكتملة")

    can_manage = session.get("role") in {"manager", "employee", "hr"}

    return render_template(
        "hr/engineers.html",
        engineers=pagination.items,
        pagination=pagination,
        q=q,
        current_specialty=specialty,
        current_status=status,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        overdue_counts=overdue_counts,
        open_counts=open_counts,
        can_manage=can_manage,
        title="مهندسو الاستشارات",
    )


@hr_bp.route("/engineers/new", methods=["GET", "POST"])
def create_engineer():
    maybe_redirect = _require_roles(["manager", "employee", "hr"])
    if maybe_redirect:
        return maybe_redirect

    form_values: Dict[str, str] = {
        "name": "",
        "specialty": ENGINEER_SPECIALTIES[0] if ENGINEER_SPECIALTIES else "",
        "phone": "",
        "email": "",
        "join_date": "",
        "status": "نشط",
        "department_id": "",
    }
    form_errors: Dict[str, str] = {}

    if request.method == "POST":
        for key in form_values:
            form_values[key] = (request.form.get(key) or "").strip()

        data, form_errors = validate_engineer_form(request.form)
        if form_errors:
            for _, msg in form_errors.items():
                flash(f"❌ {msg}", "error")
        else:
            engineer = Engineer(
                name=data["name"],
                specialty=data["specialty"],
                phone=data["phone"],
                email=data["email"],
                join_date=data["join_date"],
                status=data["status"] or "نشط",
                department_id=data.get("department_id"),
            )
            db.session.add(engineer)
            db.session.flush()

            # إنشاء حساب مستخدم محدود الدور للمهندس
            user, raw_password = _create_limited_user(engineer.email or engineer.phone, role="engineer")

            db.session.commit()

            flash(f"✅ تم إضافة المهندس بنجاح. تم إنشاء مستخدم: {user.username} بكلمة مرور مؤقتة.", "success")
            return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer.id))

    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template(
        "hr/engineer_form.html",
        mode="create",
        engineer=None,
        form_values=form_values,
        form_errors=form_errors,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        departments=departments,
        title="إضافة مهندس جديد",
    )


@hr_bp.route("/engineers/<int:engineer_id>/edit", methods=["GET", "POST"])
def edit_engineer(engineer_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "hr"])
    if maybe_redirect:
        return maybe_redirect

    engineer = Engineer.query.get_or_404(engineer_id)

    form_values: Dict[str, str] = {
        "name": engineer.name or "",
        "specialty": engineer.specialty or (ENGINEER_SPECIALTIES[0] if ENGINEER_SPECIALTIES else ""),
        "phone": engineer.phone or "",
        "email": engineer.email or "",
        "join_date": engineer.join_date.strftime("%Y-%m-%d") if engineer.join_date else "",
        "status": engineer.status or "نشط",
        "department_id": str(engineer.department_id) if engineer.department_id else "",
    }
    form_errors: Dict[str, str] = {}

    if request.method == "POST":
        for key in form_values:
            form_values[key] = (request.form.get(key) or "").strip()

        data, form_errors = validate_engineer_form(request.form, for_update=True)
        if form_errors:
            for _, msg in form_errors.items():
                flash(f"❌ {msg}", "error")
        else:
            engineer.name = data["name"]
            engineer.specialty = data["specialty"]
            engineer.phone = data["phone"]
            engineer.email = data["email"]
            engineer.join_date = data["join_date"]
            if data["status"]:
                engineer.status = data["status"]
            engineer.department_id = data.get("department_id")

            db.session.commit()

            flash("✅ تم تحديث بيانات المهندس", "success")
            return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer.id))

    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template(
        "hr/engineer_form.html",
        mode="edit",
        engineer=engineer,
        form_values=form_values,
        form_errors=form_errors,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        departments=departments,
        title=f"تعديل بيانات المهندس - {engineer.name}",
    )


@hr_bp.route("/engineers/<int:engineer_id>")
def engineer_detail(engineer_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "hr"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    engineer = Engineer.query.get_or_404(engineer_id)
    tasks = Task.query.filter_by(engineer_id=engineer.id).order_by(Task.created_at.desc()).all()

    # For task creation modal
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()

    overdue_count = sum(1 for t in tasks if t.is_overdue())
    can_manage = session.get("role") in {"manager", "employee", "hr"}

    return render_template(
        "hr/engineer_detail.html",
        engineer=engineer,
        tasks=tasks,
        projects=projects,
        TASK_STATUSES=TASK_STATUSES,
        overdue_count=overdue_count,
        can_manage=can_manage,
        title=f"المهندس - {engineer.name}",
    )


# ---------- Actions ----------

@hr_bp.route("/engineers/<int:engineer_id>/tasks", methods=["POST"])
def add_task(engineer_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "hr"])  # restrict adding tasks to staff
    if maybe_redirect:
        return maybe_redirect

    # Force engineer_id from path
    form_data = dict(request.form)
    form_data["engineer_id"] = str(engineer_id)
    data, errors = validate_new_task_form(form_data)

    # Basic existence checks
    if not errors:
        if not ConsultingProject.query.get(data["project_id"]):
            errors["project_id"] = "المشروع المحدد غير موجود"
        if not Engineer.query.get(data["engineer_id"]):
            errors["engineer_id"] = "المهندس المحدد غير موجود"

    if errors:
        for _, msg in errors.items():
            flash(f"❌ {msg}", "error")
        return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer_id))

    task = Task(
        project_id=data["project_id"],
        engineer_id=data["engineer_id"],
        title=data["title"],
        description=data["description"],
        deadline=data["deadline"],
        status="جديدة",
        progress=0,
    )
    db.session.add(task)
    db.session.commit()

    flash("✅ تم إضافة المهمة بنجاح", "success")
    return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer_id))


@hr_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
def update_task(task_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "hr"])  # engineers can update their tasks
    if maybe_redirect:
        return maybe_redirect

    task = Task.query.get_or_404(task_id)

    data, errors = validate_update_task_form(request.form)
    if errors:
        # If it is an AJAX request, return JSON error
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (request.headers.get("Accept") or ""):
            return jsonify({"ok": False, "errors": errors}), 400
        for _, msg in errors.items():
            flash(f"❌ {msg}", "error")
        return redirect(url_for("consulting_hr.engineer_detail", engineer_id=task.engineer_id))

    task.status = data["status"]
    task.progress = data["progress"]
    db.session.commit()

    # AJAX friendly response
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (request.headers.get("Accept") or ""):
        return jsonify({
            "ok": True,
            "task": {
                "id": task.id,
                "status": task.status,
                "progress": task.progress,
                "overdue": task.is_overdue(),
            },
            "message": "تم تحديث المهمة بنجاح",
        })

    flash("✅ تم تحديث المهمة", "success")
    return redirect(url_for("consulting_hr.engineer_detail", engineer_id=task.engineer_id))


# ==================== Routes للنظام الشامل ====================
# ملاحظة: تم إنشاء النماذج والتحققات. المطلوب الآن هو إنشاء Routes وTemplates
# تم توثيق جميع المسارات المطلوبة في ملف HR_SYSTEM_DOCUMENTATION.md

from .models import (
    Department, Employee, Attendance, SalaryComponent, Payroll, PayrollDetail,
    LeaveType, LeaveBalance, LeaveRequest, PerformanceReview, EmployeeGoal,
    TrainingProgram, TrainingParticipant, JobPosting, Candidate, JobApplication,
    Interview, EmployeeDocument, DocumentAlert
)
from .forms import (
    validate_employee_form, validate_attendance_form, validate_payroll_form,
    validate_leave_request_form, validate_performance_review_form,
    validate_employee_goal_form, validate_job_posting_form,
    validate_candidate_form, validate_interview_form,
    EMPLOYEE_STATUSES, EMPLOYMENT_TYPES, LEAVE_REQUEST_STATUSES,
    ATTENDANCE_STATUSES, PAYROLL_STATUSES, PERFORMANCE_REVIEW_STATUSES,
    PERFORMANCE_PERIODS, JOB_POSTING_STATUSES, CANDIDATE_STATUSES,
    INTERVIEW_STATUSES, INTERVIEW_RESULTS, GOAL_PRIORITIES, GOAL_STATUSES
)
from datetime import date, datetime, timedelta
from decimal import Decimal


@hr_bp.route("/staff")
def list_staff():
    """قائمة موحدة للموظفين والمهندسين - كل فرع يظهر موظفيه لوحده"""
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect
    
    q = (request.args.get("q") or "").strip()
    department_id = request.args.get("department_id", type=int)
    employee_status = (request.args.get("employee_status") or "").strip()
    engineer_status = (request.args.get("engineer_status") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 30) or 30), 1), 100)
    
    # جلب الموظفين
    employee_query = Employee.query.options(joinedload(Employee.user_account))
    if q:
        like = f"%{q}%"
        employee_query = employee_query.filter(or_(
            Employee.first_name.ilike(like),
            Employee.last_name.ilike(like),
            Employee.employee_number.ilike(like),
            Employee.email.ilike(like),
            Employee.phone.ilike(like)
        ))
    if department_id:
        employee_query = employee_query.filter(Employee.department_id == department_id)
    if employee_status:
        employee_query = employee_query.filter(Employee.status == employee_status)
    employees = employee_query.order_by(Employee.id.desc()).all()
    
    # جلب المهندسين
    engineer_query = Engineer.query
    if q:
        like = f"%{q}%"
        engineer_query = engineer_query.filter(or_(
            Engineer.name.ilike(like),
            Engineer.phone.ilike(like),
            Engineer.email.ilike(like)
        ))
    if department_id:
        engineer_query = engineer_query.filter(Engineer.department_id == department_id)
    if engineer_status:
        engineer_query = engineer_query.filter(Engineer.status == engineer_status)
    engineers = engineer_query.order_by(Engineer.id.desc()).all()
    
    # تجميع حسب الفرع
    from collections import defaultdict
    staff_by_department = defaultdict(lambda: {"employees": [], "engineers": []})
    
    for emp in employees:
        dept_key = emp.department.name if emp.department else "بدون فرع"
        staff_by_department[dept_key]["employees"].append(emp)
    
    for eng in engineers:
        dept_key = eng.department.name if eng.department else "بدون فرع"
        staff_by_department[dept_key]["engineers"].append(eng)
    
    # بناء إحصائيات المهام للمهندسين
    overdue_counts: Dict[int, int] = {}
    open_counts: Dict[int, int] = {}
    for eng in engineers:
        overdue_counts[eng.id] = sum(1 for t in eng.tasks if t.is_overdue())
        open_counts[eng.id] = sum(1 for t in eng.tasks if t.status != "مكتملة")
    
    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    can_manage = session.get("role") in {"manager", "hr", "hr_manager"}
    
    return render_template(
        "hr/staff.html",
        staff_by_department=dict(staff_by_department),
        q=q,
        current_department_id=department_id,
        current_employee_status=employee_status,
        current_engineer_status=engineer_status,
        departments=departments,
        EMPLOYEE_STATUSES=EMPLOYEE_STATUSES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        overdue_counts=overdue_counts,
        open_counts=open_counts,
        can_manage=can_manage,
        title="الموظفين والمهندسين",
    )


@hr_bp.route("/employees")
def list_employees():
    """قائمة الموظفين"""
    maybe_redirect = _require_roles(["manager", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect
    
    q = (request.args.get("q") or "").strip()
    department_id = request.args.get("department_id", type=int)
    status = (request.args.get("status") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)
    
    query = Employee.query.options(joinedload(Employee.user_account))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Employee.first_name.ilike(like),
            Employee.last_name.ilike(like),
            Employee.employee_number.ilike(like),
            Employee.email.ilike(like),
            Employee.phone.ilike(like)
        ))
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if status:
        query = query.filter(Employee.status == status)
    
    query = query.order_by(Employee.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    can_manage = session.get("role") in {"manager", "hr", "hr_manager"}
    
    return render_template(
        "hr/employees.html",
        employees=pagination.items,
        pagination=pagination,
        q=q,
        current_department_id=department_id,
        current_status=status,
        departments=departments,
        EMPLOYEE_STATUSES=EMPLOYEE_STATUSES,
        can_manage=can_manage,
        title="قائمة الموظفين",
    )


@hr_bp.route("/employees/new", methods=["GET", "POST"])
def create_employee():
    """إضافة موظف جديد"""
    maybe_redirect = _require_roles(["manager", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect

    branch_choices, branch_sections_map = _get_branch_choices()
    
    form_values = {}
    form_errors = {}
    
    if request.method == "POST":
        data, form_errors = validate_employee_form(request.form)
        if form_errors:
            for _, msg in form_errors.items():
                flash(f"❌ {msg}", "error")
            form_values = dict(request.form)
            form_values.setdefault("branch_id", form_values.get("branch_id", ""))
            form_values.setdefault("branch_section_id", form_values.get("branch_section_id", ""))
        else:
            employee = Employee(**data)
            db.session.add(employee)
            db.session.flush()

            # إنشاء حساب مستخدم محدود الدور للموظف
            user, raw_password = _create_limited_user(employee.email or employee.phone, role="employee")
            user.employee_id = employee.id
            user.branch_id = employee.branch_id
            user.section_id = employee.branch_section_id

            invitation, invitation_url, email_sent = _create_employee_invitation(employee, user, raw_password)
            db.session.commit()

            flash(f"✅ تم إضافة الموظف بنجاح. تم إنشاء مستخدم: {user.username}.", "success")
            if email_sent:
                flash("✉️ تم إرسال رابط إنشاء الحساب للموظف عبر البريد الإلكتروني.", "info")
            else:
                flash(
                    f"🔗 رابط إنشاء الحساب: {invitation_url} — كلمة المرور المؤقتة: {raw_password}",
                    "warning",
                )
            return redirect(url_for("consulting_hr.employee_detail", employee_id=employee.id))
    else:
        # تعيين القيم الافتراضية
        form_values = {
            "status": "نشط",
            "currency": "OMR",
            "employment_type": EMPLOYMENT_TYPES[0] if EMPLOYMENT_TYPES else None,
            "branch_id": "",
            "branch_section_id": "",
        }
    
    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template(
        "hr/employee_form.html",
        mode="create",
        employee=None,
        form_values=form_values,
        form_errors=form_errors,
        departments=departments,
        EMPLOYEE_STATUSES=EMPLOYEE_STATUSES,
        EMPLOYMENT_TYPES=EMPLOYMENT_TYPES,
        branch_choices=branch_choices,
        branch_sections_json=json.dumps(branch_sections_map, ensure_ascii=False),
        title="إضافة موظف جديد",
    )


@hr_bp.route("/employees/<int:employee_id>")
def employee_detail(employee_id: int):
    """تفاصيل الموظف"""
    maybe_redirect = _require_roles(["manager", "employee", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect
    
    employee = Employee.query.get_or_404(employee_id)
    
    # التحقق من الصلاحيات - الموظف يمكنه رؤية بياناته فقط
    user_role = session.get("role")
    if user_role == "employee":
        # يجب التحقق من أن الموظف المسجل هو نفسه (يتطلب نظام مصادقة)
        pass
    
    # جلب البيانات المرتبطة
    recent_attendance = Attendance.query.filter_by(employee_id=employee.id)\
        .order_by(Attendance.attendance_date.desc()).limit(10).all()
    
    recent_leaves = LeaveRequest.query.filter_by(employee_id=employee.id)\
        .order_by(LeaveRequest.start_date.desc()).limit(5).all()
    
    recent_reviews = PerformanceReview.query.filter_by(employee_id=employee.id)\
        .order_by(PerformanceReview.review_year.desc(), PerformanceReview.review_period.desc()).limit(3).all()
    
    documents = EmployeeDocument.query.filter_by(employee_id=employee.id)\
        .order_by(EmployeeDocument.uploaded_at.desc()).all()
    
    # التحقق من المستندات المنتهية الصلاحية
    expiring_docs = [doc for doc in documents if doc.is_expired()]
    
    can_manage = user_role in {"manager", "hr", "hr_manager"}
    
    return render_template(
        "hr/employee_detail.html",
        employee=employee,
        recent_attendance=recent_attendance,
        recent_leaves=recent_leaves,
        recent_reviews=recent_reviews,
        documents=documents,
        expiring_docs=expiring_docs,
        can_manage=can_manage,
        title=f"تفاصيل الموظف - {employee.full_name}",
    )


@hr_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
def edit_employee(employee_id: int):
    """تعديل بيانات الموظف"""
    maybe_redirect = _require_roles(["manager", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect
    
    employee = Employee.query.get_or_404(employee_id)
    branch_choices, branch_sections_map = _get_branch_choices()
    form_values = {}
    form_errors = {}
    
    if request.method == "POST":
        data, form_errors = validate_employee_form(request.form, for_update=True)
        if form_errors:
            for _, msg in form_errors.items():
                flash(f"❌ {msg}", "error")
            form_values = dict(request.form)
            form_values.setdefault("branch_id", form_values.get("branch_id", ""))
            form_values.setdefault("branch_section_id", form_values.get("branch_section_id", ""))
        else:
            # تحديث البيانات
            for key, value in data.items():
                if value is not None or key in ["notes", "description"]:
                    setattr(employee, key, value)
            
            if employee.user_account:
                employee.user_account.branch_id = employee.branch_id
                employee.user_account.section_id = employee.branch_section_id

            db.session.commit()
            flash("✅ تم تحديث بيانات الموظف", "success")
            return redirect(url_for("consulting_hr.employee_detail", employee_id=employee.id))
    else:
        # تعبئة النموذج بالبيانات الحالية
        form_values = {
            "employee_number": employee.employee_number or "",
            "first_name": employee.first_name or "",
            "middle_name": employee.middle_name or "",
            "last_name": employee.last_name or "",
            "arabic_name": employee.arabic_name or "",
            "date_of_birth": employee.date_of_birth.strftime("%Y-%m-%d") if employee.date_of_birth else "",
            "gender": employee.gender or "",
            "nationality": employee.nationality or "",
            "national_id": employee.national_id or "",
            "passport_number": employee.passport_number or "",
            "email": employee.email or "",
            "phone": employee.phone or "",
            "mobile": employee.mobile or "",
            "address": employee.address or "",
            "city": employee.city or "",
            "country": employee.country or "",
            "emergency_contact_name": employee.emergency_contact_name or "",
            "emergency_contact_phone": employee.emergency_contact_phone or "",
            "emergency_contact_relation": employee.emergency_contact_relation or "",
            "department_id": str(employee.department_id) if employee.department_id else "",
            "position": employee.position or "",
            "job_title": employee.job_title or "",
            "employment_type": employee.employment_type or "",
            "join_date": employee.join_date.strftime("%Y-%m-%d") if employee.join_date else "",
            "contract_start_date": employee.contract_start_date.strftime("%Y-%m-%d") if employee.contract_start_date else "",
            "contract_end_date": employee.contract_end_date.strftime("%Y-%m-%d") if employee.contract_end_date else "",
            "status": employee.status or "نشط",
            "resignation_date": employee.resignation_date.strftime("%Y-%m-%d") if employee.resignation_date else "",
            "termination_date": employee.termination_date.strftime("%Y-%m-%d") if employee.termination_date else "",
            "base_salary": str(employee.base_salary) if employee.base_salary else "",
            "currency": employee.currency or "OMR",
            "notes": employee.notes or "",
            "branch_id": str(employee.branch_id) if employee.branch_id else "",
            "branch_section_id": str(employee.branch_section_id) if employee.branch_section_id else "",
        }
    
    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template(
        "hr/employee_form.html",
        mode="edit",
        employee=employee,
        form_values=form_values,
        form_errors=form_errors,
        departments=departments,
        EMPLOYEE_STATUSES=EMPLOYEE_STATUSES,
        EMPLOYMENT_TYPES=EMPLOYMENT_TYPES,
        branch_choices=branch_choices,
        branch_sections_json=json.dumps(branch_sections_map, ensure_ascii=False),
        title=f"تعديل بيانات الموظف - {employee.full_name}",
    )


@hr_bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """لوحة تحكم HR الشاملة لجميع الأقسام"""
    maybe_redirect = _require_roles(["manager", "employee", "hr", "hr_manager"])
    if maybe_redirect:
        return maybe_redirect
    
    today = date.today()
    
    # ===== إحصائيات عامة للموظفين =====
    total_employees = Employee.query.count()
    active_employees = Employee.query.filter(Employee.status == "نشط").count()
    on_leave_employees = Employee.query.filter(Employee.status == "إجازة").count()
    
    # ===== إحصائيات الحضور (هذا الشهر) =====
    current_month_attendance = Attendance.query.filter(
        func.extract('year', Attendance.attendance_date) == today.year,
        func.extract('month', Attendance.attendance_date) == today.month
    ).all()
    present_count = sum(1 for a in current_month_attendance if a.status == "حاضر")
    absent_count = sum(1 for a in current_month_attendance if a.status == "غائب")
    
    # ===== إحصائيات الإجازات =====
    pending_leaves = LeaveRequest.query.filter(LeaveRequest.status == "معلق").count()
    approved_leaves_today = LeaveRequest.query.filter(
        LeaveRequest.status == "معتمد",
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today
    ).count()
    
    # ===== إحصائيات الرواتب =====
    current_month_payroll = Payroll.query.filter(
        Payroll.payroll_year == today.year,
        Payroll.payroll_month == today.month
    ).count()
    total_payroll_amount = db.session.query(func.sum(Payroll.net_salary)).filter(
        Payroll.payroll_year == today.year,
        Payroll.payroll_month == today.month
    ).scalar() or Decimal(0)
    
    # ===== المستندات المنتهية الصلاحية =====
    expiring_documents = EmployeeDocument.query.filter(
        EmployeeDocument.expiry_date.isnot(None),
        EmployeeDocument.expiry_date <= today + timedelta(days=30),
        EmployeeDocument.expiry_date >= today
    ).count()
    
    # ===== طلبات التوظيف المعلقة =====
    pending_applications = JobApplication.query.filter(
        JobApplication.status == "قيد المراجعة"
    ).count()
    
    # ===== إحصائيات المهندسين (للتوافق مع النظام القديم) =====
    total_engineers = Engineer.query.count()
    active_engineers = Engineer.query.filter(Engineer.status == "نشط").count()
    open_tasks_query = Task.query.filter(Task.status != "مكتملة")
    total_open_tasks = open_tasks_query.count()
    overdue_tasks_count = open_tasks_query.filter(
        Task.deadline.isnot(None),
        Task.deadline < today,
    ).count()
    
    # ===== إحصائيات لكل قسم =====
    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    department_stats = []
    
    for dept in departments:
        dept_employees = Employee.query.filter(Employee.department_id == dept.id).all()
        dept_total = len(dept_employees)
        dept_active = sum(1 for e in dept_employees if e.status == "نشط")
        dept_on_leave = sum(1 for e in dept_employees if e.status == "إجازة")
        
        # الحضور لهذا الشهر
        dept_employee_ids = [e.id for e in dept_employees]
        dept_attendance = [
            a for a in current_month_attendance 
            if a.employee_id in dept_employee_ids
        ]
        dept_present = sum(1 for a in dept_attendance if a.status == "حاضر")
        dept_absent = sum(1 for a in dept_attendance if a.status == "غائب")
        
        # الإجازات المعلقة
        dept_pending_leaves = LeaveRequest.query.filter(
            LeaveRequest.employee_id.in_(dept_employee_ids),
            LeaveRequest.status == "معلق"
        ).count()
        
        department_stats.append({
            "department": dept,
            "total_employees": dept_total,
            "active_employees": dept_active,
            "on_leave_employees": dept_on_leave,
            "present_count": dept_present,
            "absent_count": dept_absent,
            "pending_leaves": dept_pending_leaves,
        })
    
    # ===== توزيع الموظفين حسب الأقسام =====
    department_distribution = {}
    for dept in departments:
        count = Employee.query.filter(Employee.department_id == dept.id).count()
        if count > 0:
            department_distribution[dept.name] = count
    
    # ===== أحدث الموظفين من جميع الأقسام =====
    recent_employees = Employee.query.order_by(Employee.created_at.desc()).limit(5).all()
    
    # ===== الإجازات القادمة =====
    upcoming_leaves = LeaveRequest.query.filter(
        LeaveRequest.status == "معتمد",
        LeaveRequest.start_date > today
    ).order_by(LeaveRequest.start_date.asc()).limit(5).all()
    
    # ===== المستندات المنتهية قريباً =====
    docs_expiring_soon = EmployeeDocument.query.filter(
        EmployeeDocument.expiry_date.isnot(None),
        EmployeeDocument.expiry_date <= today + timedelta(days=30),
        EmployeeDocument.expiry_date >= today
    ).order_by(EmployeeDocument.expiry_date.asc()).limit(5).all()
    
    # ===== المهام القادمة والمتأخرة (للمهندسين) =====
    upcoming_tasks = (
        open_tasks_query.filter(
            Task.deadline.isnot(None),
            Task.deadline >= today,
        )
        .order_by(Task.deadline.asc())
        .limit(5)
        .all()
    )
    
    overdue_tasks = (
        open_tasks_query.filter(
            Task.deadline.isnot(None),
            Task.deadline < today,
        )
        .order_by(Task.deadline.asc())
        .limit(5)
        .all()
    )
    
    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
    recent_engineers = Engineer.query.order_by(Engineer.created_at.desc()).limit(5).all()
    
    # توزيع المهندسين حسب التخصص
    specialty_rows = (
        db.session.query(Engineer.specialty, func.count(Engineer.id))
        .group_by(Engineer.specialty)
        .all()
    )
    specialty_distribution = {row[0]: row[1] for row in specialty_rows}
    
    stats = {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "on_leave_employees": on_leave_employees,
        "present_count": present_count,
        "absent_count": absent_count,
        "pending_leaves": pending_leaves,
        "approved_leaves_today": approved_leaves_today,
        "current_month_payroll": current_month_payroll,
        "total_payroll_amount": total_payroll_amount,
        "expiring_documents": expiring_documents,
        "pending_applications": pending_applications,
        "total_engineers": total_engineers,
        "active_engineers": active_engineers,
        "total_open_tasks": total_open_tasks,
        "overdue_tasks_count": overdue_tasks_count,
    }
    
    return render_template(
        "hr/dashboard.html",
        stats=stats,
        department_stats=department_stats,
        department_distribution=department_distribution,
        departments=departments,
        recent_employees=recent_employees,
        upcoming_leaves=upcoming_leaves,
        docs_expiring_soon=docs_expiring_soon,
        upcoming_tasks=upcoming_tasks,
        overdue_tasks=overdue_tasks,
        recent_tasks=recent_tasks,
        recent_engineers=recent_engineers,
        specialty_distribution=specialty_distribution,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        title="لوحة تحكم الموارد البشرية الشاملة",
    )


# ========== Unified Staff Creation (Employee or Engineer) ==========

@hr_bp.route("/staff/new", methods=["GET", "POST"])
def create_staff():
    """نموذج موحد لإضافة موظف أو مهندس مع إلزام اختيار القسم."""
    maybe_redirect = _require_roles(["manager", "hr", "hr_manager", "employee"])
    if maybe_redirect:
        return maybe_redirect
    branch_choices, branch_sections_map = _get_branch_choices()

    form_errors: Dict[str, str] = {}
    form_values: Dict[str, str] = {
        "role_type": (request.args.get("role_type") or "employee").strip(),
        # Employee fields
        "first_name": "",
        "last_name": "",
        "email": "",
        "phone": "",
        "mobile": "",
        "employment_type": "",
        "position": "",
        "job_title": "",
        "join_date": "",
        "status": "نشط",
        "branch_id": "",
        "branch_section_id": "",
        # Engineer fields
        "name": "",
        "specialty": ENGINEER_SPECIALTIES[0] if ENGINEER_SPECIALTIES else "",
        # Shared
        "department_id": "",
    }

    if request.method == "POST":
        # Preserve incoming values for re-render
        for key in form_values.keys():
            form_values[key] = (request.form.get(key) or "").strip()

        role_type = (request.form.get("role_type") or "employee").strip()
        dept_raw = (request.form.get("department_id") or "").strip()
        if not dept_raw:
            form_errors["department_id"] = "يجب اختيار القسم"

        if role_type == "engineer":
            data, eng_errors = validate_engineer_form(request.form)
            form_errors.update(eng_errors)
            # Ensure department required
            if not data.get("department_id"):
                form_errors["department_id"] = "يجب اختيار القسم"

            if form_errors:
                for _, msg in form_errors.items():
                    flash(f"❌ {msg}", "error")
            else:
                engineer = Engineer(
                    name=data["name"],
                    specialty=data["specialty"],
                    phone=data.get("phone"),
                    email=data.get("email"),
                    join_date=data.get("join_date"),
                    status=data.get("status") or "نشط",
                    department_id=data.get("department_id"),
                )
                db.session.add(engineer)
                db.session.flush()

                user, raw_password = _create_limited_user(engineer.email or engineer.phone, role="engineer")
                db.session.commit()
                flash(
                    f"✅ تم إضافة المهندس بنجاح. تم إنشاء مستخدم: {user.username} بكلمة مرور مؤقتة.",
                    "success",
                )
                return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer.id))

        else:  # employee
            data, emp_errors = validate_employee_form(request.form)
            form_errors.update(emp_errors)
            # Ensure department required
            if not data.get("department_id"):
                form_errors["department_id"] = "يجب اختيار القسم"

            if form_errors:
                for _, msg in form_errors.items():
                    flash(f"❌ {msg}", "error")
            else:
                employee = Employee(**data)
                db.session.add(employee)
                db.session.flush()

                user, raw_password = _create_limited_user(employee.email or employee.phone, role="employee")
                user.employee_id = employee.id
                user.branch_id = employee.branch_id
                user.section_id = employee.branch_section_id
                invitation, invitation_url, email_sent = _create_employee_invitation(employee, user, raw_password)
                db.session.commit()
                flash(f"✅ تم إضافة الموظف بنجاح. تم إنشاء مستخدم: {user.username}.", "success")
                if email_sent:
                    flash("✉️ تم إرسال رابط إنشاء الحساب للموظف عبر البريد الإلكتروني.", "info")
                else:
                    flash(
                        f"🔗 رابط إنشاء الحساب: {invitation_url} — كلمة المرور المؤقتة: {raw_password}",
                        "warning",
                    )
                return redirect(url_for("consulting_hr.employee_detail", employee_id=employee.id))

    _ensure_default_departments()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    return render_template(
        "hr/staff_form.html",
        form_values=form_values,
        form_errors=form_errors,
        departments=departments,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        EMPLOYMENT_TYPES=EMPLOYMENT_TYPES,
        EMPLOYEE_STATUSES=EMPLOYEE_STATUSES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        branch_choices=branch_choices,
        branch_sections_json=json.dumps(branch_sections_map, ensure_ascii=False),
        title="إضافة موظف/مهندس",
    )


# NOTE: Legacy redirect routes removed to avoid endpoint conflicts with existing
# create_employee/create_engineer handlers above. If external callers need
# redirection, place them in a separate module with unique endpoint names.
