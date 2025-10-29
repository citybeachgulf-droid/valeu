from typing import List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from sqlalchemy import or_

from .models import Client
from .forms import CLIENT_TYPES, validate_client_form
from extensions import db

# Blueprint prefix at /consulting
clients_bp = Blueprint(
    "consulting_clients",
    __name__,
    url_prefix="/consulting",
    template_folder="templates",
)


# ---------- Helpers ----------
def _require_roles(allowed: List[str]) -> Optional[None]:
    role = session.get("role")
    if role not in allowed:
        # Redirect to login if not permitted
        return redirect(url_for("login"))
    return None


# ---------- Pages ----------
@clients_bp.route("/clients")
def list_clients():
    maybe_redirect = _require_roles(["manager", "employee"])  # consulting staff
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    type_filter = (request.args.get("type") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Client.name.ilike(like),
                Client.phone.ilike(like),
                Client.email.ilike(like),
                Client.tax_number.ilike(like),
            )
        )
    if type_filter:
        query = query.filter(Client.type == type_filter)

    query = query.order_by(Client.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "clients/list.html",
        clients=pagination.items,
        pagination=pagination,
        q=q,
        current_type=type_filter,
        CLIENT_TYPES=CLIENT_TYPES,
        title="عملاء الاستشارات"
    )


@clients_bp.route("/clients/<int:client_id>")
def client_detail(client_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow engineers to view
    if maybe_redirect:
        return maybe_redirect

    client = Client.query.get_or_404(client_id)

    # Placeholders for future integration
    related_projects: List[dict] = []  # to be filled when projects module exists
    related_contracts: List[dict] = []  # to be filled when contracts module exists

    return render_template(
        "clients/detail.html",
        client=client,
        related_projects=related_projects,
        related_contracts=related_contracts,
        title=f"تفاصيل العميل - {client.name}"
    )


@clients_bp.route("/clients/new", methods=["GET", "POST"])
def create_client():
    maybe_redirect = _require_roles(["manager", "employee"])  # create restricted
    if maybe_redirect:
        return maybe_redirect

    if request.method == "POST":
        data, errors = validate_client_form(request.form)
        if errors:
            for field, msg in errors.items():
                flash(f"❌ {msg}", "error")
            return render_template(
                "clients/form.html",
                mode="create",
                data=data,
                CLIENT_TYPES=CLIENT_TYPES,
                title="إضافة عميل"
            )

        client = Client(**data)
        db.session.add(client)
        db.session.commit()
        flash("✅ تم إضافة العميل بنجاح", "success")
        return redirect(url_for("consulting_clients.client_detail", client_id=client.id))

    # GET
    return render_template(
        "clients/form.html",
        mode="create",
        data={},
        CLIENT_TYPES=CLIENT_TYPES,
        title="إضافة عميل"
    )


@clients_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
def edit_client(client_id: int):
    maybe_redirect = _require_roles(["manager", "employee"])  # edit restricted
    if maybe_redirect:
        return maybe_redirect

    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        data, errors = validate_client_form(request.form)
        if errors:
            for field, msg in errors.items():
                flash(f"❌ {msg}", "error")
            return render_template(
                "clients/form.html",
                mode="edit",
                data=data,
                CLIENT_TYPES=CLIENT_TYPES,
                client=client,
                title=f"تعديل عميل - {client.name}"
            )

        client.name = data["name"]
        client.type = data["type"]
        client.phone = data["phone"]
        client.email = data["email"]
        client.address = data["address"]
        client.tax_number = data["tax_number"]
        client.notes = data["notes"]
        db.session.commit()
        flash("✅ تم تحديث بيانات العميل", "success")
        return redirect(url_for("consulting_clients.client_detail", client_id=client.id))

    # GET
    return render_template(
        "clients/form.html",
        mode="edit",
        data={
            "name": client.name,
            "type": client.type,
            "phone": client.phone,
            "email": client.email,
            "address": client.address,
            "tax_number": client.tax_number,
            "notes": client.notes,
        },
        CLIENT_TYPES=CLIENT_TYPES,
        client=client,
        title=f"تعديل عميل - {client.name}"
    )


@clients_bp.route("/clients/<int:client_id>/delete", methods=["POST"])
def delete_client(client_id: int):
    maybe_redirect = _require_roles(["manager"])  # restrict delete to manager
    if maybe_redirect:
        return maybe_redirect

    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash("✅ تم حذف العميل", "success")

    return redirect(url_for("consulting_clients.list_clients"))


# ---------- API ----------
@clients_bp.route("/api/clients")
def api_clients():
    # API can be used by authenticated staff only
    maybe_redirect = _require_roles(["manager", "employee", "engineer"])  # allow read by engineers
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    type_filter = (request.args.get("type") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), 200)

    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Client.name.ilike(like),
                Client.phone.ilike(like),
                Client.email.ilike(like),
                Client.tax_number.ilike(like),
            )
        )
    if type_filter:
        query = query.filter(Client.type == type_filter)

    pagination = query.order_by(Client.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": pagination.per_page,
    })
