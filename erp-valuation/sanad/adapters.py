"""
Government Integration Adapters
Abstract interface and mock implementations for government entity integrations
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime
import json


class GovAdapterInterface(ABC):
    """Abstract base class for government integrations"""
    
    @abstractmethod
    def login(self, credentials: Dict) -> bool:
        """Authenticate with government system"""
        pass
    
    @abstractmethod
    def submit(self, request_data: Dict) -> Dict:
        """
        Submit a request to government system
        
        Returns:
            Dict with 'success', 'reference_number', 'message'
        """
        pass
    
    @abstractmethod
    def get_status(self, reference_number: str) -> Dict:
        """
        Check status of a submitted request
        
        Returns:
            Dict with 'status', 'updated_at', 'notes'
        """
        pass
    
    @abstractmethod
    def download_receipt(self, reference_number: str) -> Optional[bytes]:
        """Download official receipt/certificate"""
        pass
    
    @abstractmethod
    def get_fees(self, service_code: str, params: Dict = None) -> Dict:
        """
        Get fees for a service
        
        Returns:
            Dict with 'amount', 'currency', 'breakdown'
        """
        pass


class MockLaborAdapter(GovAdapterInterface):
    """Mock adapter for Ministry of Labor (وزارة العمل)"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logged_in = False
        self.mock_db = {}  # In-memory storage for demo
        
    def login(self, credentials: Dict) -> bool:
        """Mock login"""
        # In real implementation, would authenticate with actual API
        self.logged_in = True
        return True
    
    def submit(self, request_data: Dict) -> Dict:
        """Mock submit worker residence renewal"""
        if not self.logged_in:
            return {'success': False, 'message': 'Not authenticated'}
        
        # Generate mock reference number
        ref = f"LABOR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Store in mock DB
        self.mock_db[ref] = {
            'reference': ref,
            'service': request_data.get('service_type', 'worker_residence_renewal'),
            'worker_name': request_data.get('worker_name'),
            'passport_no': request_data.get('passport_no'),
            'employer': request_data.get('employer'),
            'status': 'submitted',
            'submitted_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'reference_number': ref,
            'message': 'تم تقديم الطلب بنجاح - Request submitted successfully',
            'estimated_completion': '3-5 business days'
        }
    
    def get_status(self, reference_number: str) -> Dict:
        """Mock status check"""
        if reference_number not in self.mock_db:
            return {
                'success': False,
                'message': 'Reference number not found'
            }
        
        record = self.mock_db[reference_number]
        return {
            'success': True,
            'status': record['status'],
            'updated_at': record['updated_at'],
            'notes': 'Processing normally'
        }
    
    def download_receipt(self, reference_number: str) -> Optional[bytes]:
        """Mock download - returns placeholder"""
        if reference_number not in self.mock_db:
            return None
        
        # In real implementation, would download actual PDF
        mock_pdf = b'%PDF-1.4 Mock Labor Ministry Receipt'
        return mock_pdf
    
    def get_fees(self, service_code: str, params: Dict = None) -> Dict:
        """Mock fee calculation"""
        fees = {
            'worker_residence_renewal': 10.0,  # 10 OMR
            'work_permit': 50.0,
            'labor_card': 5.0
        }
        
        amount = fees.get(service_code, 0.0)
        
        return {
            'amount': amount,
            'currency': 'OMR',
            'breakdown': [
                {'description': 'Government fee', 'amount': amount}
            ]
        }


