from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from extensions import db
from consulting.clients.models import Client
from .models import ConsultingProject, ProjectFile
from .forms import (
    PROJECT_TYPES,
    PROJECT_STATUSES,
    ALLOWED_FILE_EXTENSIONS,
    validate_project_form,
)
from consulting.clients.forms import validate_client_form, CLIENT_TYPES


projects_bp = Blueprint(
    "consulting_projects",
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


def _ext_of(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1]
    parts = base.rsplit(".", 1)
    return parts[-1].lower() if len(parts) == 2 else ""


# ---------- Pages ----------

@projects_bp.route("/projects")
def list_projects():
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    client_id = (request.args.get("client_id") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = ConsultingProject.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                ConsultingProject.name.ilike(like),
                ConsultingProject.location.ilike(like),
                ConsultingProject.description.ilike(like),
            )
        )
    if status_filter:
        query = query.filter(ConsultingProject.status == status_filter)
    if client_id:
        try:
            query = query.filter(ConsultingProject.client_id == int(client_id))
        except Exception:
            pass

    query = query.order_by(ConsultingProject.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Clients for filter dropdown
    clients = Client.query.order_by(Client.name.asc()).all()

    return render_template(
        "projects/list.html",
        projects=pagination.items,
        pagination=pagination,
        q=q,
        current_status=status_filter,
        current_client_id=client_id,
        PROJECT_STATUSES=PROJECT_STATUSES,
        clients=clients,
        title="مشاريع الاستشارات",
    )


@projects_bp.route("/projects/<int:project_id>")
def project_detail(project_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    project = ConsultingProject.query.get_or_404(project_id)

    # Placeholder data for contracts and engineers (no schema defined yet)
    related_contracts: List[Dict] = []
    assigned_engineers: List[Dict] = []

    # Files
    files = ProjectFile.query.filter_by(project_id=project.id).order_by(ProjectFile.uploaded_at.desc()).all()

    return render_template(
        "projects/detail.html",
        project=project,
        files=files,
        related_contracts=related_contracts,
        assigned_engineers=assigned_engineers,
        PROJECT_STATUSES=PROJECT_STATUSES,
        PROJECT_TYPES=PROJECT_TYPES,
        title=f"تفاصيل المشروع - {project.name}",
    )


# ---------- Create / Edit (optional for operability) ----------

@projects_bp.route("/projects/new", methods=["GET", "POST"])
def create_project():
    maybe_redirect = _require_roles(["manager", "employee"])  # create restricted
    if maybe_redirect:
        return maybe_redirect

    if request.method == "POST":
        # Allow inline creation of a new client when adding a project
        form_data = request.form.to_dict(flat=True)

        new_client_name = (form_data.get("new_client_name") or "").strip()
        if new_client_name:
            # Build client form payload from prefixed fields
            client_form_payload = {
                "name": new_client_name,
                "type": (form_data.get("new_client_type") or "").strip(),
                "phone": (form_data.get("new_client_phone") or "").strip(),
                "email": (form_data.get("new_client_email") or "").strip(),
                "address": (form_data.get("new_client_address") or "").strip(),
                "tax_number": (form_data.get("new_client_tax_number") or "").strip(),
                "notes": (form_data.get("new_client_notes") or "").strip(),
            }

            client_clean, client_errors = validate_client_form(client_form_payload)
            if client_errors:
                for _, msg in client_errors.items():
                    flash(f"❌ {msg}", "error")
                clients = Client.query.order_by(Client.name.asc()).all()
                # Preserve entered values
                data = form_data
                return render_template(
                    "projects/form.html",
                    mode="create",
                    data=data,
                    clients=clients,
                    PROJECT_TYPES=PROJECT_TYPES,
                    PROJECT_STATUSES=PROJECT_STATUSES,
                    CLIENT_TYPES=CLIENT_TYPES,
                    title="إضافة مشروع",
                )

            # Create and persist the client, then inject its id into project form
            client = Client(**client_clean)
            db.session.add(client)
            db.session.commit()
            form_data["client_id"] = str(client.id)
            flash("✅ تم إنشاء العميل وربطه بالمشروع", "success")

        data, errors = validate_project_form(form_data)
        if errors:
            for _, msg in errors.items():
                flash(f"❌ {msg}", "error")
            clients = Client.query.order_by(Client.name.asc()).all()
            # Preserve also the inline client fields on error
            data_with_client = {**form_data, **{k: v for k, v in data.items()}}
            return render_template(
                "projects/form.html",
                mode="create",
                data=data_with_client,
                clients=clients,
                PROJECT_TYPES=PROJECT_TYPES,
                PROJECT_STATUSES=PROJECT_STATUSES,
                CLIENT_TYPES=CLIENT_TYPES,
                title="إضافة مشروع",
            )
        project = ConsultingProject(**data)
        db.session.add(project)
        db.session.commit()
        flash("✅ تم إضافة المشروع بنجاح", "success")
        return redirect(url_for("consulting_projects.project_detail", project_id=project.id))

    clients = Client.query.order_by(Client.name.asc()).all()
    return render_template(
        "projects/form.html",
        mode="create",
        data={},
        clients=clients,
        PROJECT_TYPES=PROJECT_TYPES,
        PROJECT_STATUSES=PROJECT_STATUSES,
        CLIENT_TYPES=CLIENT_TYPES,
        title="إضافة مشروع",
    )


@projects_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
def edit_project(project_id: int):
    maybe_redirect = _require_roles(["manager", "employee"])  # edit restricted
    if maybe_redirect:
        return maybe_redirect

    project = ConsultingProject.query.get_or_404(project_id)

    if request.method == "POST":
        data, errors = validate_project_form(request.form)
        if errors:
            for _, msg in errors.items():
                flash(f"❌ {msg}", "error")
            clients = Client.query.order_by(Client.name.asc()).all()
            return render_template(
                "projects/form.html",
                mode="edit",
                data=data,
                clients=clients,
                project=project,
                PROJECT_TYPES=PROJECT_TYPES,
                PROJECT_STATUSES=PROJECT_STATUSES,
                CLIENT_TYPES=CLIENT_TYPES,
                title=f"تعديل مشروع - {project.name}",
            )

        project.client_id = data["client_id"]
        project.name = data["name"]
        project.type = data["type"]
        project.location = data["location"]
        project.start_date = data["start_date"]
        project.end_date = data["end_date"]
        project.status = data["status"]
        project.progress = data["progress"]
        project.description = data["description"]
        db.session.commit()
        flash("✅ تم تحديث بيانات المشروع", "success")
        return redirect(url_for("consulting_projects.project_detail", project_id=project.id))

    # GET
    clients = Client.query.order_by(Client.name.asc()).all()
    return render_template(
        "projects/form.html",
        mode="edit",
        data={
            "client_id": project.client_id,
            "name": project.name,
            "type": project.type,
            "location": project.location or "",
            "start_date": project.start_date.isoformat() if project.start_date else "",
            "end_date": project.end_date.isoformat() if project.end_date else "",
            "status": project.status,
            "progress": project.progress,
            "description": project.description or "",
        },
        clients=clients,
        project=project,
        PROJECT_TYPES=PROJECT_TYPES,
        PROJECT_STATUSES=PROJECT_STATUSES,
        CLIENT_TYPES=CLIENT_TYPES,
        title=f"تعديل مشروع - {project.name}",
    )


# ---------- File Upload ----------

@projects_bp.route("/projects/<int:project_id>/upload", methods=["POST"])
def upload_project_file(project_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to upload
    if maybe_redirect:
        return maybe_redirect

    project = ConsultingProject.query.get_or_404(project_id)

    files = request.files.getlist("files")
    if not files:
        flash("❌ لم يتم اختيار ملفات", "error")
        return redirect(url_for("consulting_projects.project_detail", project_id=project.id))

    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    os.makedirs(upload_dir, exist_ok=True)

    saved_count = 0
    for file in files:
        if not file or not file.filename:
            continue
        original = secure_filename(file.filename)
        ext = _ext_of(original)
        if ext not in ALLOWED_FILE_EXTENSIONS:
            flash(f"⚠️ تم تجاهل {original} (امتداد غير مسموح)", "warning")
            continue
        unique = f"project_{project.id}_{int(time.time())}_{secure_filename(original)}"
        path = os.path.join(upload_dir, unique)
        file.save(path)
        pf = ProjectFile(
            project_id=project.id,
            stored_filename=unique,
            original_filename=original,
            file_type=ext,
            uploaded_by=session.get("user_id"),
        )
        db.session.add(pf)
        saved_count += 1

    if saved_count:
        db.session.commit()
        flash(f"✅ تم رفع {saved_count} ملف/ملفات", "success")
    else:
        flash("⚠️ لم يتم حفظ أي ملف", "warning")

    return redirect(url_for("consulting_projects.project_detail", project_id=project.id))
