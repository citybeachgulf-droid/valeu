from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Tuple, Optional
from decimal import Decimal, InvalidOperation

# ==================== ثوابت القيم الممكنة ====================

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

# حالات الموظفين
EMPLOYEE_STATUSES = [
    "نشط",
    "إجازة",
    "متوقف",
    "مستقل",
]

# أنواع التوظيف
EMPLOYMENT_TYPES = [
    "دوام كامل",
    "دوام جزئي",
    "عقد",
    "مستقل",
]

# أنواع الإجازات الأساسية
LEAVE_TYPES_BASIC = [
    "إجازة سنوية",
    "إجازة مرضية",
    "إجازة بدون راتب",
    "إجازة أمومة",
    "إجازة والدية",
]

# حالات طلبات الإجازات
LEAVE_REQUEST_STATUSES = [
    "معلق",
    "معتمد",
    "مرفوض",
    "ملغي",
]

# حالات الحضور
ATTENDANCE_STATUSES = [
    "حاضر",
    "غائب",
    "إجازة",
    "متأخر",
]

# حالات الرواتب
PAYROLL_STATUSES = [
    "مسودة",
    "معتمد",
    "مدفوع",
]

# حالات التقييمات
PERFORMANCE_REVIEW_STATUSES = [
    "مسودة",
    "منتهي",
    "معتمد",
]

PERFORMANCE_PERIODS = [
    "شهري",
    "ربع سنوي",
    "سنوي",
]

# حالات التوظيف
JOB_POSTING_STATUSES = [
    "مفتوح",
    "مغلق",
    "ملغي",
]

CANDIDATE_STATUSES = [
    "جديد",
    "قيد المراجعة",
    "مختار",
    "مرفوض",
    "غير مناسب",
]

INTERVIEW_STATUSES = [
    "مخطط",
    "تم",
    "ملغي",
]

INTERVIEW_RESULTS = [
    "نجح",
    "فشل",
    "معلق",
]

GOAL_PRIORITIES = [
    "عالي",
    "متوسط",
    "منخفض",
]

GOAL_STATUSES = [
    "قيد التنفيذ",
    "مكتمل",
    "ملغي",
]


def _normalize_str(value: str | None) -> str:
    return (value or "").strip()


def _normalize_decimal(value: str | None) -> Optional[Decimal]:
    """تحويل قيمة نصية إلى Decimal"""
    if not value:
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _normalize_int(value: str | None) -> Optional[int]:
    """تحويل قيمة نصية إلى int"""
    if not value:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _parse_date(value: str | None) -> Optional[date]:
    """تحويل قيمة نصية إلى date"""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _parse_datetime(value: str | None) -> Optional[datetime]:
    """تحويل قيمة نصية إلى datetime"""
    if not value:
        return None
    try:
        # محاولة تنسيقات متعددة
        for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None
    except (ValueError, AttributeError):
        return None


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
    department_id_raw = _normalize_str(form.get("department_id"))

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

    department_id = None
    if department_id_raw:
        try:
            department_id = int(department_id_raw)
        except (ValueError, TypeError):
            errors["department_id"] = "معرف القسم غير صالح"

    data = {
        "name": name,
        "specialty": specialty,
        "phone": phone or None,
        "email": email or None,
        "join_date": join_date,
        "status": status,
        "department_id": department_id,
    }

    return data, errors


# ==================== دوال التحقق للنماذج الجديدة ====================

