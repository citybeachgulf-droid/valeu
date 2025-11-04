"""
Sanad Routes - Government Services Operations
Flask blueprints for the Sanad module
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from sanad.models import (
    Organization, SanadBranch, SanadCustomer, GovEntity, GovService,
    SanadTicket, TicketItem, SanadInvoice, SanadPayment
)
from sanad.services import PricingService, TicketService, InvoiceService
from sanad.adapters import AdapterFactory
from datetime import datetime, timedelta
from sqlalchemy import func, or_


sanad_bp = Blueprint('sanad', __name__, url_prefix='/sanad')


# ==================== Helper Functions ====================

def require_sanad_role():
    """Check if user has access to Sanad module"""
    if 'user_id' not in session:
        return False
    role = session.get('role')
    return role in ['manager', 'employee', 'cashier', 'agent']


def get_current_org():
    """Get current organization (for single-tenant, return first org)"""
    return Organization.query.first()


# ==================== Dashboard ====================

@sanad_bp.route('/dashboard')
def dashboard():
    """Main Sanad dashboard"""
    if not require_sanad_role():
        flash('غير مصرح بالدخول', 'danger')
        return redirect(url_for('login'))
    
    org = get_current_org()
    if not org:
        flash('لا توجد مؤسسة مفعّلة', 'warning')
        return render_template('sanad/setup_required.html')
    
    # Statistics
    today = datetime.utcnow().date()
    
    stats = {
        'tickets_today': SanadTicket.query.filter(
            func.date(SanadTicket.created_at) == today
        ).count(),
        'tickets_pending': SanadTicket.query.filter(
            SanadTicket.status.in_(['new', 'pending_docs', 'priced'])
        ).count(),
        'tickets_in_progress': SanadTicket.query.filter(
            SanadTicket.status.in_(['paid', 'submitted', 'in_progress'])
        ).count(),
        'revenue_today': db.session.query(func.sum(SanadPayment.amount)).filter(
            func.date(SanadPayment.created_at) == today
        ).scalar() or 0.0
    }
    
    # Recent tickets
    recent_tickets = SanadTicket.query.order_by(
        SanadTicket.created_at.desc()
    ).limit(10).all()
    
    return render_template('sanad/dashboard.html', 
                         org=org, stats=stats, recent_tickets=recent_tickets)


# ==================== Services Management ====================

@sanad_bp.route('/services')
def services_list():
    """List all services"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    services = GovService.query.filter_by(org_id=org.id, is_active=True).all()
    entities = GovEntity.query.filter_by(is_active=True).all()
    
    return render_template('sanad/services_list.html', 
                         services=services, entities=entities, org=org)


@sanad_bp.route('/services/new', methods=['GET', 'POST'])
def service_new():
    """Create new service"""
    if session.get('role') != 'manager':
        flash('غير مصرح', 'danger')
        return redirect(url_for('sanad.services_list'))
    
    org = get_current_org()
    entities = GovEntity.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        service = GovService(
            org_id=org.id,
            gov_entity_id=request.form.get('gov_entity_id') or None,
            name=request.form['name'],
            name_ar=request.form['name_ar'],
            code=request.form.get('code'),
            description=request.form.get('description'),
            base_office_fee=float(request.form.get('base_office_fee', 0)),
            gov_fee_type=request.form.get('gov_fee_type', 'fixed'),
            gov_fee_value=float(request.form.get('gov_fee_value', 0)),
            vat_applicable=request.form.get('vat_applicable') == 'on',
            sla_minutes=int(request.form.get('sla_minutes', 1440))
        )
        db.session.add(service)
        db.session.commit()
        
        flash('تم إضافة الخدمة بنجاح', 'success')
        return redirect(url_for('sanad.services_list'))
    
    return render_template('sanad/service_form.html', entities=entities, org=org)


# ==================== Customers Management ====================

@sanad_bp.route('/customers')
def customers_list():
    """List customers"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    search = request.args.get('q', '').strip()
    
    query = SanadCustomer.query.filter_by(org_id=org.id)
    if search:
        query = query.filter(
            or_(
                SanadCustomer.full_name.ilike(f'%{search}%'),
                SanadCustomer.phone.ilike(f'%{search}%'),
                SanadCustomer.national_id.ilike(f'%{search}%')
            )
        )
    
    customers = query.order_by(SanadCustomer.created_at.desc()).all()
    
    return render_template('sanad/customers_list.html', 
                         customers=customers, org=org, search=search)


@sanad_bp.route('/customers/new', methods=['GET', 'POST'])
def customer_new():
    """Create new customer"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    
    if request.method == 'POST':
        customer = SanadCustomer(
            org_id=org.id,
            full_name=request.form['full_name'],
            full_name_ar=request.form.get('full_name_ar') or request.form['full_name'],
            national_id=request.form.get('national_id'),
            id_type=request.form.get('id_type'),
            phone=request.form['phone'],
            email=request.form.get('email'),
            notes=request.form.get('notes')
        )
        db.session.add(customer)
        db.session.commit()
        
        flash('تم إضافة العميل بنجاح', 'success')
        return redirect(url_for('sanad.customers_list'))
    
    return render_template('sanad/customer_form.html', org=org)


# ==================== Tickets/Transactions ====================

