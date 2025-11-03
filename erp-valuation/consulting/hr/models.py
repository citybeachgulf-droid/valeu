from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional
from decimal import Decimal

from extensions import db
from consulting.projects.models import ConsultingProject


# ==================== نماذج الموارد البشرية الشاملة ====================

class Engineer(db.Model):
    """نموذج المهندسين (للتوافق مع النظام القديم)"""
    __tablename__ = "consulting_engineer"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    specialty = db.Column(db.String(20), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    join_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="نشط", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Engineer {self.id} {self.name!r} {self.specialty!r} status={self.status}>"


class Task(db.Model):
    """نموذج المهام (للتوافق مع النظام القديم)"""
    __tablename__ = "consulting_task"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("consulting_project.id"), nullable=False, index=True)
    engineer_id = db.Column(db.Integer, db.ForeignKey("consulting_engineer.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="جديدة", index=True)
    deadline = db.Column(db.Date, nullable=True, index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship(ConsultingProject, backref=db.backref("tasks", lazy=True), foreign_keys=[project_id])
    engineer = db.relationship(Engineer, backref=db.backref("tasks", lazy=True), foreign_keys=[engineer_id])

    def __repr__(self) -> str:
        return f"<Task {self.id} eng={self.engineer_id} proj={self.project_id} status={self.status}>"

    def is_overdue(self) -> bool:
        if self.status == "مكتملة":
            return False
        if not self.deadline:
            return False
        return self.deadline < date.today()

    def days_remaining(self) -> Optional[int]:
        if not self.deadline:
            return None
        return (self.deadline - date.today()).days


# ==================== إدارة الموظفين (Employee Management) ====================

class Department(db.Model):
    """الأقسام"""
    __tablename__ = "hr_department"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    code = db.Column(db.String(20), nullable=True, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = db.relationship("Employee", foreign_keys=[manager_id], remote_side="Employee.id")
    employees = db.relationship("Employee", backref=db.backref("department", lazy=True), foreign_keys="Employee.department_id")

    def __repr__(self) -> str:
        return f"<Department {self.id} {self.name!r}>"


class Employee(db.Model):
    """الموظفين - بيانات شاملة"""
    __tablename__ = "hr_employee"

    id = db.Column(db.Integer, primary_key=True)
    employee_number = db.Column(db.String(50), unique=True, nullable=True, index=True)
    
    # البيانات الشخصية
    first_name = db.Column(db.String(100), nullable=False, index=True)
    middle_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=False, index=True)
    arabic_name = db.Column(db.String(200), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # ذكر / أنثى
    nationality = db.Column(db.String(50), nullable=True)
    national_id = db.Column(db.String(50), nullable=True, index=True)
    passport_number = db.Column(db.String(50), nullable=True, index=True)
    
    # معلومات الاتصال
    email = db.Column(db.String(120), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=True, index=True)
    mobile = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    
    # معلومات الطوارئ
    emergency_contact_name = db.Column(db.String(150), nullable=True)
    emergency_contact_phone = db.Column(db.String(50), nullable=True)
    emergency_contact_relation = db.Column(db.String(50), nullable=True)
    
    # بيانات الوظيفة
    department_id = db.Column(db.Integer, db.ForeignKey("hr_department.id"), nullable=True, index=True)
    position = db.Column(db.String(100), nullable=True, index=True)
    job_title = db.Column(db.String(150), nullable=True, index=True)
    employment_type = db.Column(db.String(50), nullable=True, index=True)  # دوام كامل / جزئي / عقد / مستقل
    join_date = db.Column(db.Date, nullable=True, index=True)
    contract_start_date = db.Column(db.Date, nullable=True)
    contract_end_date = db.Column(db.Date, nullable=True, index=True)
    
    # الحالة
    status = db.Column(db.String(20), nullable=False, default="نشط", index=True)  # نشط / إجازة / متوقف / مستقل
    resignation_date = db.Column(db.Date, nullable=True)
    termination_date = db.Column(db.Date, nullable=True)
    
    # الرواتب
    base_salary = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(10), default="SAR", nullable=True)
    
    # معلومات إضافية
    notes = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)
    updated_by = db.Column(db.Integer, nullable=True)

    # Relationships
    attendance_records = db.relationship("Attendance", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")
    payroll_records = db.relationship("Payroll", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")
    leave_requests = db.relationship("LeaveRequest", backref=db.backref("employee", lazy=True), foreign_keys="LeaveRequest.employee_id", cascade="all, delete-orphan")
    leave_balances = db.relationship("LeaveBalance", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")
    performance_reviews = db.relationship("PerformanceReview", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")
    employee_goals = db.relationship("EmployeeGoal", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")
    documents = db.relationship("EmployeeDocument", backref=db.backref("employee", lazy=True), cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        """الاسم الكامل"""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"<Employee {self.id} {self.full_name} ({self.employee_number})>"


# ==================== الحضور والرواتب (Attendance & Payroll) ====================

class Attendance(db.Model):
    """سجلات الحضور"""
    __tablename__ = "hr_attendance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    hours_worked = db.Column(db.Numeric(5, 2), nullable=True)  # عدد الساعات
    status = db.Column(db.String(20), nullable=False, default="حاضر", index=True)  # حاضر / غائب / إجازة / متأخر
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_hours(self) -> Optional[float]:
        """حساب ساعات العمل"""
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            return delta.total_seconds() / 3600.0
        return None

    def __repr__(self) -> str:
        return f"<Attendance {self.id} emp={self.employee_id} date={self.attendance_date}>"


class SalaryComponent(db.Model):
    """مكونات الراتب (بدلات، استقطاعات، إلخ)"""
    __tablename__ = "hr_salary_component"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    type = db.Column(db.String(20), nullable=False, index=True)  # allowance / deduction / bonus
    is_taxable = db.Column(db.Boolean, default=False)
    is_percentage = db.Column(db.Boolean, default=False)  # نسبة أم مبلغ ثابت
    default_value = db.Column(db.Numeric(12, 2), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SalaryComponent {self.id} {self.name} ({self.type})>"


class Payroll(db.Model):
    """كشوف الرواتب الشهرية"""
    __tablename__ = "hr_payroll"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    payroll_month = db.Column(db.Integer, nullable=False, index=True)  # 1-12
    payroll_year = db.Column(db.Integer, nullable=False, index=True)
    
    # الرواتب الأساسية
    base_salary = db.Column(db.Numeric(12, 2), nullable=False)
    
    # البدلات والإضافات
    allowances_total = db.Column(db.Numeric(12, 2), default=0)
    bonuses_total = db.Column(db.Numeric(12, 2), default=0)
    
    # الاستقطاعات
    deductions_total = db.Column(db.Numeric(12, 2), default=0)
    tax_deductions = db.Column(db.Numeric(12, 2), default=0)
    insurance_deductions = db.Column(db.Numeric(12, 2), default=0)
    loan_deductions = db.Column(db.Numeric(12, 2), default=0)
    other_deductions = db.Column(db.Numeric(12, 2), default=0)
    
    # الإجماليات
    gross_salary = db.Column(db.Numeric(12, 2), nullable=False)
    net_salary = db.Column(db.Numeric(12, 2), nullable=False)
    
    # معلومات إضافية
    working_days = db.Column(db.Integer, default=0)
    present_days = db.Column(db.Integer, default=0)
    absent_days = db.Column(db.Integer, default=0)
    leave_days = db.Column(db.Integer, default=0)
    
    # حالة الراتب
    status = db.Column(db.String(20), default="مسودة", index=True)  # مسودة / معتمد / مدفوع
    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)
    approved_by = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('employee_id', 'payroll_month', 'payroll_year', name='unique_payroll_period'),)

    def calculate_net(self):
        """حساب الراتب الصافي"""
        self.gross_salary = self.base_salary + self.allowances_total + self.bonuses_total
        self.net_salary = self.gross_salary - self.deductions_total

    def __repr__(self) -> str:
        return f"<Payroll {self.id} emp={self.employee_id} {self.payroll_year}/{self.payroll_month}>"


class PayrollDetail(db.Model):
    """تفاصيل مكونات الراتب"""
    __tablename__ = "hr_payroll_detail"

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.Integer, db.ForeignKey("hr_payroll.id"), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey("hr_salary_component.id"), nullable=True)
    component_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # allowance / deduction / bonus
    notes = db.Column(db.Text, nullable=True)

    payroll = db.relationship("Payroll", backref=db.backref("details", lazy=True, cascade="all, delete-orphan"))
    component = db.relationship("SalaryComponent", backref=db.backref("payroll_details", lazy=True))

    def __repr__(self) -> str:
        return f"<PayrollDetail {self.id} payroll={self.payroll_id} {self.component_name}={self.amount}>"


# ==================== الإجازات والغياب (Leaves & Absences) ====================

class LeaveType(db.Model):
    """أنواع الإجازات"""
    __tablename__ = "hr_leave_type"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    name_ar = db.Column(db.String(100), nullable=True)
    code = db.Column(db.String(20), nullable=True, unique=True)
    max_days = db.Column(db.Integer, nullable=True)  # الحد الأقصى للأيام
    is_paid = db.Column(db.Boolean, default=True)
    requires_approval = db.Column(db.Boolean, default=True)
    carry_forward = db.Column(db.Boolean, default=False)  # هل يمكن تحويل الرصيد
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LeaveType {self.id} {self.name}>"


class LeaveBalance(db.Model):
    """رصيد الإجازات لكل موظف"""
    __tablename__ = "hr_leave_balance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("hr_leave_type.id"), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    
    initial_balance = db.Column(db.Numeric(6, 2), default=0)  # الرصيد الابتدائي
    used_balance = db.Column(db.Numeric(6, 2), default=0)  # المستخدم
    remaining_balance = db.Column(db.Numeric(6, 2), default=0)  # المتبقي
    carry_forward = db.Column(db.Numeric(6, 2), default=0)  # المحول من السنة السابقة
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leave_type = db.relationship("LeaveType", backref=db.backref("balances", lazy=True))

    __table_args__ = (db.UniqueConstraint('employee_id', 'leave_type_id', 'year', name='unique_leave_balance'),)

    def update_balance(self):
        """تحديث الرصيد المتبقي"""
        self.remaining_balance = self.initial_balance + self.carry_forward - self.used_balance

    def __repr__(self) -> str:
        return f"<LeaveBalance {self.id} emp={self.employee_id} type={self.leave_type_id} year={self.year}>"


class LeaveRequest(db.Model):
    """طلبات الإجازات"""
    __tablename__ = "hr_leave_request"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("hr_leave_type.id"), nullable=False, index=True)
    
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    total_days = db.Column(db.Numeric(6, 2), nullable=False)
    
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="معلق", index=True)  # معلق / معتمد / مرفوض / ملغي
    approval_status = db.Column(db.String(20), nullable=True)  # في انتظار / معتمد / مرفوض
    
    # الموافقات
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_by = db.Column(db.Integer, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    # معلومات إضافية
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leave_type = db.relationship("LeaveType", backref=db.backref("requests", lazy=True))

    def calculate_days(self):
        """حساب عدد أيام الإجازة"""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.total_days = Decimal(delta.days + 1)  # +1 لتضمين اليوم الأول

    def __repr__(self) -> str:
        return f"<LeaveRequest {self.id} emp={self.employee_id} {self.start_date} to {self.end_date}>"


# ==================== التقييم والتطوير (Performance & Development) ====================

class PerformanceReview(db.Model):
    """تقييمات الأداء"""
    __tablename__ = "hr_performance_review"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    
    review_period = db.Column(db.String(20), nullable=False, index=True)  # سنوي / ربع سنوي / شهري
    review_year = db.Column(db.Integer, nullable=False, index=True)
    review_quarter = db.Column(db.Integer, nullable=True)  # 1-4
    review_month = db.Column(db.Integer, nullable=True)  # 1-12
    
    # التقييم
    overall_score = db.Column(db.Numeric(5, 2), nullable=True)  # من 100
    communication_score = db.Column(db.Numeric(5, 2), nullable=True)
    teamwork_score = db.Column(db.Numeric(5, 2), nullable=True)
    productivity_score = db.Column(db.Numeric(5, 2), nullable=True)
    quality_score = db.Column(db.Numeric(5, 2), nullable=True)
    leadership_score = db.Column(db.Numeric(5, 2), nullable=True)
    
    # التعليقات
    strengths = db.Column(db.Text, nullable=True)
    areas_for_improvement = db.Column(db.Text, nullable=True)
    reviewer_comments = db.Column(db.Text, nullable=True)
    employee_comments = db.Column(db.Text, nullable=True)
    
    # الحالة
    status = db.Column(db.String(20), default="مسودة", index=True)  # مسودة / منتهي / معتمد
    
    reviewed_by = db.Column(db.Integer, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PerformanceReview {self.id} emp={self.employee_id} {self.review_period} {self.review_year}>"


class EmployeeGoal(db.Model):
    """أهداف الموظفين"""
    __tablename__ = "hr_employee_goal"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    goal_type = db.Column(db.String(50), nullable=True)  # فردي / جماعي / شركة
    
    start_date = db.Column(db.Date, nullable=True)
    target_date = db.Column(db.Date, nullable=False, index=True)
    completion_date = db.Column(db.Date, nullable=True)
    
    target_value = db.Column(db.Numeric(12, 2), nullable=True)
    current_value = db.Column(db.Numeric(12, 2), default=0)
    progress_percentage = db.Column(db.Integer, default=0)
    
    status = db.Column(db.String(20), default="قيد التنفيذ", index=True)  # قيد التنفيذ / مكتمل / ملغي
    priority = db.Column(db.String(20), default="متوسط")  # عالي / متوسط / منخفض
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)

    def update_progress(self):
        """تحديث نسبة الإنجاز"""
        if self.target_value and self.target_value > 0:
            self.progress_percentage = int((self.current_value / self.target_value) * 100)
        if self.completion_date or self.progress_percentage >= 100:
            self.status = "مكتمل"

    def __repr__(self) -> str:
        return f"<EmployeeGoal {self.id} emp={self.employee_id} {self.title}>"


class TrainingProgram(db.Model):
    """برامج التدريب والتطوير"""
    __tablename__ = "hr_training_program"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    training_type = db.Column(db.String(50), nullable=True)  # داخلي / خارجي / أونلاين
    provider = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    duration_hours = db.Column(db.Integer, nullable=True)
    cost = db.Column(db.Numeric(12, 2), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    
    status = db.Column(db.String(20), default="مخطط", index=True)  # مخطط / قيد التنفيذ / منتهي / ملغي
    max_participants = db.Column(db.Integer, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)

    participants = db.relationship("TrainingParticipant", backref=db.backref("program", lazy=True), cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TrainingProgram {self.id} {self.name}>"


class TrainingParticipant(db.Model):
    """مشاركون في برامج التدريب"""
    __tablename__ = "hr_training_participant"

    id = db.Column(db.Integer, primary_key=True)
    training_program_id = db.Column(db.Integer, db.ForeignKey("hr_training_program.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    
    status = db.Column(db.String(20), default="مسجل", index=True)  # مسجل / حضر / لم يحضر / ألغى
    attendance_percentage = db.Column(db.Numeric(5, 2), nullable=True)
    completion_certificate = db.Column(db.String(255), nullable=True)
    evaluation_score = db.Column(db.Numeric(5, 2), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", backref=db.backref("training_participations", lazy=True))

    __table_args__ = (db.UniqueConstraint('training_program_id', 'employee_id', name='unique_training_participant'),)

    def __repr__(self) -> str:
        return f"<TrainingParticipant {self.id} program={self.training_program_id} emp={self.employee_id}>"


# ==================== التوظيف (Recruitment) ====================

class JobPosting(db.Model):
    """الوظائف الشاغرة"""
    __tablename__ = "hr_job_posting"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("hr_department.id"), nullable=True, index=True)
    position = db.Column(db.String(100), nullable=True)
    
    description = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=True)
    responsibilities = db.Column(db.Text, nullable=True)
    
    employment_type = db.Column(db.String(50), nullable=True)  # دوام كامل / جزئي / عقد
    experience_required = db.Column(db.Integer, nullable=True)  # سنوات
    education_level = db.Column(db.String(100), nullable=True)
    
    salary_min = db.Column(db.Numeric(12, 2), nullable=True)
    salary_max = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(10), default="SAR")
    
    posting_date = db.Column(db.Date, nullable=False, index=True)
    closing_date = db.Column(db.Date, nullable=True, index=True)
    
    status = db.Column(db.String(20), default="مفتوح", index=True)  # مفتوح / مغلق / ملغي
    is_external = db.Column(db.Boolean, default=True)  # هل متاح للموظفين الحاليين
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, nullable=True)

    department = db.relationship("Department", backref=db.backref("job_postings", lazy=True))
    applications = db.relationship("JobApplication", backref=db.backref("job_posting", lazy=True), cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<JobPosting {self.id} {self.title}>"


class Candidate(db.Model):
    """المرشحون"""
    __tablename__ = "hr_candidate"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=False)
    
    email = db.Column(db.String(120), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=True, index=True)
    mobile = db.Column(db.String(50), nullable=True)
    
    nationality = db.Column(db.String(50), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    
    education_level = db.Column(db.String(100), nullable=True)
    years_of_experience = db.Column(db.Integer, nullable=True)
    current_position = db.Column(db.String(150), nullable=True)
    current_company = db.Column(db.String(200), nullable=True)
    
    resume_path = db.Column(db.String(255), nullable=True)
    cover_letter_path = db.Column(db.String(255), nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)
    
    source = db.Column(db.String(100), nullable=True)  # موقع التوظيف / إحالة / إعلان
    
    status = db.Column(db.String(20), default="جديد", index=True)  # جديد / قيد المراجعة / مختار / مرفوض / غير مناسب
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = db.relationship("JobApplication", backref=db.backref("candidate", lazy=True), cascade="all, delete-orphan")
    interviews = db.relationship("Interview", backref=db.backref("candidate", lazy=True), cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"<Candidate {self.id} {self.full_name}>"


class JobApplication(db.Model):
    """طلبات التوظيف"""
    __tablename__ = "hr_job_application"

    id = db.Column(db.Integer, primary_key=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("hr_job_posting.id"), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("hr_candidate.id"), nullable=False, index=True)
    
    application_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(20), default="مستلم", index=True)  # مستلم / قيد المراجعة / مختار / مرفوض / سحب
    
    cover_letter = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    reviewed_by = db.Column(db.Integer, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    interviews = db.relationship("Interview", backref=db.backref("application", lazy=True), cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint('job_posting_id', 'candidate_id', name='unique_job_application'),)

    def __repr__(self) -> str:
        return f"<JobApplication {self.id} job={self.job_posting_id} candidate={self.candidate_id}>"


class Interview(db.Model):
    """المقابلات"""
    __tablename__ = "hr_interview"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("hr_job_application.id"), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("hr_candidate.id"), nullable=False, index=True)
    
    interview_type = db.Column(db.String(50), nullable=True)  # هاتفي / وجهاً لوجه / أونلاين
    interview_date = db.Column(db.DateTime, nullable=False, index=True)
    location = db.Column(db.String(200), nullable=True)
    
    interviewers = db.Column(db.String(500), nullable=True)  # قائمة أسماء المقابلين
    interviewer_ids = db.Column(db.String(200), nullable=True)  # قائمة IDs
    
    status = db.Column(db.String(20), default="مخطط", index=True)  # مخطط / تم / ملغي
    result = db.Column(db.String(20), nullable=True)  # نجح / فشل / معلق
    
    feedback = db.Column(db.Text, nullable=True)
    technical_score = db.Column(db.Numeric(5, 2), nullable=True)
    communication_score = db.Column(db.Numeric(5, 2), nullable=True)
    cultural_fit_score = db.Column(db.Numeric(5, 2), nullable=True)
    overall_score = db.Column(db.Numeric(5, 2), nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Interview {self.id} candidate={self.candidate_id} date={self.interview_date}>"


# ==================== المستندات والامتثال (Documents & Compliance) ====================

class EmployeeDocument(db.Model):
    """مستندات الموظفين"""
    __tablename__ = "hr_employee_document"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    
    document_type = db.Column(db.String(100), nullable=False, index=True)  # عقد / شهادة / هوية / رخصة
    document_name = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    
    description = db.Column(db.Text, nullable=True)
    is_confidential = db.Column(db.Boolean, default=False)
    
    uploaded_by = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_expired(self) -> bool:
        """التحقق من انتهاء صلاحية المستند"""
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False

    def days_until_expiry(self) -> Optional[int]:
        """عدد الأيام حتى انتهاء الصلاحية"""
        if self.expiry_date:
            delta = self.expiry_date - date.today()
            return delta.days
        return None

    def __repr__(self) -> str:
        return f"<EmployeeDocument {self.id} emp={self.employee_id} {self.document_name}>"


class DocumentAlert(db.Model):
    """تنبيهات انتهاء المستندات"""
    __tablename__ = "hr_document_alert"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("hr_employee_document.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("hr_employee.id"), nullable=False, index=True)
    
    alert_type = db.Column(db.String(20), nullable=False)  # تحذير / انتهاء
    days_before_expiry = db.Column(db.Integer, nullable=True)
    expiry_date = db.Column(db.Date, nullable=False)
    
    status = db.Column(db.String(20), default="نشط", index=True)  # نشط / معالج / ملغي
    notified_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship("EmployeeDocument", backref=db.backref("alerts", lazy=True))
    employee = db.relationship("Employee", backref=db.backref("document_alerts", lazy=True))

    def __repr__(self) -> str:
        return f"<DocumentAlert {self.id} doc={self.document_id} type={self.alert_type}>"
