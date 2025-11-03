from __future__ import annotations

from datetime import date
from typing import List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from sqlalchemy import or_, func

from extensions import db
from consulting.clients.models import Client
from consulting.projects.models import ConsultingProject
from consulting.contracts.models import Contract
from .models import Invoice, INVOICE_STATUSES
from .forms import validate_invoice_form, validate_status_form, INVOICE_STATUSES as FORM_STATUSES


invoices_bp = Blueprint(
    "consulting_invoices",
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

@invoices_bp.route("/invoices")
def list_invoices():
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "finance", "hr"])  # read wide
    if maybe_redirect:
        return maybe_redirect

    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    client_id = (request.args.get("client_id") or "").strip()
    project_id = (request.args.get("project_id") or "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Invoice.query

    if q:
        like = f"%{q}%"
        query = query.join(ConsultingProject, Invoice.project_id == ConsultingProject.id) \
                     .join(Client, Invoice.client_id == Client.id) \
                     .outerjoin(Contract, Invoice.contract_id == Contract.id) \
                     .filter(
                         or_(
                             Client.name.ilike(like),
                             ConsultingProject.name.ilike(like),
                             Contract.contract_number.ilike(like),
                         )
                     )

    if status_filter:
        query = query.filter(Invoice.status == status_filter)

    if client_id:
        try:
            query = query.filter(Invoice.client_id == int(client_id))
        except Exception:
            pass

    if project_id:
        try:
            query = query.filter(Invoice.project_id == int(project_id))
        except Exception:
            pass

    query = query.order_by(Invoice.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # For filters
    clients = Client.query.order_by(Client.name.asc()).all()
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()

    # Overdue alert count
    today = date.today()
    overdue_count = sum(1 for inv in pagination.items if inv.is_overdue(today))

    return render_template(
        "invoices/list.html",
        invoices=pagination.items,
        pagination=pagination,
        q=q,
        INVOICE_STATUSES=INVOICE_STATUSES,
        current_status=status_filter,
        current_client_id=client_id,
        current_project_id=project_id,
        clients=clients,
        projects=projects,
        overdue_count=overdue_count,
        title="فواتير الاستشارات",
    )


@invoices_bp.route("/invoices/new", methods=["GET", "POST"])
def create_invoice():
    maybe_redirect = _require_roles(["manager", "employee", "finance", "hr"])  # create restricted
    if maybe_redirect:
        return maybe_redirect

    if request.method == "POST":
        data, errors = validate_invoice_form(request.form)
        if errors:
            for _, msg in errors.items():
                flash(f"❌ {msg}", "error")
            clients = Client.query.order_by(Client.name.asc()).all()
            projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
            contracts = Contract.query.order_by(Contract.id.desc()).limit(200).all()
            return render_template(
                "invoices/form.html",
                mode="create",
                data=data,
                clients=clients,
                projects=projects,
                contracts=contracts,
                INVOICE_STATUSES=FORM_STATUSES,
                title="إضافة فاتورة",
            )

        invoice = Invoice(**data)
        db.session.add(invoice)
        db.session.commit()
        flash("✅ تم إضافة الفاتورة بنجاح", "success")
        return redirect(url_for("consulting_invoices.invoice_detail", invoice_id=invoice.id))

    # GET
    # Optional defaults via querystring
    default_client_id = (request.args.get("client_id") or "").strip()
    default_project_id = (request.args.get("project_id") or "").strip()

    clients = Client.query.order_by(Client.name.asc()).all()
    projects = ConsultingProject.query.order_by(ConsultingProject.name.asc()).all()
    contracts = Contract.query.order_by(Contract.id.desc()).limit(200).all()

    return render_template(
        "invoices/form.html",
        mode="create",
        data={
            "client_id": int(default_client_id) if default_client_id.isdigit() else "",
            "project_id": int(default_project_id) if default_project_id.isdigit() else "",
            "status": "غير مدفوعة",
        },
        clients=clients,
        projects=projects,
        contracts=contracts,
        INVOICE_STATUSES=FORM_STATUSES,
        title="إضافة فاتورة",
    )


@invoices_bp.route("/invoices/<int:invoice_id>")
def invoice_detail(invoice_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "finance", "hr"])  # read wide
    if maybe_redirect:
        return maybe_redirect

    invoice = Invoice.query.get_or_404(invoice_id)
    
    # ✅ البحث عن الفواتير المالية المرتبطة
    # استخدام استيراد ديناميكي لتجنب الاعتماد الدائري
    linked_finance_invoices = []
    try:
        # محاولة الاستيراد من app (يتم تسجيله بعد تحميل app)
        import sys
        if 'app' in sys.modules:
            CustomerInvoice = sys.modules['app'].CustomerInvoice
            linked_finance_invoices = CustomerInvoice.query.filter_by(consulting_invoice_id=invoice_id).all()
    except (ImportError, AttributeError, KeyError):
        # إذا فشل، نستخدم query مباشرة عبر SQL
        from sqlalchemy import text
        try:
            result = db.session.execute(
                text("SELECT id, invoice_number, customer_name, amount, issued_at FROM customer_invoice WHERE consulting_invoice_id = :inv_id"),
                {"inv_id": invoice_id}
            )
            for row in result:
                # إنشاء كائن بسيط للعرض
                linked_finance_invoices.append(type('obj', (object,), {
                    'id': row[0],
                    'invoice_number': row[1],
                    'customer_name': row[2],
                    'amount': row[3],
                    'issued_at': row[4]
                })())
        except Exception:
            linked_finance_invoices = []

    return render_template(
        "invoices/detail.html",
        invoice=invoice,
        linked_finance_invoices=linked_finance_invoices,
        INVOICE_STATUSES=INVOICE_STATUSES,
        title=f"تفاصيل الفاتورة - #{invoice.id}",
    )


@invoices_bp.route("/invoices/<int:invoice_id>/status", methods=["POST"])
def update_invoice_status(invoice_id: int):
    maybe_redirect = _require_roles(["manager", "employee", "finance", "hr"])  # update restricted
    if maybe_redirect:
        return maybe_redirect

    invoice = Invoice.query.get_or_404(invoice_id)

    data, errors = validate_status_form(request.form)
    if errors:
        for _, msg in errors.items():
            flash(f"❌ {msg}", "error")
        return redirect(url_for("consulting_invoices.invoice_detail", invoice_id=invoice.id))

    # Apply
    invoice.status = data["status"]
    # If paid and date not provided -> today
    if invoice.status == "مدفوعة":
        invoice.paid_date = data["paid_date"] or date.today()
    else:
        # If not paid, do not keep a paid_date to avoid confusion
        invoice.paid_date = data["paid_date"]

    db.session.commit()
    flash("✅ تم تحديث حالة الفاتورة", "success")
    return redirect(url_for("consulting_invoices.invoice_detail", invoice_id=invoice.id))


@invoices_bp.route("/invoices/reports")
def invoices_reports():
    maybe_redirect = _require_roles(["manager", "finance", "hr"])  # reports restricted
    if maybe_redirect:
        return maybe_redirect

    total_amount = db.session.query(func.coalesce(func.sum(Invoice.amount), 0.0)).scalar() or 0.0
    unpaid_amount = (
        db.session.query(func.coalesce(func.sum(Invoice.amount), 0.0))
        .filter(Invoice.status != "مدفوعة")
        .scalar()
        or 0.0
    )

    # Overdue amount: due_date < today and not paid
    today = date.today()
    overdue_amount = (
        db.session.query(func.coalesce(func.sum(Invoice.amount), 0.0))
        .filter(Invoice.status != "مدفوعة")
        .filter(Invoice.due_date.isnot(None))
        .filter(Invoice.due_date < today)
        .scalar()
        or 0.0
    )

    totals = {
        "total": total_amount,
        "unpaid": unpaid_amount,
        "overdue": overdue_amount,
    }

    return render_template(
        "invoices/reports.html",
        totals=totals,
        title="تقارير الفواتير"
    )