@sanad_bp.route('/tickets')
def tickets_list():
    """List tickets"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    status_filter = request.args.get('status', '').strip()
    
    query = SanadTicket.query.filter_by(org_id=org.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    tickets = query.order_by(SanadTicket.created_at.desc()).limit(50).all()
    
    return render_template('sanad/tickets_list.html', 
                         tickets=tickets, org=org, status_filter=status_filter)


@sanad_bp.route('/tickets/new', methods=['GET', 'POST'])
def ticket_new():
    """Create new ticket"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    customers = SanadCustomer.query.filter_by(org_id=org.id).order_by(SanadCustomer.full_name).all()
    services = GovService.query.filter_by(org_id=org.id, is_active=True).all()
    branches = SanadBranch.query.filter_by(org_id=org.id, is_active=True).all()
    
    if request.method == 'POST':
        customer_id = int(request.form['customer_id'])
        branch_id = int(request.form['branch_id'])
        
        # Parse service items
        service_items = []
        service_ids = request.form.getlist('service_id[]')
        quantities = request.form.getlist('qty[]')
        
        for sid, qty in zip(service_ids, quantities):
            if sid:
                service_items.append({
                    'service_id': int(sid),
                    'qty': int(qty) if qty else 1
                })
        
        if not service_items:
            flash('يجب اختيار خدمة واحدة على الأقل', 'warning')
            return redirect(url_for('sanad.ticket_new'))
        
        # Create ticket
        ticket = TicketService.create_ticket(
            org_id=org.id,
            branch_id=branch_id,
            customer_id=customer_id,
            created_by=session['user_id'],
            service_items=service_items
        )
        
        flash(f'تم إنشاء المعاملة {ticket.code} بنجاح', 'success')
        return redirect(url_for('sanad.ticket_detail', ticket_id=ticket.id))
    
    return render_template('sanad/ticket_form.html', 
                         org=org, customers=customers, services=services, branches=branches)


@sanad_bp.route('/tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    """Ticket details"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    ticket = SanadTicket.query.get_or_404(ticket_id)
    
    return render_template('sanad/ticket_detail.html', ticket=ticket)


# ==================== POS / Invoicing ====================

@sanad_bp.route('/pos')
def pos():
    """Point of Sale interface"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    org = get_current_org()
    customers = SanadCustomer.query.filter_by(org_id=org.id).order_by(SanadCustomer.full_name).all()
    services = GovService.query.filter_by(org_id=org.id, is_active=True).all()
    branches = SanadBranch.query.filter_by(org_id=org.id, is_active=True).all()
    
    return render_template('sanad/pos.html', 
                         org=org, customers=customers, services=services, branches=branches)


@sanad_bp.route('/invoices/<int:invoice_id>')
def invoice_detail(invoice_id):
    """Invoice details"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    invoice = SanadInvoice.query.get_or_404(invoice_id)
    
    return render_template('sanad/invoice_detail.html', invoice=invoice)


@sanad_bp.route('/invoices/<int:invoice_id>/pay', methods=['POST'])
def invoice_pay(invoice_id):
    """Record payment for invoice"""
    if not require_sanad_role():
        return redirect(url_for('login'))
    
    invoice = SanadInvoice.query.get_or_404(invoice_id)
    
    amount = float(request.form['amount'])
    method = request.form['method']
    reference = request.form.get('reference', '').strip()
    
    InvoiceService.record_payment(
        invoice=invoice,
        amount=amount,
        method=method,
        created_by=session['user_id'],
        reference=reference or None
    )
    
    flash(f'تم تسجيل الدفع: {amount} ريال عماني', 'success')
    return redirect(url_for('sanad.invoice_detail', invoice_id=invoice.id))


# ==================== API Endpoints ====================

@sanad_bp.route('/api/services/<int:service_id>/price', methods=['POST'])
def api_service_price(service_id):
    """Calculate price for a service"""
    if not require_sanad_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    service = GovService.query.get_or_404(service_id)
    data = request.get_json() or {}
    
    qty = data.get('qty', 1)
    calc_params = data.get('calc_params')
    
    pricing = PricingService.calculate_line_item(service, qty, calc_params)
    
    return jsonify({
        'success': True,
        'service_id': service.id,
        'service_name': service.name_ar,
        'qty': qty,
        **pricing
    })


@sanad_bp.route('/api/tickets/<int:ticket_id>/invoice', methods=['POST'])
def api_create_invoice(ticket_id):
    """Create invoice for a ticket"""
    if not require_sanad_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    ticket = SanadTicket.query.get_or_404(ticket_id)
    
    if ticket.invoice:
        return jsonify({
            'success': False,
            'message': 'Invoice already exists',
            'invoice_id': ticket.invoice.id
        })
    
    invoice = InvoiceService.create_invoice_from_ticket(ticket)
    
    return jsonify({
        'success': True,
        'invoice_id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'grand_total': invoice.grand_total
    })


# ==================== Reports ====================

@sanad_bp.route('/reports')
def reports():
    """Reports dashboard"""
    if session.get('role') not in ['manager', 'finance']:
        flash('غير مصرح', 'danger')
        return redirect(url_for('sanad.dashboard'))
    
    org = get_current_org()
    
    # Date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    
    # Revenue by day
    revenue_query = db.session.query(
        func.date(SanadPayment.created_at).label('date'),
        func.sum(SanadPayment.amount).label('total')
    ).filter(
        SanadPayment.org_id == org.id,
        func.date(SanadPayment.created_at) >= start_date
    ).group_by(func.date(SanadPayment.created_at)).all()
    
    revenue_data = {str(row.date): float(row.total) for row in revenue_query}
    
    # Tickets by status
    status_query = db.session.query(
        SanadTicket.status,
        func.count(SanadTicket.id).label('count')
    ).filter(
        SanadTicket.org_id == org.id
    ).group_by(SanadTicket.status).all()
    
    status_data = {row.status: row.count for row in status_query}
    
    return render_template('sanad/reports.html', 
                         org=org, revenue_data=revenue_data, status_data=status_data)
