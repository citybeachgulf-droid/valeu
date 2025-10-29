from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional

from extensions import db
from consulting.clients.models import Client
from consulting.projects.models import ConsultingProject


class Contract(db.Model):
    __tablename__ = "consulting_contract"

    id = db.Column(db.Integer, primary_key=True)

    # Relations
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("consulting_client.id"), nullable=False, index=True)

    # Core fields
    contract_number = db.Column(db.String(100), nullable=False, index=True)
    value = db.Column(db.Float, nullable=True)
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    payment_terms = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ساري", index=True)  # ساري / منتهي / موقوف
    notes = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)  # stored filename in UPLOAD_FOLDER

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    project = db.relationship(ConsultingProject, backref=db.backref("contracts", lazy=True), foreign_keys=[project_id])
    client = db.relationship(Client, backref=db.backref("contracts", lazy=True), foreign_keys=[client_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<Contract {self.id} no={self.contract_number!r} status={self.status}>"

    # ---- Helpers ----
    def days_to_expiry(self) -> Optional[int]:
        if not self.end_date:
            return None
        return (self.end_date - date.today()).days

    def is_near_expiry(self) -> bool:
        d = self.days_to_expiry()
        return self.status == "ساري" and d is not None and 0 <= d <= 15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project": {"id": self.project.id, "name": self.project.name} if self.project else None,
            "client": {"id": self.client.id, "name": self.client.name} if self.client else None,
            "contract_number": self.contract_number,
            "value": self.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "payment_terms": self.payment_terms,
            "status": self.status,
            "notes": self.notes,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "days_to_expiry": self.days_to_expiry(),
            "near_expiry": self.is_near_expiry(),
        }
