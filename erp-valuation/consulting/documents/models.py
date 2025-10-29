from __future__ import annotations

from datetime import datetime

from extensions import db


class Document(db.Model):
    __tablename__ = "consulting_document"

    id = db.Column(db.Integer, primary_key=True)

    # Relations
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)

    # Core fields
    uploaded_by = db.Column(db.String(120), nullable=True, index=True)  # username or engineer name
    title = db.Column(db.String(255), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, index=True)  # تصميم / إشراف / مراسلات / تقرير
    file_path = db.Column(db.String(255), nullable=False)  # stored filename under static/uploads/projects
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document {self.id} project={self.project_id} title={self.title!r} category={self.category!r}>"
