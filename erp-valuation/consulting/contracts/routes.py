from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

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
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from extensions import db
from consulting.clients.models import Client
from consulting.projects.models import ConsultingProject
from .models import Contract, generate_unique_contract_number, preview_next_contract_number
from .forms import (
    CONTRACT_STATUSES,
    ALLOWED_FILE_EXTENSIONS,
    validate_contract_form,
)


contracts_bp = Blueprint(
    "consulting_contracts",
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

@contracts_bp.route("/contracts")
def list_contracts():
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    client_id = (request.args.get("client_id") or "").strip()
    project_id = (request.args.get("project_id") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Contract.query

    # Optional search joins
    if q:
        like = f"%{q}%"
        query = (
            query.join(ConsultingProject, Contract.project_id == ConsultingProject.id)
            .join(Client, Contract.client_id == Client.id)
            .filter(
                or_(
                    Contract.contract_number.ilike(like),
                    ConsultingProject.name.ilike(like),
                    Client.name.ilike(like),
                )
            )
        )

    if status_filter:
        query = query.filter(Contract.status == status_filter)

    if client_id:
        try:
            query = query.filter(Contract.client_id == int(client_id))
        except Exception:
            pass

    if project_id:
        try:
            query = query.filter(Contract.project_id == int(project_id))
        except Exception:
            pass

    query = query.order_by(Contract.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    clients = Client.query.order_by(Client.name.asc()).all()
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()

    return render_template(
        "contracts/list.html",
        contracts=pagination.items,
        pagination=pagination,
        q=q,
        current_status=status_filter,
        current_client_id=client_id,
        current_project_id=project_id,
        CONTRACT_STATUSES=CONTRACT_STATUSES,
        clients=clients,
        projects=projects,
        title="عقود الاستشارات",
    )


@contracts_bp.route("/contracts/<int:contract_id>")
def contract_detail(contract_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    contract = Contract.query.get_or_404(contract_id)

    return render_template(
        "contracts/detail.html",
        contract=contract,
        title=f"تفاصيل العقد - {contract.contract_number}",
    )


@contracts_bp.route("/contracts/new", methods=["GET", "POST"])
def create_contract():
    maybe_redirect = _require_roles(["manager", "employee"])  # create restricted
    if maybe_redirect:
        return maybe_redirect

    if request.method == "POST":
        data, errors = validate_contract_form(request.form)
        if errors:
            for _, msg in errors.items():
                flash(f"❌ {msg}", "error")
            clients = Client.query.order_by(Client.name.asc()).all()
            projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
            return render_template(
                "contracts/form.html",
                mode="create",
                data=data,
                clients=clients,
                projects=projects,
                CONTRACT_STATUSES=CONTRACT_STATUSES,
                next_contract_number=preview_next_contract_number(),
                title="إضافة عقد",
            )

        data["contract_number"] = generate_unique_contract_number()
        contract = Contract(**data)
        db.session.add(contract)
        db.session.commit()

        # Optional file upload (PDF only)
        file = request.files.get("file")
        if file and file.filename:
            original = secure_filename(file.filename)
            ext = _ext_of(original)
            if ext in ALLOWED_FILE_EXTENSIONS:
                upload_dir = current_app.config.get("UPLOAD_FOLDER")
                os.makedirs(upload_dir, exist_ok=True)
                unique = f"contract_{contract.id}_{int(time.time())}_{secure_filename(original)}"
                path = os.path.join(upload_dir, unique)
                file.save(path)
                contract.file_path = unique
                db.session.commit()
            else:
                flash("⚠️ تم تجاهل الملف (يجب أن يكون PDF)", "warning")

        flash("✅ تم إضافة العقد بنجاح", "success")
        return redirect(url_for("consulting_contracts.contract_detail", contract_id=contract.id))

    clients = Client.query.order_by(Client.name.asc()).all()
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
    default_project_id = request.args.get("project_id", type=int)
    default_client_id = request.args.get("client_id", type=int)
    prefilled: Dict[str, Any] = {}
    if default_project_id and any(p.id == default_project_id for p in projects):
        prefilled["project_id"] = default_project_id
    if default_client_id and any(c.id == default_client_id for c in clients):
        prefilled["client_id"] = default_client_id
    return render_template(
        "contracts/form.html",
        mode="create",
        data=prefilled,
        clients=clients,
        projects=projects,
        CONTRACT_STATUSES=CONTRACT_STATUSES,
        next_contract_number=preview_next_contract_number(),
        title="إضافة عقد",
    )


# ---------- File Upload ----------

@contracts_bp.route("/contracts/<int:contract_id>/upload", methods=["POST"])
def upload_contract_file(contract_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to upload
    if maybe_redirect:
        return maybe_redirect

    contract = Contract.query.get_or_404(contract_id)

    file = request.files.get("file")
    if not file or not file.filename:
        flash("❌ لم يتم اختيار ملف", "error")
        return redirect(url_for("consulting_contracts.contract_detail", contract_id=contract.id))

    original = secure_filename(file.filename)
    ext = _ext_of(original)
    if ext not in ALLOWED_FILE_EXTENSIONS:
        flash("⚠️ امتداد غير مسموح. يُقبل فقط PDF", "warning")
        return redirect(url_for("consulting_contracts.contract_detail", contract_id=contract.id))

    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    os.makedirs(upload_dir, exist_ok=True)
    unique = f"contract_{contract.id}_{int(time.time())}_{secure_filename(original)}"
    path = os.path.join(upload_dir, unique)
    file.save(path)
    contract.file_path = unique
    db.session.commit()

    flash("✅ تم رفع العقد (PDF) بنجاح", "success")
    return redirect(url_for("consulting_contracts.contract_detail", contract_id=contract.id))


# ---------- API ----------

@contracts_bp.route("/api/contracts")
def api_contracts():
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # read allowed by engineers
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    client_id = (request.args.get("client_id") or "").strip()
    project_id = (request.args.get("project_id") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), 200)

    query = Contract.query

    if q:
        like = f"%{q}%"
        query = (
            query.join(ConsultingProject, Contract.project_id == ConsultingProject.id)
            .join(Client, Contract.client_id == Client.id)
            .filter(
                or_(
                    Contract.contract_number.ilike(like),
                    ConsultingProject.name.ilike(like),
                    Client.name.ilike(like),
                )
            )
        )

    if status_filter:
        query = query.filter(Contract.status == status_filter)
    if client_id:
        try:
            query = query.filter(Contract.client_id == int(client_id))
        except Exception:
            pass
    if project_id:
        try:
            query = query.filter(Contract.project_id == int(project_id))
        except Exception:
            pass

    pagination = query.order_by(Contract.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": pagination.per_page,
    })