def validate_employee_form(form: Dict[str, str], *, for_update: bool = False) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من بيانات الموظف"""
    errors: Dict[str, str] = {}
    
    first_name = _normalize_str(form.get("first_name"))
    last_name = _normalize_str(form.get("last_name"))
    email = _normalize_str(form.get("email"))
    employee_number = _normalize_str(form.get("employee_number"))
    
    # اجعل الحقول الإجبارية عند الإضافة هي الاسم والقسم فقط
    if not first_name:
        errors["first_name"] = "الاسم مطلوب"
    
    if email and "@" not in email:
        errors["email"] = "البريد الإلكتروني غير صالح"
    
    status = _normalize_str(form.get("status")) or ("نشط" if not for_update else None)
    if status and status not in EMPLOYEE_STATUSES:
        errors["status"] = "الحالة غير صالحة"
    
    join_date = _parse_date(form.get("join_date"))
    date_of_birth = _parse_date(form.get("date_of_birth"))
    contract_start_date = _parse_date(form.get("contract_start_date"))
    contract_end_date = _parse_date(form.get("contract_end_date"))
    
    if contract_start_date and contract_end_date and contract_start_date > contract_end_date:
        errors["contract_end_date"] = "تاريخ انتهاء العقد يجب أن يكون بعد تاريخ البداية"
    
    base_salary = _normalize_decimal(form.get("base_salary"))
    if base_salary and base_salary < 0:
        errors["base_salary"] = "الراتب يجب أن يكون رقمًا موجبًا"
    
    # تحقق من القسم (department_id) على أنه مطلوب عند الإضافة
    department_id_value = _normalize_int(form.get("department_id"))
    if not for_update and not department_id_value:
        errors["department_id"] = "يجب اختيار القسم"

    branch_id_value = _normalize_int(form.get("branch_id"))
    branch_section_id_value = _normalize_int(form.get("branch_section_id"))
    if not for_update and not branch_id_value:
        errors["branch_id"] = "يجب اختيار الفرع"
    if branch_section_id_value and not branch_id_value:
        errors["branch_section_id"] = "يجب اختيار الفرع قبل تحديد القسم"

    data = {
        "employee_number": employee_number or None,
        "first_name": first_name,
        "middle_name": _normalize_str(form.get("middle_name")) or None,
        "last_name": last_name,
        "arabic_name": _normalize_str(form.get("arabic_name")) or None,
        "date_of_birth": date_of_birth,
        "gender": _normalize_str(form.get("gender")) or None,
        "nationality": _normalize_str(form.get("nationality")) or None,
        "national_id": _normalize_str(form.get("national_id")) or None,
        "passport_number": _normalize_str(form.get("passport_number")) or None,
        "email": email or None,
        "phone": _normalize_str(form.get("phone")) or None,
        "mobile": _normalize_str(form.get("mobile")) or None,
        "address": _normalize_str(form.get("address")) or None,
        "city": _normalize_str(form.get("city")) or None,
        "country": _normalize_str(form.get("country")) or None,
        "emergency_contact_name": _normalize_str(form.get("emergency_contact_name")) or None,
        "emergency_contact_phone": _normalize_str(form.get("emergency_contact_phone")) or None,
        "emergency_contact_relation": _normalize_str(form.get("emergency_contact_relation")) or None,
        "department_id": department_id_value,
        "branch_id": branch_id_value,
        "branch_section_id": branch_section_id_value,
        "position": _normalize_str(form.get("position")) or None,
        "job_title": _normalize_str(form.get("job_title")) or None,
        "employment_type": _normalize_str(form.get("employment_type")) or None,
        "join_date": join_date,
        "contract_start_date": contract_start_date,
        "contract_end_date": contract_end_date,
        "status": status,
        "resignation_date": _parse_date(form.get("resignation_date")),
        "termination_date": _parse_date(form.get("termination_date")),
        "base_salary": base_salary,
        "currency": _normalize_str(form.get("currency")) or "OMR",
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors


def validate_attendance_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من سجل الحضور"""
    errors: Dict[str, str] = {}
    
    employee_id = _normalize_int(form.get("employee_id"))
    attendance_date = _parse_date(form.get("attendance_date"))
    
    if not employee_id:
        errors["employee_id"] = "يجب تحديد موظف"
    if not attendance_date:
        errors["attendance_date"] = "يجب تحديد تاريخ"
    
    check_in = _parse_datetime(form.get("check_in"))
    check_out = _parse_datetime(form.get("check_out"))
    
    if check_in and check_out and check_out < check_in:
        errors["check_out"] = "وقت الانصراف يجب أن يكون بعد وقت الحضور"
    
    status = _normalize_str(form.get("status")) or "حاضر"
    if status not in ATTENDANCE_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    data = {
        "employee_id": employee_id,
        "attendance_date": attendance_date,
        "check_in": check_in,
        "check_out": check_out,
        "status": status,
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors


def validate_payroll_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من كشف الراتب"""
    errors: Dict[str, str] = {}
    
    employee_id = _normalize_int(form.get("employee_id"))
    payroll_month = _normalize_int(form.get("payroll_month"))
    payroll_year = _normalize_int(form.get("payroll_year"))
    base_salary = _normalize_decimal(form.get("base_salary"))
    
    if not employee_id:
        errors["employee_id"] = "يجب تحديد موظف"
    if not payroll_month or payroll_month < 1 or payroll_month > 12:
        errors["payroll_month"] = "الشهر يجب أن يكون بين 1 و 12"
    if not payroll_year or payroll_year < 2000:
        errors["payroll_year"] = "السنة غير صالحة"
    if not base_salary or base_salary < 0:
        errors["base_salary"] = "الراتب الأساسي مطلوب ويجب أن يكون موجبًا"
    
    status = _normalize_str(form.get("status")) or "مسودة"
    if status not in PAYROLL_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    data = {
        "employee_id": employee_id,
        "payroll_month": payroll_month,
        "payroll_year": payroll_year,
        "base_salary": base_salary,
        "allowances_total": _normalize_decimal(form.get("allowances_total")) or Decimal(0),
        "bonuses_total": _normalize_decimal(form.get("bonuses_total")) or Decimal(0),
        "deductions_total": _normalize_decimal(form.get("deductions_total")) or Decimal(0),
        "tax_deductions": _normalize_decimal(form.get("tax_deductions")) or Decimal(0),
        "insurance_deductions": _normalize_decimal(form.get("insurance_deductions")) or Decimal(0),
        "loan_deductions": _normalize_decimal(form.get("loan_deductions")) or Decimal(0),
        "other_deductions": _normalize_decimal(form.get("other_deductions")) or Decimal(0),
        "working_days": _normalize_int(form.get("working_days")) or 0,
        "present_days": _normalize_int(form.get("present_days")) or 0,
        "absent_days": _normalize_int(form.get("absent_days")) or 0,
        "leave_days": _normalize_int(form.get("leave_days")) or 0,
        "status": status,
        "payment_date": _parse_date(form.get("payment_date")),
        "payment_method": _normalize_str(form.get("payment_method")) or None,
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors


def validate_leave_request_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من طلب الإجازة"""
    errors: Dict[str, str] = {}
    
    employee_id = _normalize_int(form.get("employee_id"))
    leave_type_id = _normalize_int(form.get("leave_type_id"))
    start_date = _parse_date(form.get("start_date"))
    end_date = _parse_date(form.get("end_date"))
    
    if not employee_id:
        errors["employee_id"] = "يجب تحديد موظف"
    if not leave_type_id:
        errors["leave_type_id"] = "يجب تحديد نوع الإجازة"
    if not start_date:
        errors["start_date"] = "يجب تحديد تاريخ البداية"
    if not end_date:
        errors["end_date"] = "يجب تحديد تاريخ النهاية"
    
    if start_date and end_date and start_date > end_date:
        errors["end_date"] = "تاريخ النهاية يجب أن يكون بعد تاريخ البداية"
    
    status = _normalize_str(form.get("status")) or "معلق"
    if status not in LEAVE_REQUEST_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    data = {
        "employee_id": employee_id,
        "leave_type_id": leave_type_id,
        "start_date": start_date,
        "end_date": end_date,
        "reason": _normalize_str(form.get("reason")) or None,
        "status": status,
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors


def validate_performance_review_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من تقييم الأداء"""
    errors: Dict[str, str] = {}
    
    employee_id = _normalize_int(form.get("employee_id"))
    review_period = _normalize_str(form.get("review_period"))
    review_year = _normalize_int(form.get("review_year"))
    
    if not employee_id:
        errors["employee_id"] = "يجب تحديد موظف"
    if not review_period or review_period not in PERFORMANCE_PERIODS:
        errors["review_period"] = "يجب تحديد فترة التقييم"
    if not review_year:
        errors["review_year"] = "يجب تحديد السنة"
    
    status = _normalize_str(form.get("status")) or "مسودة"
    if status not in PERFORMANCE_REVIEW_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    # التحقق من النقاط (0-100)
    scores = ["overall_score", "communication_score", "teamwork_score", 
              "productivity_score", "quality_score", "leadership_score"]
    for score_name in scores:
        score = _normalize_decimal(form.get(score_name))
        if score is not None and (score < 0 or score > 100):
            errors[score_name] = "النقاط يجب أن تكون بين 0 و 100"
    
    data = {
        "employee_id": employee_id,
        "review_period": review_period,
        "review_year": review_year,
        "review_quarter": _normalize_int(form.get("review_quarter")),
        "review_month": _normalize_int(form.get("review_month")),
        "overall_score": _normalize_decimal(form.get("overall_score")),
        "communication_score": _normalize_decimal(form.get("communication_score")),
        "teamwork_score": _normalize_decimal(form.get("teamwork_score")),
        "productivity_score": _normalize_decimal(form.get("productivity_score")),
        "quality_score": _normalize_decimal(form.get("quality_score")),
        "leadership_score": _normalize_decimal(form.get("leadership_score")),
        "strengths": _normalize_str(form.get("strengths")) or None,
        "areas_for_improvement": _normalize_str(form.get("areas_for_improvement")) or None,
        "reviewer_comments": _normalize_str(form.get("reviewer_comments")) or None,
        "employee_comments": _normalize_str(form.get("employee_comments")) or None,
        "status": status,
    }
    
    return data, errors


def validate_employee_goal_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من هدف الموظف"""
    errors: Dict[str, str] = {}
    
    employee_id = _normalize_int(form.get("employee_id"))
    title = _normalize_str(form.get("title"))
    target_date = _parse_date(form.get("target_date"))
    
    if not employee_id:
        errors["employee_id"] = "يجب تحديد موظف"
    if not title:
        errors["title"] = "عنوان الهدف مطلوب"
    if not target_date:
        errors["target_date"] = "يجب تحديد تاريخ الهدف"
    
    priority = _normalize_str(form.get("priority")) or "متوسط"
    if priority not in GOAL_PRIORITIES:
        errors["priority"] = "أولوية غير صالحة"
    
    status = _normalize_str(form.get("status")) or "قيد التنفيذ"
    if status not in GOAL_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    data = {
        "employee_id": employee_id,
        "title": title,
        "description": _normalize_str(form.get("description")) or None,
        "goal_type": _normalize_str(form.get("goal_type")) or None,
        "start_date": _parse_date(form.get("start_date")),
        "target_date": target_date,
        "completion_date": _parse_date(form.get("completion_date")),
        "target_value": _normalize_decimal(form.get("target_value")),
        "current_value": _normalize_decimal(form.get("current_value")) or Decimal(0),
        "priority": priority,
        "status": status,
    }
    
    return data, errors


def validate_job_posting_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من وظيفة شاغرة"""
    errors: Dict[str, str] = {}
    
    title = _normalize_str(form.get("title"))
    posting_date = _parse_date(form.get("posting_date"))
    
    if not title:
        errors["title"] = "عنوان الوظيفة مطلوب"
    if not posting_date:
        errors["posting_date"] = "يجب تحديد تاريخ النشر"
    
    closing_date = _parse_date(form.get("closing_date"))
    if posting_date and closing_date and closing_date < posting_date:
        errors["closing_date"] = "تاريخ الإغلاق يجب أن يكون بعد تاريخ النشر"
    
    status = _normalize_str(form.get("status")) or "مفتوح"
    if status not in JOB_POSTING_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    salary_min = _normalize_decimal(form.get("salary_min"))
    salary_max = _normalize_decimal(form.get("salary_max"))
    if salary_min and salary_max and salary_min > salary_max:
        errors["salary_max"] = "الحد الأقصى للراتب يجب أن يكون أكبر من الحد الأدنى"
    
    data = {
        "title": title,
        "department_id": _normalize_int(form.get("department_id")),
        "position": _normalize_str(form.get("position")) or None,
        "description": _normalize_str(form.get("description")) or None,
        "requirements": _normalize_str(form.get("requirements")) or None,
        "responsibilities": _normalize_str(form.get("responsibilities")) or None,
        "employment_type": _normalize_str(form.get("employment_type")) or None,
        "experience_required": _normalize_int(form.get("experience_required")),
        "education_level": _normalize_str(form.get("education_level")) or None,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": _normalize_str(form.get("currency")) or "OMR",
        "posting_date": posting_date,
        "closing_date": closing_date,
        "status": status,
        "is_external": form.get("is_external") == "on" or form.get("is_external") == "true",
    }
    
    return data, errors


def validate_candidate_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من بيانات المرشح"""
    errors: Dict[str, str] = {}
    
    first_name = _normalize_str(form.get("first_name"))
    last_name = _normalize_str(form.get("last_name"))
    email = _normalize_str(form.get("email"))
    
    if not first_name:
        errors["first_name"] = "الاسم الأول مطلوب"
    if not last_name:
        errors["last_name"] = "اسم العائلة مطلوب"
    
    if email and "@" not in email:
        errors["email"] = "البريد الإلكتروني غير صالح"
    
    status = _normalize_str(form.get("status")) or "جديد"
    if status not in CANDIDATE_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    data = {
        "first_name": first_name,
        "middle_name": _normalize_str(form.get("middle_name")) or None,
        "last_name": last_name,
        "email": email or None,
        "phone": _normalize_str(form.get("phone")) or None,
        "mobile": _normalize_str(form.get("mobile")) or None,
        "nationality": _normalize_str(form.get("nationality")) or None,
        "date_of_birth": _parse_date(form.get("date_of_birth")),
        "education_level": _normalize_str(form.get("education_level")) or None,
        "years_of_experience": _normalize_int(form.get("years_of_experience")),
        "current_position": _normalize_str(form.get("current_position")) or None,
        "current_company": _normalize_str(form.get("current_company")) or None,
        "portfolio_url": _normalize_str(form.get("portfolio_url")) or None,
        "source": _normalize_str(form.get("source")) or None,
        "status": status,
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors


def validate_interview_form(form: Dict[str, str]) -> Tuple[Dict, Dict[str, str]]:
    """التحقق من بيانات المقابلة"""
    errors: Dict[str, str] = {}
    
    application_id = _normalize_int(form.get("application_id"))
    candidate_id = _normalize_int(form.get("candidate_id"))
    interview_date = _parse_datetime(form.get("interview_date"))
    
    if not application_id:
        errors["application_id"] = "يجب تحديد طلب التوظيف"
    if not candidate_id:
        errors["candidate_id"] = "يجب تحديد المرشح"
    if not interview_date:
        errors["interview_date"] = "يجب تحديد تاريخ ووقت المقابلة"
    
    status = _normalize_str(form.get("status")) or "مخطط"
    if status not in INTERVIEW_STATUSES:
        errors["status"] = "حالة غير صالحة"
    
    result = _normalize_str(form.get("result"))
    if result and result not in INTERVIEW_RESULTS:
        errors["result"] = "نتيجة غير صالحة"
    
    # التحقق من النقاط (0-100)
    scores = ["technical_score", "communication_score", "cultural_fit_score", "overall_score"]
    for score_name in scores:
        score = _normalize_decimal(form.get(score_name))
        if score is not None and (score < 0 or score > 100):
            errors[score_name] = "النقاط يجب أن تكون بين 0 و 100"
    
    data = {
        "application_id": application_id,
        "candidate_id": candidate_id,
        "interview_type": _normalize_str(form.get("interview_type")) or None,
        "interview_date": interview_date,
        "location": _normalize_str(form.get("location")) or None,
        "interviewers": _normalize_str(form.get("interviewers")) or None,
        "interviewer_ids": _normalize_str(form.get("interviewer_ids")) or None,
        "status": status,
        "result": result,
        "feedback": _normalize_str(form.get("feedback")) or None,
        "technical_score": _normalize_decimal(form.get("technical_score")),
        "communication_score": _normalize_decimal(form.get("communication_score")),
        "cultural_fit_score": _normalize_decimal(form.get("cultural_fit_score")),
        "overall_score": _normalize_decimal(form.get("overall_score")),
        "notes": _normalize_str(form.get("notes")) or None,
    }
    
    return data, errors
