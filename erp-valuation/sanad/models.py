"""
Sanad System Database Models
Government services operations management
"""
from datetime import datetime, timedelta
from extensions import db
from sqlalchemy import func


# ==================== Organizations & Branches ====================

class Organization(db.Model):
    """Multi-tenant organization support"""
    __tablename__ = "sanad_organization"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    vat_number = db.Column(db.String(50), nullable=True)
    commercial_registration = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    branches = db.relationship("SanadBranch", back_populates="organization", lazy=True)
    services = db.relationship("GovService", back_populates="organization", lazy=True)


class SanadBranch(db.Model):
    """Branches for Sanad offices"""
    __tablename__ = "sanad_branch"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    name_ar = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = db.relationship("Organization", back_populates="branches")
    cash_sessions = db.relationship("CashSession", back_populates="branch", lazy=True)
    tickets = db.relationship("SanadTicket", back_populates="branch", lazy=True)


# ==================== Customers ====================

class SanadCustomer(db.Model):
    """Customer/Client management"""
    __tablename__ = "sanad_customer"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    
    # Personal Info
    full_name = db.Column(db.String(200), nullable=False)
    full_name_ar = db.Column(db.String(200), nullable=True)
    national_id = db.Column(db.String(50), nullable=True, index=True)  # Civil ID or Residence ID
    id_type = db.Column(db.String(20), nullable=True)  # 'civil_id', 'residence', 'passport'
    phone = db.Column(db.String(50), nullable=False, index=True)
    phone_verified = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(100), nullable=True)
    
    # Additional Info
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tickets = db.relationship("SanadTicket", back_populates="customer", lazy=True)
    invoices = db.relationship("SanadInvoice", back_populates="customer", lazy=True)


# ==================== Services ====================

class GovEntity(db.Model):
    """Government entities (وزارات وجهات حكومية)"""
    __tablename__ = "gov_entity"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    name_ar = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=True, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    services = db.relationship("GovService", back_populates="gov_entity", lazy=True)


class GovService(db.Model):
    """Service catalog (خدمات حكومية)"""
    __tablename__ = "gov_service"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    gov_entity_id = db.Column(db.Integer, db.ForeignKey("gov_entity.id"), nullable=True, index=True)
    
    # Service Info
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Pricing
    base_office_fee = db.Column(db.Float, default=0.0, nullable=False)  # أتعاب المكتب
    gov_fee_type = db.Column(db.String(20), default='fixed', nullable=False)  # 'fixed' or 'variable'
    gov_fee_value = db.Column(db.Float, default=0.0, nullable=False)  # الرسوم الحكومية
    vat_applicable = db.Column(db.Boolean, default=True, nullable=False)  # هل تطبق الضريبة على أتعاب المكتب
    
    # Requirements
    required_fields = db.Column(db.JSON, nullable=True)  # حقول مطلوبة
    required_docs = db.Column(db.JSON, nullable=True)  # مستندات مطلوبة
    
    # SLA
    sla_minutes = db.Column(db.Integer, default=1440, nullable=True)  # وقت التنفيذ المتوقع (بالدقائق)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = db.relationship("Organization", back_populates="services")
    gov_entity = db.relationship("GovEntity", back_populates="services")
    ticket_items = db.relationship("TicketItem", back_populates="service", lazy=True)


# ==================== Tickets/Transactions ====================

