from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from extensions import db


# Keep table names prefixed to avoid collisions with core app tables
class ConsultingProject(db.Model):
    __tablename__ = "consulting_project"

    id = db.Column(db.Integer, primary_key=True)

    # Relations
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("consulting_client.id"),
        nullable=False,
        index=True,
    )

    # Core fields
    name = db.Column(db.String(200), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False, index=True)  # تصميم معماري / إشراف / إدارة مشروع / دراسات
    location = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="قيد التنفيذ", index=True)  # قيد التنفيذ / مكتمل / متوقف
    progress = db.Column(db.Integer, nullable=False, default=0)  # 0..100
    description = db.Column(db.Text, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = db.relationship(
        "Client",
        backref=db.backref("projects", lazy=True),
        primaryjoin="Client.id==ConsultingProject.client_id",
    )
    files = db.relationship(
        "ProjectFile",
        backref="project",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConsultingProject {self.id} {self.name!r} status={self.status} progress={self.progress}>"

    def is_active(self) -> bool:
        return self.status == "قيد التنفيذ"

    def duration_days(self) -> Optional[int]:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None


class ProjectFile(db.Model):
    __tablename__ = "consulting_project_file"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)

    # Stored filename on disk (in app.config['UPLOAD_FOLDER'])
    stored_filename = db.Column(db.String(255), nullable=False)
    # Original filename provided by the user
    original_filename = db.Column(db.String(255), nullable=False)
    # Optional simple content type or extension (e.g., pdf, dwg, docx)
    file_type = db.Column(db.String(20), nullable=True, index=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Optional B2 identifiers if the deployment stores files remotely later
    b2_file_name = db.Column(db.String(255), nullable=True)
    b2_file_id = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectFile {self.id} project={self.project_id} name={self.original_filename!r}>"


class ProjectEngineerAssignment(db.Model):
    __tablename__ = "consulting_project_engineer"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("consulting_project.id"),
        nullable=False,
        index=True,
    )
    engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("consulting_engineer.id"),
        nullable=False,
        index=True,
    )

    role = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_lead = db.Column(db.Boolean, nullable=False, default=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship(
        "ConsultingProject",
        backref=db.backref(
            "engineer_assignments",
            lazy=True,
            cascade="all, delete-orphan",
        ),
        foreign_keys=[project_id],
    )
    engineer = db.relationship(
        "Engineer",
        backref=db.backref("project_assignments", lazy=True),
        foreign_keys=[engineer_id],
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProjectEngineerAssignment project={self.project_id} "
            f"engineer={self.engineer_id} lead={self.is_lead}>"
        )

