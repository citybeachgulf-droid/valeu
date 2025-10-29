import re
from typing import Dict, Tuple, Any

CLIENT_TYPES = ["فرد", "شركة", "جهة حكومية"]

_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(value: Any) -> str:
    return (value or "").strip()


def validate_client_form(form: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Validates client form data coming from request.form.
    Returns (cleaned_data, errors)
    """
    data: Dict[str, Any] = {
        "name": _clean(form.get("name")),
        "type": _clean(form.get("type")),
        "phone": _clean(form.get("phone")),
        "email": _clean(form.get("email")),
        "address": _clean(form.get("address")),
        "tax_number": _clean(form.get("tax_number")),
        "notes": _clean(form.get("notes")),
    }

    errors: Dict[str, str] = {}

    if not data["name"]:
        errors["name"] = "الاسم مطلوب"

    if not data["type"]:
        errors["type"] = "نوع العميل مطلوب"
    elif data["type"] not in CLIENT_TYPES:
        errors["type"] = "نوع العميل غير صحيح"

    if data["email"]:
        if not _email_re.match(data["email"]):
            errors["email"] = "البريد الإلكتروني غير صالح"

    # يمكن إضافة قواعد تحقق إضافية هنا (الهاتف، الرقم الضريبي، ...)

    return data, errors
