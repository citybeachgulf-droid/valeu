from __future__ import annotations

from datetime import date
from typing import Dict, Tuple

# ثابت التخصصات المتاحة للمهندسين
ENGINEER_SPECIALTIES = [
    "معماري",
    "إنشائي",
    "كهربائي",
    "ميكانيكي",
]

ENGINEER_STATUSES = [
    "نشط",
    "غير نشط",
]

# ثابت حالات المهام
TASK_STATUSES = [
    "جديدة",
    "قيد التنفيذ",
    "مكتملة",
]


def _normalize_str(value: str | None) -> str:
    return (value or "").strip()


def validate_new_task_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من حقول إضافة مهمة جديدة.

    يعيد (data, errors)
    """
    errors: Dict[str, str] = {}

    project_id = _normalize_str(form.get("project_id"))
    engineer_id = _normalize_str(form.get("engineer_id"))
    title = _normalize_str(form.get("title"))
    description = _normalize_str(form.get("description"))
    deadline_raw = _normalize_str(form.get("deadline"))

    if not project_id.isdigit():
        errors["project_id"] = "يجب اختيار مشروع صالح"
    if not engineer_id.isdigit():
        errors["engineer_id"] = "يجب تحديد مهندس صالح"
    if not title:
        errors["title"] = "العنوان مطلوب"

    deadline = None
    if deadline_raw:
        try:
            y, m, d = map(int, deadline_raw.split("-"))
            deadline = date(y, m, d)
        except Exception:
            errors["deadline"] = "صيغة الموعد النهائي غير صحيحة"

    data = {
        "project_id": int(project_id) if project_id.isdigit() else None,
        "engineer_id": int(engineer_id) if engineer_id.isdigit() else None,
        "title": title,
        "description": description,
        "deadline": deadline,
    }
    return data, errors


def validate_update_task_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من تحديث حالة المهمة ونسبة الإنجاز"""
    errors: Dict[str, str] = {}

    status = _normalize_str(form.get("status"))
    progress_raw = _normalize_str(form.get("progress"))

    if status not in TASK_STATUSES:
        errors["status"] = "حالة غير صالحة"

    progress = 0
    if progress_raw:
        try:
            progress = max(0, min(100, int(progress_raw)))
        except Exception:
            errors["progress"] = "نسبة الإنجاز يجب أن تكون رقمًا بين 0 و 100"

    data = {
        "status": status,
        "progress": progress,
    }
    return data, errors


def validate_engineer_form(form: Dict[str, str], *, for_update: bool = False) -> Tuple[Dict, Dict[str, str]]:
    """Validate creation or update of an engineer entry."""

    errors: Dict[str, str] = {}

    name = _normalize_str(form.get("name"))
    specialty = _normalize_str(form.get("specialty"))
    phone = _normalize_str(form.get("phone"))
    email = _normalize_str(form.get("email"))
    join_date_raw = _normalize_str(form.get("join_date"))
    status_input = _normalize_str(form.get("status"))

    if not name:
        errors["name"] = "الاسم مطلوب"

    if specialty not in ENGINEER_SPECIALTIES:
        errors["specialty"] = "التخصص غير صالح"

    join_date = None
    if join_date_raw:
        try:
            year, month, day = map(int, join_date_raw.split("-"))
            join_date = date(year, month, day)
        except Exception:
            errors["join_date"] = "صيغة تاريخ الانضمام غير صحيحة"

    if email and "@" not in email:
        errors["email"] = "البريد الإلكتروني غير صالح"

    status: str | None
    if status_input:
        if status_input not in ENGINEER_STATUSES:
            errors["status"] = "الحالة غير صالحة"
        status = status_input
    else:
        status = None if for_update else "نشط"

    data = {
        "name": name,
        "specialty": specialty,
        "phone": phone or None,
        "email": email or None,
        "join_date": join_date,
        "status": status,
    }

    return data, errors
