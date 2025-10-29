from __future__ import annotations

import os
import time
from typing import List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    send_from_directory,
)
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from extensions import db
from consulting.projects.models import ConsultingProject
from .models import Document
from .forms import (
    DOCUMENT_CATEGORIES,
    ALLOWED_FILE_EXTENSIONS,
    validate_document_form,
)


documents_bp = Blueprint(
    "consulting_documents",
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


def _documents_upload_dir() -> str:
    # Save under static/uploads/projects as requested
    root = current_app.root_path
    path = os.path.join(root, "static", "uploads", "projects")
    os.makedirs(path, exist_ok=True)
    return path


# ---------- Pages ----------

@documents_bp.route("/documents")
def list_documents():
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "finance"])  # allow finance too
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    project_id = (request.args.get("project_id") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Document.query

    if q:
        like = f"%{q}%"
        query = query.filter(or_(Document.title.ilike(like), Document.uploaded_by.ilike(like)))

    if category:
        query = query.filter(Document.category == category)

    if project_id:
        try:
            query = query.filter(Document.project_id == int(project_id))
        except Exception:
            pass

    query = query.order_by(Document.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
    project_map = {p.id: p for p in projects}

    return render_template(
        "documents/list.html",
        documents=pagination.items,
        pagination=pagination,
        q=q,
        current_category=category,
        current_project_id=project_id,
        DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
        projects=projects,
        project_map=project_map,
        title="مستندات المشاريع",
    )


@documents_bp.route("/documents/new", methods=["GET", "POST"])
def create_document():
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "finance"])  # create allowed
    if maybe_redirect:
        return maybe_redirect

    if request.method == "POST":
        data, errors = validate_document_form(request.form)
        file = request.files.get("file")

        if not file or not file.filename:
            errors["file"] = "الملف مطلوب"

        if not errors and file and file.filename:
            original = secure_filename(file.filename)
            ext = _ext_of(original)
            if ext not in ALLOWED_FILE_EXTENSIONS:
                errors["file"] = "امتداد الملف غير مسموح (PDF, DWG, DOCX, XLSX)"

        if errors:
            for _, msg in errors.items():
                flash(f"❌ {msg}", "error")
            projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
            return render_template(
                "documents/form.html",
                mode="create",
                data=data,
                projects=projects,
                DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
                title="رفع مستند مشروع",
            )

        upload_dir = _documents_upload_dir()
        original = secure_filename(file.filename)
        unique = f"doc_project_{data['project_id']}_{int(time.time())}_{original}"
        save_path = os.path.join(upload_dir, unique)
        file.save(save_path)

        doc = Document(
            project_id=data["project_id"],
            title=data["title"],
            category=data["category"],
            file_path=unique,
            uploaded_by=session.get("username") or str(session.get("user_id") or ""),
        )
        db.session.add(doc)
        db.session.commit()

        flash("✅ تم رفع المستند بنجاح", "success")
        return redirect(url_for("consulting_documents.list_documents"))

    # GET
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
    default_project_id = request.args.get("project_id", type=int)
    return render_template(
        "documents/form.html",
        mode="create",
        data={"project_id": default_project_id or ""},
        projects=projects,
        DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
        title="رفع مستند مشروع",
    )


@documents_bp.route("/documents/<int:doc_id>/download")
def download_document(doc_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "finance"])  # allow download
    if maybe_redirect:
        return maybe_redirect

    doc = Document.query.get_or_404(doc_id)
    # Serve from static/uploads/projects while forcing download
    directory = _documents_upload_dir()
    return send_from_directory(directory, doc.file_path, as_attachment=True)
