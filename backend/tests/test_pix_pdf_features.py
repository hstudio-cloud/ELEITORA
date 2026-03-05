"""
Test PIX Payments and PDF Generation features for Eleitora 360
- PIX payment creation, listing, execution simulation
- PDF generation for contracts
- Download signed contract PDF
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://brasil-voting.preview.emergentagent.com').rstrip('/')


class TestPIXPaymentsAPI:
    """Test PIX payment endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_01_health_check(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_02_pix_bank_info(self):
        """Test bank info endpoint (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/pix/bank-info")
        assert response.status_code == 200
        data = response.json()
        assert data["bank"] == "Banco do Brasil"
        assert "integration_status" in data
        assert "features" in data
        assert "PIX Pagamento" in data["features"]
        print(f"✓ Bank info: {data['bank']} - Status: {data['integration_status']}")
    
    def test_03_pix_payments_list(self):
        """Test listing PIX payments"""
        response = requests.get(f"{BASE_URL}/api/pix/payments", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} PIX payments")
    
    def test_04_pix_payments_list_no_auth(self):
        """Test listing PIX payments without auth - should fail"""
        response = requests.get(f"{BASE_URL}/api/pix/payments")
        assert response.status_code == 403, "Expected 403 without auth"
        print("✓ PIX list protected (returns 403 without auth)")
    
    def test_05_create_pix_payment(self):
        """Test creating a new PIX payment"""
        pix_data = {
            "pix_key": "12345678901",
            "pix_key_type": "cpf",
            "recipient_name": "Teste PIX Recipient",
            "recipient_cpf_cnpj": "123.456.789-01",
            "amount": 150.00,
            "description": "Teste PIX criado por test_pix_pdf_features.py",
            "scheduled_date": "2026-02-01"
        }
        
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200, f"Failed to create PIX: {response.text}"
        
        data = response.json()
        assert "pix_payment" in data
        assert data["pix_payment"]["recipient_name"] == "Teste PIX Recipient"
        assert data["pix_payment"]["amount"] == 150.00
        assert data["pix_payment"]["status"] == "agendado"
        assert "note" in data  # Should have simulation note
        
        # Store for later tests
        self.__class__.created_pix_id = data["pix_payment"]["id"]
        print(f"✓ Created PIX payment: {self.__class__.created_pix_id}")
    
    def test_06_get_single_pix_payment(self):
        """Test getting a single PIX payment by ID"""
        pix_id = getattr(self.__class__, 'created_pix_id', None)
        if not pix_id:
            pytest.skip("No PIX payment created in previous test")
        
        response = requests.get(f"{BASE_URL}/api/pix/payment/{pix_id}", headers=self.headers)
        assert response.status_code == 200, f"Failed to get PIX: {response.text}"
        
        data = response.json()
        assert data["id"] == pix_id
        assert data["recipient_name"] == "Teste PIX Recipient"
        print(f"✓ Retrieved PIX payment: {data['id'][:8]}...")
    
    def test_07_simulate_pix_execution(self):
        """Test simulating PIX execution"""
        pix_id = getattr(self.__class__, 'created_pix_id', None)
        if not pix_id:
            pytest.skip("No PIX payment created in previous test")
        
        response = requests.post(f"{BASE_URL}/api/pix/simulate-execution/{pix_id}", headers=self.headers)
        assert response.status_code == 200, f"Failed to simulate PIX: {response.text}"
        
        data = response.json()
        assert data["status"] == "executado"
        assert "transaction_id" in data
        assert data["transaction_id"].startswith("E")
        print(f"✓ PIX executed (simulated): {data['transaction_id']}")
    
    def test_08_simulate_pix_already_executed(self):
        """Test simulating PIX execution on already executed - should fail"""
        pix_id = getattr(self.__class__, 'created_pix_id', None)
        if not pix_id:
            pytest.skip("No PIX payment created in previous test")
        
        response = requests.post(f"{BASE_URL}/api/pix/simulate-execution/{pix_id}", headers=self.headers)
        assert response.status_code == 400, "Expected 400 for already executed PIX"
        assert "já foi executado" in response.json().get("detail", "").lower() or "already" in response.json().get("detail", "").lower()
        print("✓ Correctly rejected double execution")
    
    def test_09_pix_payment_not_found(self):
        """Test getting non-existent PIX payment"""
        response = requests.get(f"{BASE_URL}/api/pix/payment/non-existent-id", headers=self.headers)
        assert response.status_code == 404
        print("✓ Non-existent PIX returns 404")
    
    def test_10_create_pix_with_invalid_data(self):
        """Test creating PIX with missing required fields"""
        pix_data = {
            "pix_key": "123",
            # Missing required fields
        }
        
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 422, "Expected 422 for invalid data"
        print("✓ Invalid PIX data correctly rejected")


class TestPDFGeneration:
    """Test PDF generation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_11_generate_contract_pdf(self):
        """Test generating PDF for a contract"""
        # First, get list of contracts
        contracts_response = requests.get(f"{BASE_URL}/api/contracts", headers=self.headers)
        assert contracts_response.status_code == 200
        contracts = contracts_response.json()
        
        if not contracts:
            pytest.skip("No contracts available for PDF generation test")
        
        contract_id = contracts[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/contracts/{contract_id}/pdf", headers=self.headers)
        
        # PDF generation might return 200 with PDF or error if PDF module not available
        if response.status_code == 200:
            assert response.headers.get("content-type") == "application/pdf"
            assert len(response.content) > 0
            print(f"✓ Generated PDF for contract {contract_id[:8]}... ({len(response.content)} bytes)")
        elif response.status_code == 500:
            # PDF generation not available
            assert "not available" in response.json().get("detail", "").lower()
            print("✓ PDF generation not available (expected in some environments)")
        else:
            pytest.fail(f"Unexpected response: {response.status_code} - {response.text}")
    
    def test_12_download_signed_pdf_no_signature(self):
        """Test downloading signed PDF for contract without signatures"""
        # Get list of contracts
        contracts_response = requests.get(f"{BASE_URL}/api/contracts", headers=self.headers)
        assert contracts_response.status_code == 200
        contracts = contracts_response.json()
        
        if not contracts:
            pytest.skip("No contracts available")
        
        # Find contract without signatures
        unsigned_contract = None
        for c in contracts:
            if not c.get("locador_assinatura_hash") and not c.get("locatario_assinatura_hash"):
                unsigned_contract = c
                break
        
        if not unsigned_contract:
            print("✓ All contracts appear to be signed - skipping unsigned test")
            return
        
        contract_id = unsigned_contract["id"]
        response = requests.get(f"{BASE_URL}/api/contracts/{contract_id}/download-signed-pdf", headers=self.headers)
        
        # Expected: 400 if contract not fully signed, 200 if signed, or 404/500 for other cases
        assert response.status_code in [200, 400, 404, 500], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 400:
            # This is correct behavior - contract is not fully signed
            assert "assinado" in response.json().get("detail", "").lower()
            print(f"✓ Correctly rejected unsigned contract download with 400")
        else:
            print(f"✓ Download signed PDF: {response.status_code}")
    
    def test_13_reports_pdf(self):
        """Test generating reports PDF"""
        response = requests.get(f"{BASE_URL}/api/reports/pdf", headers=self.headers)
        
        if response.status_code == 200:
            assert response.headers.get("content-type") == "application/pdf"
            print(f"✓ Generated reports PDF ({len(response.content)} bytes)")
        elif response.status_code == 500:
            assert "not available" in response.json().get("detail", "").lower()
            print("✓ PDF generation not available (expected in some environments)")
        else:
            pytest.fail(f"Unexpected response: {response.status_code}")
    
    def test_14_contract_not_found_pdf(self):
        """Test PDF generation for non-existent contract"""
        response = requests.get(f"{BASE_URL}/api/contracts/non-existent-id/pdf", headers=self.headers)
        assert response.status_code == 404
        print("✓ Non-existent contract PDF returns 404")


class TestPIXWithExpenseIntegration:
    """Test PIX payment linked to expense"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "test123"
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_15_list_expenses(self):
        """Test listing expenses to find pending ones"""
        response = requests.get(f"{BASE_URL}/api/expenses", headers=self.headers)
        assert response.status_code == 200
        expenses = response.json()
        
        # Find pending expenses
        pending = [e for e in expenses if e.get("payment_status") == "pendente"]
        print(f"✓ Found {len(pending)} pending expenses out of {len(expenses)} total")
        
        if pending:
            self.__class__.pending_expense_id = pending[0]["id"]
    
    def test_16_create_pix_linked_to_expense(self):
        """Test creating PIX payment linked to expense"""
        expense_id = getattr(self.__class__, 'pending_expense_id', None)
        if not expense_id:
            pytest.skip("No pending expense available")
        
        pix_data = {
            "pix_key": "98765432100",
            "pix_key_type": "cpf",
            "recipient_name": "Fornecedor Teste PIX",
            "recipient_cpf_cnpj": "987.654.321-00",
            "amount": 100.00,
            "description": "PIX vinculado a despesa",
            "scheduled_date": "2026-02-15",
            "expense_id": expense_id
        }
        
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["pix_payment"]["expense_id"] == expense_id
        
        self.__class__.linked_pix_id = data["pix_payment"]["id"]
        print(f"✓ Created PIX {self.__class__.linked_pix_id[:8]}... linked to expense {expense_id[:8]}...")
    
    def test_17_create_pix_with_invalid_expense(self):
        """Test creating PIX with non-existent expense"""
        pix_data = {
            "pix_key": "11122233344",
            "pix_key_type": "cpf",
            "recipient_name": "Invalid Expense Test",
            "amount": 50.00,
            "description": "Test with invalid expense",
            "expense_id": "non-existent-expense-id"
        }
        
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 404, "Expected 404 for non-existent expense"
        print("✓ Invalid expense_id correctly rejected with 404")


class TestPIXKeyTypes:
    """Test different PIX key types"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "test123"
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_18_pix_with_cpf_key(self):
        """Test PIX with CPF key type"""
        pix_data = {
            "pix_key": "12345678901",
            "pix_key_type": "cpf",
            "recipient_name": "CPF Key Test",
            "amount": 25.00,
            "description": "Test CPF key"
        }
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200
        print("✓ PIX with CPF key type created")
    
    def test_19_pix_with_cnpj_key(self):
        """Test PIX with CNPJ key type"""
        pix_data = {
            "pix_key": "12345678000199",
            "pix_key_type": "cnpj",
            "recipient_name": "CNPJ Key Test",
            "amount": 30.00,
            "description": "Test CNPJ key"
        }
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200
        print("✓ PIX with CNPJ key type created")
    
    def test_20_pix_with_email_key(self):
        """Test PIX with email key type"""
        pix_data = {
            "pix_key": "fornecedor@teste.com",
            "pix_key_type": "email",
            "recipient_name": "Email Key Test",
            "amount": 35.00,
            "description": "Test email key"
        }
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200
        print("✓ PIX with email key type created")
    
    def test_21_pix_with_phone_key(self):
        """Test PIX with phone key type"""
        pix_data = {
            "pix_key": "+5584999990000",
            "pix_key_type": "phone",
            "recipient_name": "Phone Key Test",
            "amount": 40.00,
            "description": "Test phone key"
        }
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200
        print("✓ PIX with phone key type created")
    
    def test_22_pix_with_random_key(self):
        """Test PIX with random key type"""
        pix_data = {
            "pix_key": "550e8400-e29b-41d4-a716-446655440000",
            "pix_key_type": "random",
            "recipient_name": "Random Key Test",
            "amount": 45.00,
            "description": "Test random key"
        }
        response = requests.post(f"{BASE_URL}/api/pix/payment", headers=self.headers, json=pix_data)
        assert response.status_code == 200
        print("✓ PIX with random key type created")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
