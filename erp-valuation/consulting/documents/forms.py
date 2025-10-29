from __future__ import annotations

from typing import Any, Dict, Tuple

DOCUMENT_CATEGORIES = [
    "تصميم",
    "إشراف",
    "مراسلات",
    "تقرير",
]

ALLOWED_FILE_EXTENSIONS = {"pdf", "dwg", "docx", "xlsx"}


def _clean(value: Any) -> str:
    return (value or "").strip()


def validate_document_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    data: Dict[str, Any] = {
        "project_id": _clean(form.get("project_id")),
        "title": _clean(form.get("title")),
        "category": _clean(form.get("category")),
    }

    errors: Dict[str, str] = {}

    if not data["project_id"]:
        errors["project_id"] = "المشروع مطلوب"
    else:
        try:
            data["project_id"] = int(data["project_id"])  # type: ignore[assignment]
        except Exception:
            errors["project_id"] = "معرّف المشروع غير صالح"

    if not data["title"]:
        errors["title"] = "عنوان المستند مطلوب"

    if not data["category"] or data["category"] not in DOCUMENT_CATEGORIES:
        errors["category"] = "التصنيف غير صحيح"

    return data, errors
