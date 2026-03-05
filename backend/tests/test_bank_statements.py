"""
Tests for Bank Statements OFX Import and Reconciliation Features
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "test123"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


class TestDocumentValidation:
    """Tests for CPF/CNPJ validation endpoint"""
    
    def test_validate_valid_cpf(self, api_client):
        """Test validation of valid CPF"""
        # Valid CPF: 529.982.247-25 (checksum valid)
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=52998224725")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "cpf"
        assert data["valid"] == True
        assert data["formatted"] == "529.982.247-25"
    
    def test_validate_invalid_cpf(self, api_client):
        """Test validation of invalid CPF"""
        # Invalid CPF
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=12345678901")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "cpf"
        assert data["valid"] == False
    
    def test_validate_valid_cnpj(self, api_client):
        """Test validation of valid CNPJ"""
        # Valid CNPJ: 11.222.333/0001-81 (checksum valid)
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=11222333000181")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "cnpj"
        assert data["valid"] == True
        assert data["formatted"] == "11.222.333/0001-81"
    
    def test_validate_invalid_cnpj(self, api_client):
        """Test validation of invalid CNPJ"""
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=12345678000100")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "cnpj"
        assert data["valid"] == False
    
    def test_validate_formatted_cpf(self, api_client):
        """Test validation with formatted input"""
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=529.982.247-25")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "cpf"
        assert data["valid"] == True
    
    def test_validate_invalid_length(self, api_client):
        """Test validation with wrong length document"""
        response = api_client.get(f"{BASE_URL}/api/validate/document?cpf_cnpj=12345")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "unknown"
        assert data["valid"] == False
        assert "error" in data


class TestBankStatementsEndpoints:
    """Tests for Bank Statements API endpoints"""
    
    def test_list_bank_statements_unauthenticated(self, api_client):
        """Test that bank statements require authentication"""
        response = api_client.get(f"{BASE_URL}/api/bank-statements")
        assert response.status_code == 403 or response.status_code == 401
    
    def test_list_bank_statements_authenticated(self, api_client, auth_token):
        """Test listing bank statements with auth"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
        response = api_client.get(f"{BASE_URL}/api/bank-statements")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_upload_invalid_file_format(self, api_client, auth_token):
        """Test upload rejection for non-OFX files"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
        api_client.headers.pop("Content-Type", None)
        
        # Create a dummy non-OFX file
        files = {'file': ('test.txt', b'This is not an OFX file', 'text/plain')}
        response = api_client.post(f"{BASE_URL}/api/bank-statements/upload", files=files)
        
        assert response.status_code == 400
        assert "inválido" in response.json()["detail"].lower() or "format" in response.json()["detail"].lower()


class TestBankTransactionActions:
    """Tests for bank transaction actions (reconcile, ignore, create record)"""
    
    def test_get_nonexistent_statement(self, api_client, auth_token):
        """Test getting a non-existent statement returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
        response = api_client.get(f"{BASE_URL}/api/bank-statements/nonexistent-id-123")
        assert response.status_code == 404


class TestRevenuesWithCpfCnpj:
    """Tests for Revenues with CPF/CNPJ fields"""
    
    def test_create_revenue_with_valid_cpf(self, api_client, auth_token):
        """Test creating revenue with valid CPF"""
        api_client.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "description": f"TEST_Revenue_{unique_id}",
            "amount": 1500.00,
            "category": "doacao_pf",
            "donor_name": f"Test Donor {unique_id}",
            "donor_cpf_cnpj": "529.982.247-25",  # Valid CPF
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_fisica",
            "forma_recebimento": "pix"
        }
        
        response = api_client.post(f"{BASE_URL}/api/revenues", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Cleanup
        if "id" in data:
            api_client.delete(f"{BASE_URL}/api/revenues/{data['id']}")
    
    def test_create_revenue_with_cnpj(self, api_client, auth_token):
        """Test creating revenue with CNPJ (PJ donation)"""
        api_client.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "description": f"TEST_Revenue_PJ_{unique_id}",
            "amount": 5000.00,
            "category": "doacao_pj",
            "donor_name": f"Test Company {unique_id}",
            "donor_cpf_cnpj": "11.222.333/0001-81",  # Valid CNPJ
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_juridica",
            "forma_recebimento": "transferencia"
        }
        
        response = api_client.post(f"{BASE_URL}/api/revenues", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Cleanup
        if "id" in data:
            api_client.delete(f"{BASE_URL}/api/revenues/{data['id']}")


class TestExpensesWithCpfCnpj:
    """Tests for Expenses with CPF/CNPJ fields"""
    
    def test_create_expense_with_valid_cpf(self, api_client, auth_token):
        """Test creating expense with valid supplier CPF"""
        api_client.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "description": f"TEST_Expense_{unique_id}",
            "amount": 800.00,
            "category": "servicos_terceiros",
            "supplier_name": f"Test Supplier {unique_id}",
            "supplier_cpf_cnpj": "529.982.247-25",  # Valid CPF
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_pagamento": "pix",
            "numero_documento_fiscal": f"NF{unique_id}"
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Cleanup
        if "id" in data:
            api_client.delete(f"{BASE_URL}/api/expenses/{data['id']}")
    
    def test_create_expense_with_cnpj(self, api_client, auth_token):
        """Test creating expense with valid supplier CNPJ"""
        api_client.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "description": f"TEST_Expense_PJ_{unique_id}",
            "amount": 2500.00,
            "category": "publicidade",
            "supplier_name": f"Test Agency {unique_id}",
            "supplier_cpf_cnpj": "11.222.333/0001-81",  # Valid CNPJ
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_pagamento": "boleto",
            "numero_documento_fiscal": f"NF{unique_id}"
        }
        
        response = api_client.post(f"{BASE_URL}/api/expenses", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Cleanup
        if "id" in data:
            api_client.delete(f"{BASE_URL}/api/expenses/{data['id']}")
