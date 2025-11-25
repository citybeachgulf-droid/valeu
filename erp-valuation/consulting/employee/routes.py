# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date

from flask import Blueprint, redirect, render_template, session, url_for
from sqlalchemy import func

from consulting.clients.models import Client
from consulting.contracts.models import Contract
from consulting.hr.models import Task
from consulting.invoices.models import Invoice
from consulting.projects.models import ConsultingProject


consulting_employee_bp = Blueprint(
    "consulting_employee",
    __name__,
    url_prefix="/consulting",
    template_folder="templates",
)


@consulting_employee_bp.route("/employee/dashboard")
def dashboard():
    """لوحة الموظف المختص بالاستشارات الهندسية."""
    if session.get("role") not in {"consulting_employee", "consultant", "manager"}:
        return redirect(url_for("login"))

    today = date.today()

    total_projects = ConsultingProject.query.count() or 0
    completed_projects = (
        ConsultingProject.query.filter(ConsultingProject.progress >= 100).count() or 0
    )
    active_projects = total_projects - completed_projects

    total_invoices = Invoice.query.count() or 0
    paid_invoices = Invoice.query.filter(Invoice.paid_date.isnot(None)).count() or 0
    overdue_invoices = (
        Invoice.query.filter(
            Invoice.paid_date.is_(None),
            Invoice.due_date.isnot(None),
            Invoice.due_date < today,
        ).count()
        or 0
    )

    total_contracts = Contract.query.count() or 0
    total_clients = Client.query.count() or 0

    latest_projects = (
        ConsultingProject.query.order_by(ConsultingProject.created_at.desc())
        .limit(5)
        .all()
    )
    latest_invoices = (
        Invoice.query.order_by(Invoice.issue_date.desc()).limit(5).all()
    )
    overdue_tasks = (
        Task.query.filter(
            Task.deadline.isnot(None),
            Task.deadline < today,
        )
        .order_by(Task.deadline.asc())
        .limit(5)
        .all()
    )
    recent_clients = (
        Client.query.order_by(Client.created_at.desc()).limit(5).all()
    )

    total_progress = (
        ConsultingProject.query.with_entities(func.avg(ConsultingProject.progress))
        .scalar()
        or 0
    )

    return render_template(
        "employee/dashboard.html",
        title="لوحة موظف الاستشارات الهندسية",
        total_projects=total_projects,
        active_projects=active_projects,
        completed_projects=completed_projects,
        total_invoices=total_invoices,
        paid_invoices=paid_invoices,
        overdue_invoices=overdue_invoices,
        total_contracts=total_contracts,
        total_clients=total_clients,
        total_progress=round(total_progress, 1),
        latest_projects=latest_projects,
        latest_invoices=latest_invoices,
        overdue_tasks=overdue_tasks,
        recent_clients=recent_clients,
        today=today,
    )
