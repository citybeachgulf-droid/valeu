from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Tuple, Optional

CONTRACT_STATUSES = [
    "ساري",
    "منتهي",
    "موقوف",
]

ALLOWED_FILE_EXTENSIONS = {"pdf"}


def _clean(value: Any) -> str:
    return (value or "").strip()


def _parse_date(value: str) -> Optional[_dt.date]:
    value = _clean(value)
    if not value:
        return None
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def validate_contract_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "project_id": _clean(form.get("project_id")),
        "client_id": _clean(form.get("client_id")),
        "contract_number": _clean(form.get("contract_number")),
        "value": _clean(form.get("value")),
        "start_date": _clean(form.get("start_date")),
        "end_date": _clean(form.get("end_date")),
        "payment_terms": _clean(form.get("payment_terms")),
        "status": _clean(form.get("status")) or "ساري",
        "notes": _clean(form.get("notes")),
    }

    errors: Dict[str, str] = {}

    # Requireds
    if not data["project_id"]:
        errors["project_id"] = "المشروع مطلوب"
    if not data["client_id"]:
        errors["client_id"] = "العميل مطلوب"
    if not data["contract_number"]:
        errors["contract_number"] = "رقم العقد مطلوب"

    # Value -> float
    if data["value"]:
        try:
            data["value"] = float(data["value"])  # type: ignore[assignment]
        except Exception:
            errors["value"] = "قيمة العقد غير صالحة"
    else:
        data["value"] = None

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

    # Status
    if data["status"] not in CONTRACT_STATUSES:
        errors["status"] = "حالة العقد غير صحيحة"

    # Convert ids
    if not errors.get("project_id"):
        try:
            data["project_id"] = int(data["project_id"])  # type: ignore[assignment]
        except Exception:
            errors["project_id"] = "معرّف المشروع غير صالح"
    if not errors.get("client_id"):
        try:
            data["client_id"] = int(data["client_id"])  # type: ignore[assignment]
        except Exception:
            errors["client_id"] = "معرّف العميل غير صالح"

    return data, errors
