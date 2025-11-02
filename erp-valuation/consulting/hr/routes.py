from __future__ import annotations

from typing import Dict, List, Optional
from datetime import date

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from sqlalchemy import or_, func

from extensions import db
from consulting.projects.models import ConsultingProject
from .models import Engineer, Task
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
    url_prefix="/consulting",
    template_folder="templates",
)


# ---------- Helpers ----------

def _require_roles(allowed: List[str]) -> Optional[None]:
    role = session.get("role")
    if role not in allowed:
        return redirect(url_for("login"))
    return None


# ---------- Pages ----------

@hr_bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
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
            )
            db.session.add(engineer)
            db.session.commit()

            flash("✅ تم إضافة المهندس بنجاح", "success")
            return redirect(url_for("consulting_hr.dashboard"))

    total_engineers = Engineer.query.count()
    active_engineers = Engineer.query.filter(Engineer.status == "نشط").count()
    inactive_engineers = Engineer.query.filter(Engineer.status != "نشط").count()

    specialty_rows = (
        db.session.query(Engineer.specialty, func.count(Engineer.id))
        .group_by(Engineer.specialty)
        .all()
    )
    specialty_distribution = {row[0]: row[1] for row in specialty_rows}

    today = date.today()

    open_tasks_query = Task.query.filter(Task.status != "مكتملة")
    total_open_tasks = open_tasks_query.count()

    overdue_tasks_query = open_tasks_query.filter(
        Task.deadline.isnot(None),
        Task.deadline < today,
    )
    overdue_tasks_count = overdue_tasks_query.count()
    overdue_tasks = (
        overdue_tasks_query.order_by(Task.deadline.asc())
        .limit(5)
        .all()
    )

    upcoming_tasks = (
        open_tasks_query.filter(
            Task.deadline.isnot(None),
            Task.deadline >= today,
        )
        .order_by(Task.deadline.asc())
        .limit(5)
        .all()
    )

    recent_engineers = (
        Engineer.query.order_by(Engineer.created_at.desc()).limit(5).all()
    )
    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()

    stats = {
        "total_engineers": total_engineers,
        "active_engineers": active_engineers,
        "inactive_engineers": inactive_engineers,
        "total_open_tasks": total_open_tasks,
        "overdue_tasks_count": overdue_tasks_count,
    }

    return render_template(
        "hr/dashboard.html",
        stats=stats,
        specialty_distribution=specialty_distribution,
        recent_engineers=recent_engineers,
        upcoming_tasks=upcoming_tasks,
        overdue_tasks=overdue_tasks,
        recent_tasks=recent_tasks,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
        form_values=form_values,
        form_errors=form_errors,
        title="لوحة الموارد البشرية",
    )


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
            )
            db.session.add(engineer)
            db.session.commit()

            flash("✅ تم إضافة المهندس بنجاح", "success")
            return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer.id))

    return render_template(
        "hr/engineer_form.html",
        mode="create",
        engineer=None,
        form_values=form_values,
        form_errors=form_errors,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
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

            db.session.commit()

            flash("✅ تم تحديث بيانات المهندس", "success")
            return redirect(url_for("consulting_hr.engineer_detail", engineer_id=engineer.id))

    return render_template(
        "hr/engineer_form.html",
        mode="edit",
        engineer=engineer,
        form_values=form_values,
        form_errors=form_errors,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        ENGINEER_STATUSES=ENGINEER_STATUSES,
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
