"""
Seed data for Sanad system
Populate with common Omani government services and entities
"""
from extensions import db
from sanad.models import (
    Organization, SanadBranch, GovEntity, GovService,
    NotificationTemplate
)
from datetime import datetime


def seed_sanad_data():
    """Seed basic Sanad data"""
    
    # Check if already seeded
    if Organization.query.first():
        print("⚠️ Organization already exists, skipping seed")
        return
    
    # Create default organization
    org = Organization(
        name="Sanad Services",
        name_ar="خدمات سند",
        vat_number="OM1234567890",
        commercial_registration="CR123456",
        phone="+968 24123456",
        email="info@sanad.om",
        address="Muscat, Sultanate of Oman"
    )
    db.session.add(org)
    db.session.flush()
    
    print("✅ Created organization: Sanad Services")
    
    # Create default branch
    branch = SanadBranch(
        org_id=org.id,
        name="Main Branch",
        name_ar="الفرع الرئيسي",
        city="Muscat",
        address="Ruwi, Muscat",
        phone="+968 24123456"
    )
    db.session.add(branch)
    db.session.flush()
    
    print("✅ Created branch: Main Branch")
    
    # Create government entities
    entities_data = [
        {
            "name": "Ministry of Labor",
            "name_ar": "وزارة العمل",
            "code": "MOL",
            "description": "Responsible for labor affairs, work permits, and worker residency"
        },
        {
            "name": "Ministry of Commerce, Industry and Investment Promotion",
            "name_ar": "وزارة التجارة والصناعة وترويج الاستثمار",
            "code": "MOCI",
            "description": "Handles commercial registration, business licenses"
        },
        {
            "name": "Royal Oman Police",
            "name_ar": "شرطة عُمان السلطانية",
            "code": "ROP",
            "description": "Immigration, residence visas, traffic services"
        },
        {
            "name": "Municipality",
            "name_ar": "البلدية",
            "code": "MUN",
            "description": "Building permits, business licenses, health certificates"
        },
        {
            "name": "Ministry of Health",
            "name_ar": "وزارة الصحة",
            "code": "MOH",
            "description": "Health certificates, medical approvals"
        }
    ]
    
    entities = {}
    for ent_data in entities_data:
        entity = GovEntity(**ent_data)
        db.session.add(entity)
        db.session.flush()
        entities[ent_data['code']] = entity
        print(f"✅ Created entity: {ent_data['name_ar']}")
    
    # Create common services
    services_data = [
        # Ministry of Labor
        {
            "name": "Worker Residence Renewal",
            "name_ar": "تجديد إقامة عامل",
            "code": "MOL_RES_RENEW",
            "gov_entity_id": entities['MOL'].id,
            "base_office_fee": 3.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 10.0,
            "vat_applicable": True,
            "sla_minutes": 2880,  # 2 days
            "description": "Renewal of worker residence permit"
        },
        {
            "name": "New Work Permit",
            "name_ar": "تصريح عمل جديد",
            "code": "MOL_WORK_NEW",
            "gov_entity_id": entities['MOL'].id,
            "base_office_fee": 5.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 50.0,
            "vat_applicable": True,
            "sla_minutes": 4320,  # 3 days
            "description": "New work permit application"
        },
        {
            "name": "Sponsorship Transfer",
            "name_ar": "نقل كفالة",
            "code": "MOL_SPONSOR_TRANSFER",
            "gov_entity_id": entities['MOL'].id,
            "base_office_fee": 10.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 30.0,
            "vat_applicable": True,
            "sla_minutes": 10080,  # 7 days
            "description": "Transfer worker sponsorship"
        },
        
        # Ministry of Commerce
        {
            "name": "Commercial Registration Renewal",
            "name_ar": "تجديد سجل تجاري",
            "code": "MOCI_CR_RENEW",
            "gov_entity_id": entities['MOCI'].id,
            "base_office_fee": 5.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 20.0,
            "vat_applicable": True,
            "sla_minutes": 7200,  # 5 days
            "description": "Renew commercial registration"
        },
        {
            "name": "New Commercial Registration",
            "name_ar": "سجل تجاري جديد",
            "code": "MOCI_CR_NEW",
            "gov_entity_id": entities['MOCI'].id,
            "base_office_fee": 15.0,
            "gov_fee_type": "variable",
            "gov_fee_value": 50.0,  # Base, varies by activity
            "vat_applicable": True,
            "sla_minutes": 14400,  # 10 days
            "description": "New commercial registration application"
        },
        {
            "name": "CR Amendment",
            "name_ar": "تعديل سجل تجاري",
            "code": "MOCI_CR_AMEND",
            "gov_entity_id": entities['MOCI'].id,
            "base_office_fee": 7.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 10.0,
            "vat_applicable": True,
            "sla_minutes": 5760,  # 4 days
            "description": "Amendment to commercial registration"
        },
        
        # Royal Oman Police
        {
            "name": "Residence Visa Application",
            "name_ar": "تأشيرة إقامة",
            "code": "ROP_VISA_RES",
            "gov_entity_id": entities['ROP'].id,
            "base_office_fee": 8.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 50.0,
            "vat_applicable": True,
            "sla_minutes": 14400,  # 10 days
            "description": "New residence visa application"
        },
        {
            "name": "Visa Renewal",
            "name_ar": "تجديد تأشيرة",
            "code": "ROP_VISA_RENEW",
            "gov_entity_id": entities['ROP'].id,
            "base_office_fee": 5.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 20.0,
            "vat_applicable": True,
            "sla_minutes": 7200,  # 5 days
            "description": "Renew existing visa"
        },
        
        # Municipality
        {
            "name": "Business License Renewal",
            "name_ar": "تجديد رخصة بلدية",
            "code": "MUN_BL_RENEW",
            "gov_entity_id": entities['MUN'].id,
            "base_office_fee": 4.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 30.0,
            "vat_applicable": True,
            "sla_minutes": 4320,  # 3 days
            "description": "Renew municipal business license"
        },
        {
            "name": "Health Certificate",
            "name_ar": "شهادة صحية",
            "code": "MUN_HEALTH_CERT",
            "gov_entity_id": entities['MUN'].id,
            "base_office_fee": 2.0,
            "gov_fee_type": "fixed",
            "gov_fee_value": 10.0,
            "vat_applicable": True,
            "sla_minutes": 2880,  # 2 days
            "description": "Health certificate for food businesses"
        },
        {
            "name": "Building Permit",
            "name_ar": "تصريح بناء",
            "code": "MUN_BUILD_PERMIT",
            "gov_entity_id": entities['MUN'].id,
            "base_office_fee": 20.0,
            "gov_fee_type": "variable",
            "gov_fee_value": 100.0,  # Varies by size
            "vat_applicable": True,
            "sla_minutes": 21600,  # 15 days
            "description": "Building construction permit"
        }
    ]
    
    for svc_data in services_data:
        service = GovService(org_id=org.id, **svc_data)
        db.session.add(service)
        print(f"✅ Created service: {svc_data['name_ar']}")
    
    # Create notification templates
    templates_data = [
        {
            "key": "ticket_created",
            "channel": "sms",
            "body": "عزيزنا العميل، تم إنشاء معاملة رقم {ticket_code}. المبلغ الإجمالي: {amount} ريال. شكراً لتعاملكم معنا.",
            "variables": ["ticket_code", "amount"]
        },
        {
            "key": "ticket_completed",
            "channel": "sms",
            "body": "تم إنجاز معاملتكم رقم {ticket_code}. يمكنكم استلام المستندات من فرع {branch_name}.",
            "variables": ["ticket_code", "branch_name"]
        },
        {
            "key": "payment_received",
            "channel": "sms",
            "body": "تم استلام دفعتكم بمبلغ {amount} ريال للمعاملة {ticket_code}. رقم الإيصال: {receipt_no}",
            "variables": ["amount", "ticket_code", "receipt_no"]
        },
        {
            "key": "docs_required",
            "channel": "sms",
            "body": "عزيزنا العميل، نحتاج مستندات إضافية للمعاملة {ticket_code}. الرجاء التواصل معنا.",
            "variables": ["ticket_code"]
        }
    ]
    
    for tmpl_data in templates_data:
        template = NotificationTemplate(org_id=org.id, **tmpl_data)
        db.session.add(template)
        print(f"✅ Created notification template: {tmpl_data['key']}")
    
    db.session.commit()
    print("\n✅ Sanad seed data completed successfully!")
    print(f"   Organization: {org.name_ar}")
    print(f"   Branch: {branch.name_ar}")
    print(f"   Government Entities: {len(entities_data)}")
    print(f"   Services: {len(services_data)}")
    print(f"   Notification Templates: {len(templates_data)}")


if __name__ == "__main__":
    from app import app
    with app.app_context():
        seed_sanad_data()
