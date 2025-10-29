from datetime import datetime
from typing import Any, Dict

from extensions import db


class Client(db.Model):
    __tablename__ = "consulting_client"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False, index=True)  # فرد / شركة / جهة حكومية
    phone = db.Column(db.String(50), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    tax_number = db.Column(db.String(100), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug friendly only
        return f"<Client {self.id} {self.name!r}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "tax_number": self.tax_number,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
