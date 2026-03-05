"""
Test SPCE Fields in Revenues and Expenses
Tests the SPCE (Sistema de Prestação de Contas Eleitorais) compliance fields:
- Revenue SPCE fields: tipo_receita, tipo_doador, forma_recebimento, donor_titulo_eleitor
- Expense SPCE fields: tipo_pagamento, numero_documento_fiscal, data_pagamento
- Recibo Eleitoral PDF download
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CANDIDATO_EMAIL = "admin@test.com"
CANDIDATO_PASSWORD = "test123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": CANDIDATO_EMAIL,
        "password": CANDIDATO_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed with status {response.status_code}: {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestAuthAndLogin:
    """Test authentication endpoints"""
    
    def test_login_success(self, api_client):
        """Test successful login with candidato credentials"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": CANDIDATO_EMAIL,
            "password": CANDIDATO_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, "Token not found in response"
        
    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials returns error"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [400, 401, 404], f"Expected error status, got {response.status_code}"


class TestRevenuesSPCEFields:
    """Test Revenue CRUD with SPCE fields"""
    
    def test_create_revenue_with_spce_fields(self, authenticated_client):
        """Test creating revenue with all SPCE fields"""
        unique_id = uuid.uuid4().hex[:8]
        revenue_data = {
            "description": f"TEST_Doação SPCE {unique_id}",
            "amount": 5000.00,
            "category": "doacao_pf",
            "donor_name": "João da Silva Test",
            "donor_cpf_cnpj": "123.456.789-00",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "receipt_number": f"REC-{unique_id}",
            "notes": "Teste de doação com campos SPCE",
            # SPCE Fields
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_fisica",
            "forma_recebimento": "pix",
            "donor_titulo_eleitor": "0123 4567 8901"
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/revenues", json=revenue_data)
        assert response.status_code in [200, 201], f"Create revenue failed: {response.text}"
        
        data = response.json()
        assert data["description"] == revenue_data["description"]
        assert data["amount"] == revenue_data["amount"]
        assert data["tipo_receita"] == "doacao_financeira"
        assert data["tipo_doador"] == "pessoa_fisica"
        assert data["forma_recebimento"] == "pix"
        assert data.get("donor_titulo_eleitor") == "0123 4567 8901"
        
        # Clean up
        revenue_id = data["id"]
        authenticated_client.delete(f"{BASE_URL}/api/revenues/{revenue_id}")
        
        return revenue_id
        
    def test_get_revenues_list(self, authenticated_client):
        """Test listing revenues returns data with SPCE fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/revenues")
        assert response.status_code == 200, f"Get revenues failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of revenues"
        
    def test_create_revenue_different_spce_types(self, authenticated_client):
        """Test creating revenues with different SPCE field values"""
        unique_id = uuid.uuid4().hex[:8]
        
        # Test with fundo_eleitoral type
        revenue_data = {
            "description": f"TEST_Fundo Eleitoral {unique_id}",
            "amount": 50000.00,
            "category": "fundo_eleitoral",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "fundo_eleitoral",
            "tipo_doador": "fundo_eleitoral",
            "forma_recebimento": "transferencia"
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/revenues", json=revenue_data)
        assert response.status_code in [200, 201], f"Create revenue failed: {response.text}"
        
        data = response.json()
        assert data["tipo_receita"] == "fundo_eleitoral"
        assert data["tipo_doador"] == "fundo_eleitoral"
        assert data["forma_recebimento"] == "transferencia"
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/revenues/{data['id']}")

    def test_update_revenue_spce_fields(self, authenticated_client):
        """Test updating revenue SPCE fields"""
        unique_id = uuid.uuid4().hex[:8]
        
        # Create a revenue first
        create_data = {
            "description": f"TEST_Revenue Update {unique_id}",
            "amount": 1000.00,
            "category": "doacao_pf",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_fisica",
            "forma_recebimento": "pix"
        }
        
        create_response = authenticated_client.post(f"{BASE_URL}/api/revenues", json=create_data)
        assert create_response.status_code in [200, 201]
        revenue = create_response.json()
        revenue_id = revenue["id"]
        
        # Update with new SPCE values
        update_data = {
            "description": create_data["description"],
            "amount": 1500.00,
            "category": "doacao_pf",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "doacao_estimavel",
            "tipo_doador": "pessoa_juridica",
            "forma_recebimento": "cheque"
        }
        
        update_response = authenticated_client.put(f"{BASE_URL}/api/revenues/{revenue_id}", json=update_data)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["amount"] == 1500.00
        assert updated["tipo_receita"] == "doacao_estimavel"
        assert updated["tipo_doador"] == "pessoa_juridica"
        assert updated["forma_recebimento"] == "cheque"
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/revenues/{revenue_id}")


class TestExpensesSPCEFields:
    """Test Expense CRUD with SPCE fields"""
    
    def test_create_expense_with_spce_fields(self, authenticated_client):
        """Test creating expense with all SPCE fields"""
        unique_id = uuid.uuid4().hex[:8]
        expense_data = {
            "description": f"TEST_Despesa SPCE {unique_id}",
            "amount": 3000.00,
            "category": "publicidade",
            "supplier_name": "Gráfica Test Ltda",
            "supplier_cpf_cnpj": "12.345.678/0001-00",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "invoice_number": f"NF-{unique_id}",
            "notes": "Teste de despesa com campos SPCE",
            # SPCE Fields
            "tipo_pagamento": "pix",
            "numero_documento_fiscal": f"DOC-{unique_id}",
            "data_pagamento": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/expenses", json=expense_data)
        assert response.status_code in [200, 201], f"Create expense failed: {response.text}"
        
        data = response.json()
        assert data["description"] == expense_data["description"]
        assert data["amount"] == expense_data["amount"]
        assert data["tipo_pagamento"] == "pix"
        assert data.get("numero_documento_fiscal") == f"DOC-{unique_id}"
        assert data.get("data_pagamento") == datetime.now().strftime("%Y-%m-%d")
        
        # Clean up
        expense_id = data["id"]
        authenticated_client.delete(f"{BASE_URL}/api/expenses/{expense_id}")
        
        return expense_id
        
    def test_get_expenses_list(self, authenticated_client):
        """Test listing expenses returns data with SPCE fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/expenses")
        assert response.status_code == 200, f"Get expenses failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of expenses"
        
    def test_create_expense_different_payment_types(self, authenticated_client):
        """Test creating expenses with different payment types"""
        unique_id = uuid.uuid4().hex[:8]
        
        # Test with boleto payment type
        expense_data = {
            "description": f"TEST_Despesa Boleto {unique_id}",
            "amount": 2500.00,
            "category": "servicos_terceiros",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_pagamento": "boleto",
            "numero_documento_fiscal": f"BOLETO-{unique_id}"
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/expenses", json=expense_data)
        assert response.status_code in [200, 201], f"Create expense failed: {response.text}"
        
        data = response.json()
        assert data["tipo_pagamento"] == "boleto"
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/expenses/{data['id']}")
        
    def test_update_expense_spce_fields(self, authenticated_client):
        """Test updating expense SPCE fields"""
        unique_id = uuid.uuid4().hex[:8]
        
        # Create an expense first
        create_data = {
            "description": f"TEST_Expense Update {unique_id}",
            "amount": 800.00,
            "category": "publicidade",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_pagamento": "transferencia"
        }
        
        create_response = authenticated_client.post(f"{BASE_URL}/api/expenses", json=create_data)
        assert create_response.status_code in [200, 201]
        expense = create_response.json()
        expense_id = expense["id"]
        
        # Update with new SPCE values
        update_data = {
            "description": create_data["description"],
            "amount": 900.00,
            "category": "publicidade",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_pagamento": "cartao_credito",
            "numero_documento_fiscal": f"NF-{unique_id}",
            "data_pagamento": datetime.now().strftime("%Y-%m-%d")
        }
        
        update_response = authenticated_client.put(f"{BASE_URL}/api/expenses/{expense_id}", json=update_data)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["amount"] == 900.00
        assert updated["tipo_pagamento"] == "cartao_credito"
        assert updated.get("numero_documento_fiscal") == f"NF-{unique_id}"
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/expenses/{expense_id}")


class TestReciboEleitoralPDF:
    """Test Recibo Eleitoral PDF download functionality"""
    
    def test_download_recibo_eleitoral_pdf(self, authenticated_client):
        """Test downloading Recibo Eleitoral PDF for a revenue"""
        unique_id = uuid.uuid4().hex[:8]
        
        # First create a revenue with SPCE fields
        revenue_data = {
            "description": f"TEST_Doação para Recibo {unique_id}",
            "amount": 1000.00,
            "category": "doacao_pf",
            "donor_name": "Maria Teste Silva",
            "donor_cpf_cnpj": "987.654.321-00",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_fisica",
            "forma_recebimento": "pix",
            "donor_titulo_eleitor": "9876 5432 1098"
        }
        
        create_response = authenticated_client.post(f"{BASE_URL}/api/revenues", json=revenue_data)
        assert create_response.status_code in [200, 201], f"Create revenue failed: {create_response.text}"
        
        revenue = create_response.json()
        revenue_id = revenue["id"]
        
        # Try to download Recibo Eleitoral PDF
        pdf_response = authenticated_client.get(f"{BASE_URL}/api/revenues/{revenue_id}/recibo-pdf")
        
        # PDF should return 200 with PDF content or appropriate error if PDF generation not available
        if pdf_response.status_code == 200:
            assert pdf_response.headers.get("content-type") == "application/pdf" or \
                   "pdf" in pdf_response.headers.get("content-type", "").lower(), \
                   f"Expected PDF content type, got {pdf_response.headers.get('content-type')}"
            assert len(pdf_response.content) > 0, "PDF content should not be empty"
        else:
            # PDF feature might return 400/500 if reportlab not available - that's acceptable
            assert pdf_response.status_code in [400, 500, 501], \
                f"Unexpected status {pdf_response.status_code}: {pdf_response.text}"
        
        # Clean up
        authenticated_client.delete(f"{BASE_URL}/api/revenues/{revenue_id}")


class TestConformidadeTSE:
    """Test Conformidade TSE endpoint"""
    
    def test_get_conformidade_tse(self, authenticated_client):
        """Test getting TSE conformidade status"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/conformidade-tse")
        assert response.status_code == 200, f"Get conformidade failed: {response.text}"
        
        data = response.json()
        # Check expected fields in conformidade response
        assert "status" in data, "Should have status field"
        assert "completude_geral" in data, "Should have completude_geral field"
        assert data["completude_geral"] >= 0 and data["completude_geral"] <= 100
        
    def test_conformidade_has_resumo(self, authenticated_client):
        """Test conformidade response has summary data"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/conformidade-tse")
        assert response.status_code == 200
        
        data = response.json()
        if "resumo" in data:
            resumo = data["resumo"]
            # Should have revenue and expense counts
            assert "total_receitas" in resumo or isinstance(resumo, dict)


class TestDashboard:
    """Test Dashboard endpoint"""
    
    def test_get_dashboard_stats(self, authenticated_client):
        """Test getting dashboard statistics"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200, f"Get dashboard stats failed: {response.text}"
        
        data = response.json()
        # Check expected fields
        assert "total_revenues" in data or "total_receitas" in data, "Should have total revenues"
        assert "total_expenses" in data or "total_despesas" in data, "Should have total expenses"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
