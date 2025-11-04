"""
Sanad Business Logic Services
Pricing, VAT calculation, and ticket workflow management
"""
from datetime import datetime
from typing import Dict, List, Tuple
from extensions import db
from sanad.models import (
    GovService, SanadTicket, TicketItem, TicketLog,
    SanadInvoice, InvoiceItem, SanadPayment
)


# VAT Configuration
VAT_RATE = 0.05  # 5% VAT in Oman


class PricingService:
    """Handles pricing calculation with VAT"""
    
    @staticmethod
    def calculate_line_item(service: GovService, qty: int = 1, 
                           calc_params: Dict = None) -> Dict:
        """
        Calculate pricing for a service line item
        
        Args:
            service: The government service
            qty: Quantity
            calc_params: Parameters for variable gov fee calculation
            
        Returns:
            Dict with office_fee, gov_fee, vat_amount, line_total
        """
        office_fee = service.base_office_fee * qty
        
        # Government fee calculation
        if service.gov_fee_type == 'fixed':
            gov_fee = service.gov_fee_value * qty
        else:
            # Variable calculation (would need custom logic per service)
            # For now, use base value
            gov_fee = service.gov_fee_value * qty
            
        # VAT only on office fees, NOT on government fees (pass-through)
        vat_amount = 0.0
        if service.vat_applicable:
            vat_amount = round(office_fee * VAT_RATE, 3)
            
        # Line total = office fee + VAT + gov fee
        line_total = round(office_fee + vat_amount + gov_fee, 3)
        
        return {
            'office_fee': round(office_fee, 3),
            'gov_fee': round(gov_fee, 3),
            'vat_amount': round(vat_amount, 3),
            'line_total': round(line_total, 3)
        }
    
    @staticmethod
    def calculate_invoice_totals(items: List[TicketItem]) -> Dict:
        """
        Calculate invoice totals from ticket items
        
        Returns:
            Dict with subtotal_office_fee, total_gov_fees, vat_amount, grand_total
        """
        subtotal_office_fee = sum(item.office_fee for item in items)
        total_gov_fees = sum(item.gov_fee for item in items)
        vat_amount = sum(item.vat_amount for item in items)
        grand_total = subtotal_office_fee + vat_amount + total_gov_fees
        
        return {
            'subtotal_office_fee': round(subtotal_office_fee, 3),
            'total_gov_fees': round(total_gov_fees, 3),
            'vat_amount': round(vat_amount, 3),
            'grand_total': round(grand_total, 3)
        }


class TicketService:
    """Ticket workflow management"""
    
    VALID_STATUSES = [
        'new', 'pending_docs', 'priced', 'paid', 'submitted', 
        'in_progress', 'completed', 'rejected', 'refunded', 'canceled'
    ]
    
    @staticmethod
    def generate_ticket_code(org_id: int, branch_id: int) -> str:
        """Generate unique ticket code"""
        from sqlalchemy import func, extract
        
        # Format: ORG{org_id}-BR{branch_id}-YYYY-NNNN
        current_year = datetime.utcnow().year
        
        # Count tickets for this branch this year
        count = db.session.query(func.count(SanadTicket.id)).filter(
            SanadTicket.org_id == org_id,
            SanadTicket.branch_id == branch_id,
            extract('year', SanadTicket.created_at) == current_year
        ).scalar() or 0
        
        sequence = count + 1
        return f"ORG{org_id}-BR{branch_id}-{current_year}-{sequence:04d}"
    
    @staticmethod
    def create_ticket(org_id: int, branch_id: int, customer_id: int, 
                     created_by: int, service_items: List[Dict]) -> SanadTicket:
        """
        Create a new ticket with services
        
        Args:
            org_id: Organization ID
            branch_id: Branch ID
            customer_id: Customer ID
            created_by: User ID who created the ticket
            service_items: List of dicts with 'service_id', 'qty', optional 'calc_params'
            
        Returns:
            Created ticket with items
        """
        # Generate ticket code
        code = TicketService.generate_ticket_code(org_id, branch_id)
        
        # Create ticket
        ticket = SanadTicket(
            org_id=org_id,
            branch_id=branch_id,
            customer_id=customer_id,
            code=code,
            status='new',
            created_by=created_by
        )
        db.session.add(ticket)
        db.session.flush()  # Get ticket ID
        
        # Add service items
        for item_data in service_items:
            service = db.session.query(GovService).get(item_data['service_id'])
            if not service:
                continue
                
            qty = item_data.get('qty', 1)
            calc_params = item_data.get('calc_params')
            
            # Calculate pricing
            pricing = PricingService.calculate_line_item(service, qty, calc_params)
            
            # Create ticket item
            item = TicketItem(
                ticket_id=ticket.id,
                service_id=service.id,
                qty=qty,
                office_fee=pricing['office_fee'],
                gov_fee=pricing['gov_fee'],
                vat_amount=pricing['vat_amount'],
                line_total=pricing['line_total'],
                calculation_params=calc_params
            )
            db.session.add(item)
        
        # Log creation
        log = TicketLog(
            ticket_id=ticket.id,
            actor_id=created_by,
            action='created',
            notes='Ticket created'
        )
        db.session.add(log)
        
        # Update status to priced
        ticket.status = 'priced'
        
        db.session.commit()
        return ticket
    
    @staticmethod
    def change_status(ticket: SanadTicket, new_status: str, 
                     actor_id: int, notes: str = None) -> bool:
        """
        Change ticket status with logging
        
        Returns:
            True if status changed, False if invalid transition
        """
        if new_status not in TicketService.VALID_STATUSES:
            return False
            
        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()
        
        # Update timestamps for specific statuses
        if new_status == 'paid':
            ticket.paid_at = datetime.utcnow()
        elif new_status == 'submitted':
            ticket.submitted_at = datetime.utcnow()
        elif new_status == 'completed':
            ticket.completed_at = datetime.utcnow()
        
        # Log the change
        log = TicketLog(
            ticket_id=ticket.id,
            actor_id=actor_id,
            action='status_changed',
            notes=notes or f'Status changed from {old_status} to {new_status}',
            metadata={'old_status': old_status, 'new_status': new_status}
        )
        db.session.add(log)
        db.session.commit()
        
        return True