class SanadTicket(db.Model):
    """Ticket/Transaction for government service"""
    __tablename__ = "sanad_ticket"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("sanad_branch.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("sanad_customer.id"), nullable=False, index=True)
    
    # Ticket Info
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)  # رقم المعاملة
    status = db.Column(db.String(30), default='new', nullable=False, index=True)
    # Statuses: new, pending_docs, priced, paid, submitted, in_progress, completed, rejected, refunded, canceled
    
    # Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Gov Reference
    gov_reference_number = db.Column(db.String(100), nullable=True)  # رقم مرجعي حكومي
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    branch = db.relationship("SanadBranch", back_populates="tickets")
    customer = db.relationship("SanadCustomer", back_populates="tickets")
    items = db.relationship("TicketItem", back_populates="ticket", lazy=True, cascade="all, delete-orphan")
    logs = db.relationship("TicketLog", back_populates="ticket", lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship("TicketAttachment", back_populates="ticket", lazy=True, cascade="all, delete-orphan")
    invoice = db.relationship("SanadInvoice", back_populates="ticket", uselist=False)


class TicketItem(db.Model):
    """Service items in a ticket"""
    __tablename__ = "ticket_item"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("sanad_ticket.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("gov_service.id"), nullable=False, index=True)
    
    qty = db.Column(db.Integer, default=1, nullable=False)
    office_fee = db.Column(db.Float, default=0.0, nullable=False)
    gov_fee = db.Column(db.Float, default=0.0, nullable=False)
    vat_amount = db.Column(db.Float, default=0.0, nullable=False)  # VAT on office fee only
    line_total = db.Column(db.Float, default=0.0, nullable=False)
    
    # Variable fee calculation params
    calculation_params = db.Column(db.JSON, nullable=True)  # Parameters used for variable gov fees
    
    # Relationships
    ticket = db.relationship("SanadTicket", back_populates="items")
    service = db.relationship("GovService", back_populates="ticket_items")


class TicketLog(db.Model):
    """Audit log for ticket actions"""
    __tablename__ = "ticket_log"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("sanad_ticket.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    action = db.Column(db.String(100), nullable=False)  # created, status_changed, assigned, etc.
    notes = db.Column(db.Text, nullable=True)
    metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    ticket = db.relationship("SanadTicket", back_populates="logs")


class TicketAttachment(db.Model):
    """File attachments for tickets"""
    __tablename__ = "ticket_attachment"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("sanad_ticket.id"), nullable=False, index=True)
    
    file_name = db.Column(db.String(255), nullable=False)
    file_key = db.Column(db.String(255), nullable=False)  # Storage key
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    ticket = db.relationship("SanadTicket", back_populates="attachments")


# ==================== Invoices & Payments ====================

class SanadInvoice(db.Model):
    """Invoice with VAT calculation"""
    __tablename__ = "sanad_invoice"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("sanad_branch.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("sanad_customer.id"), nullable=False, index=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("sanad_ticket.id"), nullable=True, index=True)
    
    # Invoice Info
    invoice_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    
    # Amounts
    subtotal_office_fee = db.Column(db.Float, default=0.0, nullable=False)  # مجموع أتعاب المكتب
    total_gov_fees = db.Column(db.Float, default=0.0, nullable=False)  # مجموع الرسوم الحكومية
    vat_amount = db.Column(db.Float, default=0.0, nullable=False)  # ضريبة 5% على أتعاب المكتب فقط
    grand_total = db.Column(db.Float, default=0.0, nullable=False)  # الإجمالي النهائي
    
    # Status
    status = db.Column(db.String(20), default='draft', nullable=False)  # draft, issued, paid, canceled
    
    # Dates
    issue_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = db.relationship("SanadCustomer", back_populates="invoices")
    ticket = db.relationship("SanadTicket", back_populates="invoice")
    items = db.relationship("InvoiceItem", back_populates="invoice", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("SanadPayment", back_populates="invoice", lazy=True)


class InvoiceItem(db.Model):
    """Invoice line items"""
    __tablename__ = "invoice_item"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("sanad_invoice.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("gov_service.id"), nullable=True, index=True)
    
    description = db.Column(db.String(255), nullable=False)
    qty = db.Column(db.Integer, default=1, nullable=False)
    office_fee = db.Column(db.Float, default=0.0, nullable=False)
    gov_fee = db.Column(db.Float, default=0.0, nullable=False)
    vat_amount = db.Column(db.Float, default=0.0, nullable=False)
    line_total = db.Column(db.Float, default=0.0, nullable=False)
    
    # Relationships
    invoice = db.relationship("SanadInvoice", back_populates="items")


class SanadPayment(db.Model):
    """Payment records"""
    __tablename__ = "sanad_payment"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("sanad_branch.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("sanad_invoice.id"), nullable=False, index=True)
    
    method = db.Column(db.String(20), nullable=False)  # cash, card, transfer, qr
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100), nullable=True)  # Reference number for card/transfer
    
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    invoice = db.relationship("SanadInvoice", back_populates="payments")


class CashSession(db.Model):
    """Cash register session (day close)"""
    __tablename__ = "cash_session"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("sanad_branch.id"), nullable=False, index=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    opened_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    opening_balance = db.Column(db.Float, default=0.0, nullable=False)
    closing_balance = db.Column(db.Float, nullable=True)
    expected_balance = db.Column(db.Float, nullable=True)  # Calculated from transactions
    variance = db.Column(db.Float, default=0.0)  # Difference between expected and actual
    
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    branch = db.relationship("SanadBranch", back_populates="cash_sessions")


class Receipt(db.Model):
    """Receipt (قبض) or Disbursement (صرف) voucher"""
    __tablename__ = "sanad_receipt"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    
    receipt_type = db.Column(db.String(20), nullable=False)  # 'receipt' (قبض) or 'disbursement' (صرف)
    cash_session_id = db.Column(db.Integer, db.ForeignKey("cash_session.id"), nullable=True, index=True)
    
    ref_no = db.Column(db.String(50), nullable=False, unique=True)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ==================== Government Adapters ====================

class GovAdapter(db.Model):
    """Government integration adapters configuration"""
    __tablename__ = "gov_adapter"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    adapter_type = db.Column(db.String(50), nullable=False)  # labor, commerce, rop, municipality, etc.
    config = db.Column(db.JSON, nullable=True)  # Connection config, credentials, endpoints
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==================== Notifications ====================

class Notification(db.Model):
    """Notification queue"""
    __tablename__ = "sanad_notification"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    
    channel = db.Column(db.String(20), nullable=False)  # sms, whatsapp, email
    to = db.Column(db.String(100), nullable=False)
    template_key = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.JSON, nullable=True)  # Template variables
    
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, failed
    sent_at = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class NotificationTemplate(db.Model):
    """Notification templates"""
    __tablename__ = "notification_template"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    
    key = db.Column(db.String(100), nullable=False, index=True)
    channel = db.Column(db.String(20), nullable=False)  # sms, whatsapp, email
    subject = db.Column(db.String(200), nullable=True)  # For email
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON, nullable=True)  # List of expected variables
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== Audit Logs ====================

class AuditLog(db.Model):
    """Comprehensive audit log"""
    __tablename__ = "sanad_audit_log"
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("sanad_organization.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    entity = db.Column(db.String(100), nullable=False, index=True)  # Table name
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, view
    
    diff = db.Column(db.JSON, nullable=True)  # Changes made (old vs new values)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
