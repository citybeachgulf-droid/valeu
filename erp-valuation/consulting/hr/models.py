from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from app import db
from consulting.projects.models import ConsultingProject


class Engineer(db.Model):
    __tablename__ = "consulting_engineer"

    id = db.Column(db.Integer, primary_key=True)

    # Core fields
    name = db.Column(db.String(150), nullable=False, index=True)
    specialty = db.Column(db.String(20), nullable=False, index=True)  # معماري / إنشائي / كهربائي / ميكانيكي
    phone = db.Column(db.String(50), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    join_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="نشط", index=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Engineer {self.id} {self.name!r} {self.specialty!r} status={self.status}>"


class Task(db.Model):
    __tablename__ = "consulting_task"

    id = db.Column(db.Integer, primary_key=True)

    # Relations
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)
    engineer_id = db.Column(db.Integer, db.ForeignKey("consulting_engineer.id"), nullable=False, index=True)

    # Core fields
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="جديدة", index=True)  # جديدة / قيد التنفيذ / مكتملة
    deadline = db.Column(db.Date, nullable=True, index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)  # 0..100

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    project = db.relationship(ConsultingProject, backref=db.backref("tasks", lazy=True), foreign_keys=[project_id])
    engineer = db.relationship(Engineer, backref=db.backref("tasks", lazy=True), foreign_keys=[engineer_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task {self.id} eng={self.engineer_id} proj={self.project_id} status={self.status} progress={self.progress}>"

    # ---- Helpers ----
    def is_overdue(self) -> bool:
        if self.status == "مكتملة":
            return False
        if not self.deadline:
            return False
        return self.deadline < date.today()

    def days_remaining(self) -> Optional[int]:
        if not self.deadline:
            return None
        return (self.deadline - date.today()).days
