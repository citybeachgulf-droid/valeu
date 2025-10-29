from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Tuple, Optional

INVOICE_STATUSES = [
    "غير مدفوعة",
    "مدفوعة",
    "متأخرة",
]


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


def validate_invoice_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "contract_id": _clean(form.get("contract_id")),
        "project_id": _clean(form.get("project_id")),
        "client_id": _clean(form.get("client_id")),
        "amount": _clean(form.get("amount")),
        "issue_date": _clean(form.get("issue_date")),
        "due_date": _clean(form.get("due_date")),
        "status": _clean(form.get("status")) or "غير مدفوعة",
        "notes": _clean(form.get("notes")),
    }

    errors: Dict[str, str] = {}

    if not data["project_id"]:
        errors["project_id"] = "المشروع مطلوب"
    if not data["client_id"]:
        errors["client_id"] = "العميل مطلوب"
    if not data["amount"]:
        errors["amount"] = "المبلغ مطلوب"
    if not data["issue_date"]:
        errors["issue_date"] = "تاريخ الإصدار مطلوب"

    # amount
    if data["amount"] and not errors.get("amount"):
        try:
            value = float(data["amount"])  # type: ignore[assignment]
            if value <= 0:
                raise ValueError
            data["amount"] = value
        except Exception:
            errors["amount"] = "قيمة المبلغ غير صالحة"

    # ids
    if data["contract_id"]:
        try:
            data["contract_id"] = int(data["contract_id"])  # type: ignore[assignment]
        except Exception:
            errors["contract_id"] = "معرّف العقد غير صالح"
    else:
        data["contract_id"] = None

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

    # dates
    issue_date = _parse_date(data["issue_date"]) if data["issue_date"] else None
    due_date = _parse_date(data["due_date"]) if data["due_date"] else None
    if data["issue_date"] and issue_date is None:
        errors["issue_date"] = "صيغة تاريخ الإصدار غير صحيحة"
    if data["due_date"] and due_date is None:
        errors["due_date"] = "صيغة تاريخ الاستحقاق غير صحيحة"
    if issue_date and due_date and due_date < issue_date:
        errors["due_date"] = "تاريخ الاستحقاق يجب أن يكون بعد تاريخ الإصدار"
    data["issue_date"] = issue_date
    data["due_date"] = due_date

    # status
    if data["status"] not in INVOICE_STATUSES:
        errors["status"] = "حالة الفاتورة غير صحيحة"

    return data, errors


def validate_status_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "status": _clean(form.get("status")),
        "paid_date": _clean(form.get("paid_date")),
    }
    errors: Dict[str, str] = {}

    if data["status"] not in INVOICE_STATUSES:
        errors["status"] = "حالة الفاتورة غير صحيحة"

    pd = _parse_date(data["paid_date"]) if data["paid_date"] else None
    data["paid_date"] = pd

    return data, errors
