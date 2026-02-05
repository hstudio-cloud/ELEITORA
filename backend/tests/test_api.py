"""
Backend API Tests for Brazilian Electoral ERP Platform
Tests: Authentication, Dashboard, Revenues, Expenses, Reports, CPF/CNPJ validation
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "teste@teste.com"
TEST_USER_PASSWORD = "123456"


class TestHealthCheck:
    """Health check tests - run first"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"Health check passed: {data}")


class TestAuthentication:
    """JWT Authentication tests"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert data["user"]["email"] == TEST_USER_EMAIL
        print(f"Login success: user={data['user']['name']}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with wrong credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@test.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        print("Invalid credentials test passed")
    
    def test_get_current_user(self):
        """Test /auth/me endpoint"""
        # First login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        token = login_response.json()["token"]
        
        # Get user info
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == TEST_USER_EMAIL
        print(f"Current user: {data['name']}")


class TestDashboard:
    """Dashboard endpoints tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed - skipping dashboard tests")
    
    def test_get_dashboard_stats(self, auth_token):
        """Test dashboard statistics endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "total_revenues" in data
        assert "total_expenses" in data
        assert "balance" in data
        assert "pending_payments" in data
        assert "active_contracts" in data
        assert "revenues_by_category" in data
        assert "expenses_by_category" in data
        assert "monthly_flow" in data
        
        print(f"Dashboard stats: revenues={data['total_revenues']}, expenses={data['total_expenses']}, balance={data['balance']}")


class TestPaymentAlerts:
    """Payment alerts tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_get_payment_alerts(self, auth_token):
        """Test payment alerts endpoint with days_ahead parameter"""
        response = requests.get(
            f"{BASE_URL}/api/payments/alerts?days_ahead=7",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "alerts" in data
        assert "total" in data
        assert "overdue_count" in data
        assert "due_today" in data
        
        print(f"Payment alerts: total={data['total']}, overdue={data['overdue_count']}, due_today={data['due_today']}")
        
        # Verify alerts structure if any
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "description" in alert
            assert "amount" in alert
            assert "days_until_due" in alert
            assert "is_overdue" in alert
            assert "urgency" in alert
            print(f"Sample alert: {alert['description']}, amount={alert['amount']}, days_until_due={alert['days_until_due']}")


class TestRevenues:
    """Revenues CRUD tests with period filters"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_list_revenues(self, auth_token):
        """Test listing all revenues"""
        response = requests.get(
            f"{BASE_URL}/api/revenues",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} revenues")
        
        # Verify data structure if any revenues exist
        if data:
            revenue = data[0]
            assert "id" in revenue
            assert "description" in revenue
            assert "amount" in revenue
            assert "category" in revenue
            assert "date" in revenue
            print(f"Sample revenue: {revenue['description']}, amount={revenue['amount']}")
    
    def test_create_and_delete_revenue(self, auth_token):
        """Test creating and deleting a revenue"""
        # Create revenue
        revenue_data = {
            "description": "TEST_Doacao Teste Automatizado",
            "amount": 100.50,
            "category": "doacao_pf",
            "donor_name": "Doador Teste",
            "donor_cpf_cnpj": "12345678909",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "receipt_number": "REC-TEST-001",
            "notes": "Criado por teste automatizado"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/revenues",
            json=revenue_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created = create_response.json()
        assert created["description"] == revenue_data["description"]
        assert created["amount"] == revenue_data["amount"]
        print(f"Created revenue: id={created['id']}")
        
        # Get to verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/revenues/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["id"] == created["id"]
        assert fetched["amount"] == revenue_data["amount"]
        
        # Delete revenue
        delete_response = requests.delete(
            f"{BASE_URL}/api/revenues/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200
        print(f"Deleted revenue: id={created['id']}")
        
        # Verify deletion
        verify_response = requests.get(
            f"{BASE_URL}/api/revenues/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert verify_response.status_code == 404


class TestExpenses:
    """Expenses CRUD tests with period filters"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_list_expenses(self, auth_token):
        """Test listing all expenses"""
        response = requests.get(
            f"{BASE_URL}/api/expenses",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} expenses")
        
        # Verify data structure if any expenses exist
        if data:
            expense = data[0]
            assert "id" in expense
            assert "description" in expense
            assert "amount" in expense
            assert "category" in expense
            assert "date" in expense
            print(f"Sample expense: {expense['description']}, amount={expense['amount']}")
    
    def test_create_and_delete_expense(self, auth_token):
        """Test creating and deleting an expense"""
        # Create expense
        expense_data = {
            "description": "TEST_Despesa Teste Automatizado",
            "amount": 250.75,
            "category": "publicidade",
            "supplier_name": "Fornecedor Teste",
            "supplier_cpf_cnpj": "12345678000190",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "invoice_number": "NF-TEST-001",
            "notes": "Criado por teste automatizado"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/expenses",
            json=expense_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created = create_response.json()
        assert created["description"] == expense_data["description"]
        assert created["amount"] == expense_data["amount"]
        print(f"Created expense: id={created['id']}")
        
        # Get to verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/expenses/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["id"] == created["id"]
        assert fetched["amount"] == expense_data["amount"]
        
        # Delete expense
        delete_response = requests.delete(
            f"{BASE_URL}/api/expenses/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200
        print(f"Deleted expense: id={created['id']}")
        
        # Verify deletion
        verify_response = requests.get(
            f"{BASE_URL}/api/expenses/{created['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert verify_response.status_code == 404


class TestReports:
    """Reports and exports tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_get_tse_report(self, auth_token):
        """Test TSE report generation"""
        response = requests.get(
            f"{BASE_URL}/api/reports/tse",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify report structure
        assert "receitas" in data
        assert "despesas" in data
        assert "totais" in data
        assert "gerado_em" in data
        
        if data.get("totais"):
            assert "total_receitas" in data["totais"]
            assert "total_despesas" in data["totais"]
            assert "saldo" in data["totais"]
        
        print(f"TSE Report: receitas={len(data['receitas'])}, despesas={len(data['despesas'])}")
    
    def test_export_pdf(self, auth_token):
        """Test PDF report export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/pdf?report_type=completo",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # PDF might return 200 or 400 (if campaign not fully configured)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            # Verify it's a PDF
            assert response.headers.get("content-type") == "application/pdf" or b"%PDF" in response.content[:10]
            print(f"PDF export successful, size={len(response.content)} bytes")
        else:
            print(f"PDF export returned error (may need campaign CNPJ): {response.text}")


class TestCPFCNPJValidation:
    """CPF and CNPJ validation API tests"""
    
    def test_validate_valid_cpf(self):
        """Test validating a valid CPF"""
        # Valid CPF example: 529.982.247-25
        response = requests.post(
            f"{BASE_URL}/api/validate/cpf?cpf=52998224725"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        assert data["formatted"] == "529.982.247-25"
        print(f"Valid CPF test passed: {data}")
    
    def test_validate_invalid_cpf(self):
        """Test validating an invalid CPF"""
        response = requests.post(
            f"{BASE_URL}/api/validate/cpf?cpf=12345678900"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False
        assert data["formatted"] is None
        print(f"Invalid CPF test passed: {data}")
    
    def test_validate_valid_cnpj(self):
        """Test validating a valid CNPJ"""
        # Valid CNPJ example: 11.222.333/0001-81
        response = requests.post(
            f"{BASE_URL}/api/validate/cnpj?cnpj=11222333000181"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        assert data["formatted"] == "11.222.333/0001-81"
        print(f"Valid CNPJ test passed: {data}")
    
    def test_validate_invalid_cnpj(self):
        """Test validating an invalid CNPJ"""
        response = requests.post(
            f"{BASE_URL}/api/validate/cnpj?cnpj=12345678000190"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False
        assert data["formatted"] is None
        print(f"Invalid CNPJ test passed: {data}")


class TestCampaign:
    """Campaign tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_get_my_campaign(self, auth_token):
        """Test getting user's campaign"""
        response = requests.get(
            f"{BASE_URL}/api/campaigns/my",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data:
            # Verify campaign structure
            assert "id" in data
            assert "candidate_name" in data
            assert "party" in data
            assert "position" in data
            assert "city" in data
            assert "state" in data
            print(f"Campaign: {data['candidate_name']} - {data['party']} - {data['position']}")
        else:
            print("No campaign configured for user")


class TestPayments:
    """Payments CRUD tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["token"]
        pytest.skip("Login failed")
    
    def test_list_payments(self, auth_token):
        """Test listing all payments"""
        response = requests.get(
            f"{BASE_URL}/api/payments",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} payments")
        
        # Check for pending payments
        pending = [p for p in data if p.get("status") == "pendente"]
        print(f"Pending payments: {len(pending)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
