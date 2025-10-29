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
from sqlalchemy import or_

from extensions import db
from consulting.projects.models import ConsultingProject
from .models import Engineer, Task
from .forms import ENGINEER_SPECIALTIES, TASK_STATUSES, validate_new_task_form, validate_update_task_form


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

@hr_bp.route("/engineers")
def list_engineers():
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
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

    return render_template(
        "hr/engineers.html",
        engineers=pagination.items,
        pagination=pagination,
        q=q,
        current_specialty=specialty,
        current_status=status,
        ENGINEER_SPECIALTIES=ENGINEER_SPECIALTIES,
        overdue_counts=overdue_counts,
        open_counts=open_counts,
        title="مهندسو الاستشارات",
    )


@hr_bp.route("/engineers/<int:engineer_id>")
def engineer_detail(engineer_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    engineer = Engineer.query.get_or_404(engineer_id)
    tasks = Task.query.filter_by(engineer_id=engineer.id).order_by(Task.created_at.desc()).all()

    # For task creation modal
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()

    overdue_count = sum(1 for t in tasks if t.is_overdue())

    return render_template(
        "hr/engineer_detail.html",
        engineer=engineer,
        tasks=tasks,
        projects=projects,
        TASK_STATUSES=TASK_STATUSES,
        overdue_count=overdue_count,
        title=f"المهندس - {engineer.name}",
    )


# ---------- Actions ----------

@hr_bp.route("/engineers/<int:engineer_id>/tasks", methods=["POST"])
def add_task(engineer_id: int):
    maybe_redirect = _require_roles(["manager", "employee"])  # restrict adding tasks to staff
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
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # engineers can update their tasks
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
