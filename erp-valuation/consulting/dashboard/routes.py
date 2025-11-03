# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date
from typing import List, Optional

from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
)
from sqlalchemy import func

from extensions import db
from consulting.projects.models import ConsultingProject
from consulting.contracts.models import Contract
from consulting.invoices.models import Invoice
from consulting.hr.models import Task


dashboard_bp = Blueprint(
    "consulting_dashboard",
    __name__,
    url_prefix="/consulting",
    template_folder="templates",
)


# ---------- الدوال المساعدة ----------

def _require_roles(allowed: List[str]) -> Optional[None]:
    role = session.get("role")
    if role not in allowed:
        return redirect(url_for("login"))
    return None


# ---------- الصفحات ----------

@dashboard_bp.route("/dashboard")
def dashboard_home():
    maybe_redirect = _require_roles(["manager", "employee", "engineer", "hr"])  # السماح للمهندسين وHR بالاطلاع
    if maybe_redirect:
        return maybe_redirect

    # المشاريع
    total_projects = db.session.query(func.count(ConsultingProject.id)).scalar() or 0
    ongoing_projects = (
        db.session.query(func.count(ConsultingProject.id))
        .filter(ConsultingProject.status == "قيد التنفيذ")
        .scalar()
        or 0
    )
    finished_projects = (
        db.session.query(func.count(ConsultingProject.id))
        .filter(ConsultingProject.status == "مكتمل")
        .scalar()
        or 0
    )

    # العقود
    active_contracts = (
        db.session.query(func.count(Contract.id)).filter(Contract.status == "ساري").scalar() or 0
    )
    ended_contracts = (
        db.session.query(func.count(Contract.id)).filter(Contract.status == "منتهي").scalar() or 0
    )

    # الفواتير
    total_invoices = db.session.query(func.count(Invoice.id)).scalar() or 0
    paid_invoices = (
        db.session.query(func.count(Invoice.id)).filter(Invoice.status == "مدفوعة").scalar() or 0
    )

    # أحدث خمسة مشاريع
    latest_projects = (
        ConsultingProject.query.order_by(ConsultingProject.created_at.desc()).limit(5).all()
    )

    # المهام المتأخرة (عرض 10 عناصر كحد أقصى)
    overdue_tasks = (
        Task.query.filter(
            Task.status != "مكتملة",
            Task.deadline.isnot(None),
            Task.deadline < date.today(),
        )
        .order_by(Task.deadline.asc())
        .limit(10)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        title="لوحة متابعة الاستشارات الهندسية",
        # Cards
        total_projects=total_projects,
        total_invoices=total_invoices,
        paid_invoices=paid_invoices,
        # Charts data
        projects_chart={
            "labels": ["جارية", "منتهية"],
            "data": [ongoing_projects, finished_projects],
        },
        contracts_chart={
            "labels": ["ساري", "منتهي"],
            "data": [active_contracts, ended_contracts],
        },
        invoices_chart={
            "labels": ["صادرة", "مدفوعة"],
            "data": [total_invoices, paid_invoices],
        },
        # Lists
        latest_projects=latest_projects,
        overdue_tasks=overdue_tasks,
    )