class MockCommerceAdapter(GovAdapterInterface):
    """Mock adapter for Ministry of Commerce (وزارة التجارة والصناعة)"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logged_in = False
        self.mock_db = {}
        
    def login(self, credentials: Dict) -> bool:
        self.logged_in = True
        return True
    
    def submit(self, request_data: Dict) -> Dict:
        if not self.logged_in:
            return {'success': False, 'message': 'Not authenticated'}
        
        ref = f"MOCI-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.mock_db[ref] = {
            'reference': ref,
            'service': request_data.get('service_type', 'cr_renewal'),
            'company_name': request_data.get('company_name'),
            'cr_number': request_data.get('cr_number'),
            'status': 'under_review',
            'submitted_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'reference_number': ref,
            'message': 'تم تقديم الطلب - Request under review',
            'estimated_completion': '5-7 business days'
        }
    
    def get_status(self, reference_number: str) -> Dict:
        if reference_number not in self.mock_db:
            return {'success': False, 'message': 'Not found'}
        
        record = self.mock_db[reference_number]
        return {
            'success': True,
            'status': record['status'],
            'updated_at': record['updated_at'],
            'notes': 'Under review by ministry'
        }
    
    def download_receipt(self, reference_number: str) -> Optional[bytes]:
        if reference_number not in self.mock_db:
            return None
        return b'%PDF-1.4 Mock Commerce Ministry Certificate'
    
    def get_fees(self, service_code: str, params: Dict = None) -> Dict:
        fees = {
            'cr_renewal': 20.0,  # 20 OMR
            'cr_amendment': 10.0,
            'license_renewal': 50.0
        }
        
        amount = fees.get(service_code, 0.0)
        
        return {
            'amount': amount,
            'currency': 'OMR',
            'breakdown': [
                {'description': 'Registration fee', 'amount': amount}
            ]
        }


class MockROPAdapter(GovAdapterInterface):
    """Mock adapter for Royal Oman Police (شرطة عُمان السلطانية)"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logged_in = False
        self.mock_db = {}
        
    def login(self, credentials: Dict) -> bool:
        self.logged_in = True
        return True
    
    def submit(self, request_data: Dict) -> Dict:
        if not self.logged_in:
            return {'success': False, 'message': 'Not authenticated'}
        
        ref = f"ROP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.mock_db[ref] = {
            'reference': ref,
            'service': request_data.get('service_type', 'residence_visa'),
            'applicant_name': request_data.get('applicant_name'),
            'passport_no': request_data.get('passport_no'),
            'status': 'processing',
            'submitted_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'reference_number': ref,
            'message': 'تم استلام الطلب - Request received',
            'estimated_completion': '7-10 business days'
        }
    
    def get_status(self, reference_number: str) -> Dict:
        if reference_number not in self.mock_db:
            return {'success': False, 'message': 'Not found'}
        
        record = self.mock_db[reference_number]
        return {
            'success': True,
            'status': record['status'],
            'updated_at': record['updated_at'],
            'notes': 'Security clearance in progress'
        }
    
    def download_receipt(self, reference_number: str) -> Optional[bytes]:
        if reference_number not in self.mock_db:
            return None
        return b'%PDF-1.4 Mock ROP Visa Approval'
    
    def get_fees(self, service_code: str, params: Dict = None) -> Dict:
        fees = {
            'residence_visa': 50.0,  # 50 OMR
            'visa_renewal': 20.0,
            'entry_permit': 15.0
        }
        
        amount = fees.get(service_code, 0.0)
        
        return {
            'amount': amount,
            'currency': 'OMR',
            'breakdown': [
                {'description': 'Visa fee', 'amount': amount}
            ]
        }


class MockMunicipalityAdapter(GovAdapterInterface):
    """Mock adapter for Municipality (البلدية)"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logged_in = False
        self.mock_db = {}
        
    def login(self, credentials: Dict) -> bool:
        self.logged_in = True
        return True
    
    def submit(self, request_data: Dict) -> Dict:
        if not self.logged_in:
            return {'success': False, 'message': 'Not authenticated'}
        
        ref = f"MUN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.mock_db[ref] = {
            'reference': ref,
            'service': request_data.get('service_type', 'building_permit'),
            'property_number': request_data.get('property_number'),
            'owner_name': request_data.get('owner_name'),
            'status': 'inspection_scheduled',
            'submitted_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return {
            'success': True,
            'reference_number': ref,
            'message': 'تم تسجيل الطلب - Request registered',
            'estimated_completion': '10-15 business days'
        }
    
    def get_status(self, reference_number: str) -> Dict:
        if reference_number not in self.mock_db:
            return {'success': False, 'message': 'Not found'}
        
        record = self.mock_db[reference_number]
        return {
            'success': True,
            'status': record['status'],
            'updated_at': record['updated_at'],
            'notes': 'Site inspection scheduled'
        }
    
    def download_receipt(self, reference_number: str) -> Optional[bytes]:
        if reference_number not in self.mock_db:
            return None
        return b'%PDF-1.4 Mock Municipality Approval'
    
    def get_fees(self, service_code: str, params: Dict = None) -> Dict:
        fees = {
            'building_permit': 100.0,  # 100 OMR
            'business_license': 30.0,
            'health_certificate': 10.0
        }
        
        amount = fees.get(service_code, 0.0)
        
        return {
            'amount': amount,
            'currency': 'OMR',
            'breakdown': [
                {'description': 'Municipal fee', 'amount': amount}
            ]
        }


class AdapterFactory:
    """Factory to get appropriate adapter based on type"""
    
    ADAPTERS = {
        'labor': MockLaborAdapter,
        'commerce': MockCommerceAdapter,
        'rop': MockROPAdapter,
        'municipality': MockMunicipalityAdapter
    }
    
    @classmethod
    def get_adapter(cls, adapter_type: str, config: Dict = None) -> GovAdapterInterface:
        """Get adapter instance"""
        adapter_class = cls.ADAPTERS.get(adapter_type.lower())
        if not adapter_class:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        return adapter_class(config)
    
    @classmethod
    def list_adapters(cls) -> List[str]:
        """List available adapter types"""
        return list(cls.ADAPTERS.keys())
