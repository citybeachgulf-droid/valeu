from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Tuple, Optional

PROJECT_TYPES = [
    "تصميم معماري",
    "إشراف",
    "إدارة مشروع",
    "دراسات",
]

PROJECT_STATUSES = [
    "قيد التنفيذ",
    "مكتمل",
    "متوقف",
]

ALLOWED_FILE_EXTENSIONS = {"pdf", "dwg", "docx", "xlsx"}


def _clean(value: Any) -> str:
    return (value or "").strip()


def _parse_date(value: str) -> Optional[_dt.date]:
    value = _clean(value)
    if not value:
        return None
    # Expect format YYYY-MM-DD from HTML date inputs
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def validate_project_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "client_id": _clean(form.get("client_id")),
        "name": _clean(form.get("name")),
        "type": _clean(form.get("type")),
        "location": _clean(form.get("location")),
        "start_date": _clean(form.get("start_date")),
        "end_date": _clean(form.get("end_date")),
        "status": _clean(form.get("status")) or "قيد التنفيذ",
        "progress": _clean(form.get("progress")) or "0",
        "description": _clean(form.get("description")),
    }

    errors: Dict[str, str] = {}

    # Required fields
    if not data["client_id"]:
        errors["client_id"] = "العميل مطلوب"
    if not data["name"]:
        errors["name"] = "اسم المشروع مطلوب"
    if not data["type"]:
        errors["type"] = "نوع المشروع مطلوب"
    elif data["type"] not in PROJECT_TYPES:
        errors["type"] = "نوع المشروع غير صحيح"

    if data["status"] not in PROJECT_STATUSES:
        errors["status"] = "حالة المشروع غير صحيحة"

    # Progress: integer 0..100
    try:
        progress_int = int(data["progress"])
        if progress_int < 0 or progress_int > 100:
            raise ValueError
    except Exception:
        errors["progress"] = "نسبة الإنجاز يجب أن تكون رقمًا بين 0 و 100"
    else:
        data["progress"] = progress_int

    # Dates
    start_date = _parse_date(data["start_date"]) if data["start_date"] else None
    end_date = _parse_date(data["end_date"]) if data["end_date"] else None
    if data["start_date"] and start_date is None:
        errors["start_date"] = "صيغة تاريخ البدء غير صحيحة"
    if data["end_date"] and end_date is None:
        errors["end_date"] = "صيغة تاريخ الانتهاء غير صحيحة"
    if start_date and end_date and end_date < start_date:
        errors["end_date"] = "تاريخ الانتهاء يجب أن يكون بعد تاريخ البدء"

    data["start_date"] = start_date
    data["end_date"] = end_date

    # Convert client_id to int if valid
    if not errors.get("client_id"):
        try:
            data["client_id"] = int(data["client_id"])  # type: ignore[assignment]
        except Exception:
            errors["client_id"] = "معرّف العميل غير صالح"

    return data, errors


def validate_engineer_assignment_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "engineer_id": _clean(form.get("engineer_id")),
        "role": _clean(form.get("role")),
        "notes": _clean(form.get("notes")),
        "is_lead": (form.get("is_lead") in {"1", "true", "True", "on", "yes"}),
    }

    errors: Dict[str, str] = {}

    if not data["engineer_id"]:
        errors["engineer_id"] = "يجب اختيار مهندس"
    else:
        try:
            data["engineer_id"] = int(data["engineer_id"])  # type: ignore[assignment]
        except Exception:
            errors["engineer_id"] = "معرّف المهندس غير صالح"

    if not data["role"]:
        data["role"] = ""
    if not data["notes"]:
        data["notes"] = ""

    return data, errors
