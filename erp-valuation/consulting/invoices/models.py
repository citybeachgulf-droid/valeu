from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional

from extensions import db
from consulting.clients.models import Client
from consulting.projects.models import ConsultingProject
from consulting.contracts.models import Contract


INVOICE_STATUSES = [
    "غير مدفوعة",
    "مدفوعة",
    "متأخرة",
]


class Invoice(db.Model):
    __tablename__ = "consulting_invoice"

    id = db.Column(db.Integer, primary_key=True)

    # Relations
    contract_id = db.Column(db.Integer, db.ForeignKey("consulting_contract.id"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("consulting_client.id"), nullable=False, index=True)

    # Core fields
    amount = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="غير مدفوعة", index=True)
    notes = db.Column(db.Text, nullable=True)

    # Payment audit
    paid_date = db.Column(db.Date, nullable=True, index=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = db.relationship(Contract, backref=db.backref("invoices", lazy=True), foreign_keys=[contract_id])
    project = db.relationship(ConsultingProject, backref=db.backref("invoices", lazy=True), foreign_keys=[project_id])
    client = db.relationship(Client, backref=db.backref("invoices", lazy=True), foreign_keys=[client_id])

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Invoice {self.id} amount={self.amount} status={self.status}>"

    def is_overdue(self, today: Optional[date] = None) -> bool:
        if self.status == "مدفوعة":
            return False
        if not self.due_date:
            return False
        today = today or date.today()
        return self.due_date < today

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contract": {"id": self.contract.id, "number": self.contract.contract_number}
            if self.contract
            else None,
            "project": {"id": self.project.id, "name": self.project.name} if self.project else None,
            "client": {"id": self.client.id, "name": self.client.name} if self.client else None,
            "amount": self.amount,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "notes": self.notes,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "overdue": self.is_overdue(),
        }