class InvoiceService:
    """Invoice management"""
    
    @staticmethod
    def generate_invoice_number(org_id: int) -> str:
        """Generate unique invoice number"""
        from sqlalchemy import func, extract
        
        # Format: INV-YYYY-NNNNN
        current_year = datetime.utcnow().year
        
        # Count invoices for this org this year
        count = db.session.query(func.count(SanadInvoice.id)).filter(
            SanadInvoice.org_id == org_id,
            extract('year', SanadInvoice.created_at) == current_year
        ).scalar() or 0
        
        sequence = count + 1
        return f"INV-{current_year}-{sequence:05d}"
    
    @staticmethod
    def create_invoice_from_ticket(ticket: SanadTicket) -> SanadInvoice:
        """
        Create invoice from a ticket
        
        Args:
            ticket: The ticket to invoice
            
        Returns:
            Created invoice
        """
        # Check if invoice already exists
        if ticket.invoice:
            return ticket.invoice
        
        # Generate invoice number
        invoice_number = InvoiceService.generate_invoice_number(ticket.org_id)
        
        # Calculate totals
        totals = PricingService.calculate_invoice_totals(ticket.items)
        
        # Create invoice
        invoice = SanadInvoice(
            org_id=ticket.org_id,
            branch_id=ticket.branch_id,
            customer_id=ticket.customer_id,
            ticket_id=ticket.id,
            invoice_number=invoice_number,
            subtotal_office_fee=totals['subtotal_office_fee'],
            total_gov_fees=totals['total_gov_fees'],
            vat_amount=totals['vat_amount'],
            grand_total=totals['grand_total'],
            status='issued'
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Create invoice items from ticket items
        for ticket_item in ticket.items:
            service = ticket_item.service
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                service_id=service.id if service else None,
                description=service.name_ar if service else 'خدمة',
                qty=ticket_item.qty,
                office_fee=ticket_item.office_fee,
                gov_fee=ticket_item.gov_fee,
                vat_amount=ticket_item.vat_amount,
                line_total=ticket_item.line_total
            )
            db.session.add(invoice_item)
        
        db.session.commit()
        return invoice
    
    @staticmethod
    def record_payment(invoice: SanadInvoice, amount: float, method: str,
                      created_by: int, reference: str = None, notes: str = None) -> SanadPayment:
        """
        Record a payment for an invoice
        
        Args:
            invoice: The invoice
            amount: Payment amount
            method: Payment method (cash, card, transfer, qr)
            created_by: User ID who recorded the payment
            reference: Optional reference number
            notes: Optional notes
            
        Returns:
            Payment record
        """
        payment = SanadPayment(
            org_id=invoice.org_id,
            branch_id=invoice.branch_id,
            invoice_id=invoice.id,
            method=method,
            amount=amount,
            reference=reference,
            created_by=created_by,
            notes=notes
        )
        db.session.add(payment)
        
        # Check if invoice is fully paid
        total_paid = sum(p.amount for p in invoice.payments) + amount
        if total_paid >= invoice.grand_total:
            invoice.status = 'paid'
            invoice.paid_at = datetime.utcnow()
            
            # Update ticket status
            if invoice.ticket:
                TicketService.change_status(
                    invoice.ticket, 'paid', created_by, 
                    f'Payment received: {amount} OMR via {method}'
                )
        
        db.session.commit()
        return payment
