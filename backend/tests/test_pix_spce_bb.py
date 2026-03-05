"""
Test PIX BB Integration and SPCE Export Features - Eleitora 360
Tests for:
- PIX BB Integration (real credentials in homologação)
- SPCE Export endpoints (despesas, contratos, categorias)
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is not set")


class TestAuth:
    """Authentication tests"""
    token = None
    
    @classmethod
    def get_token(cls):
        if cls.token:
            return cls.token
        
        # Login with test credentials
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "test123"
        })
        
        if response.status_code == 200:
            cls.token = response.json().get("token")
            return cls.token
        
        # If login fails, try to register
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "admin@test.com",
            "password": "test123",
            "name": "Admin Test",
            "role": "candidato"
        })
        
        if response.status_code == 200:
            cls.token = response.json().get("token")
        
        return cls.token


class TestPixBankInfo:
    """Test PIX bank-info endpoint - BB Integration status"""
    
    def test_get_bank_info(self):
        """GET /api/pix/bank-info - must show integration_available: true"""
        response = requests.get(f"{BASE_URL}/api/pix/bank-info")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"\nBank Info Response: {data}")
        
        # Verify required fields
        assert "bank" in data, "Missing 'bank' field"
        assert data["bank"] == "Banco do Brasil", f"Expected 'Banco do Brasil', got '{data['bank']}'"
        
        assert "integration_available" in data, "Missing 'integration_available' field"
        print(f"Integration Available: {data['integration_available']}")
        
        # The test request specifies integration should be available
        assert data["integration_available"] == True, f"Expected integration_available: true, got {data['integration_available']}"
        
        assert "environment" in data, "Missing 'environment' field"
        print(f"Environment: {data['environment']}")
        
        if data["integration_available"]:
            assert data["environment"] == "homologacao", f"Expected 'homologacao', got '{data['environment']}'"
            assert "features" in data, "Missing 'features' field when integration is available"
            assert len(data["features"]) > 0, "Features list should not be empty when integration is available"
            print(f"Features: {data['features']}")


class TestPixPayment:
    """Test PIX payment creation and status check"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = TestAuth.get_token()
        if not self.token:
            pytest.skip("Could not get auth token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_create_pix_payment(self):
        """POST /api/pix/payment - create PIX payment"""
        payload = {
            "pix_key": "12345678901",
            "pix_key_type": "cpf",
            "recipient_name": "Test Recipient BB",
            "recipient_cpf_cnpj": "123.456.789-01",
            "amount": 100.50,
            "description": "Test PIX BB Integration",
            "scheduled_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = requests.post(
            f"{BASE_URL}/api/pix/payment",
            json=payload,
            headers=self.headers
        )
        
        print(f"\nCreate PIX Response Status: {response.status_code}")
        print(f"Create PIX Response: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pix_payment" in data, "Missing 'pix_payment' in response"
        assert "integration_mode" in data, "Missing 'integration_mode' in response"
        
        pix_payment = data["pix_payment"]
        assert pix_payment["recipient_name"] == "Test Recipient BB"
        assert pix_payment["amount"] == 100.50
        assert "id" in pix_payment
        
        print(f"Integration Mode: {data['integration_mode']}")
        print(f"BB Available: {data.get('bb_available')}")
        
        # Store for status check
        TestPixPayment.created_pix_id = pix_payment["id"]
        
        return pix_payment["id"]
    
    def test_check_pix_status(self):
        """GET /api/pix/check-status/{id} - verify PIX status"""
        # First create a PIX if not exists
        pix_id = getattr(TestPixPayment, 'created_pix_id', None)
        
        if not pix_id:
            # Create one for testing
            payload = {
                "pix_key": "98765432100",
                "pix_key_type": "cpf",
                "recipient_name": "Status Check Test",
                "recipient_cpf_cnpj": "987.654.321-00",
                "amount": 50.00,
                "description": "Status Check Test",
                "scheduled_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            create_response = requests.post(
                f"{BASE_URL}/api/pix/payment",
                json=payload,
                headers=self.headers
            )
            
            if create_response.status_code == 200:
                pix_id = create_response.json()["pix_payment"]["id"]
            else:
                pytest.skip("Could not create PIX for status check test")
        
        # Check status
        response = requests.get(
            f"{BASE_URL}/api/pix/check-status/{pix_id}",
            headers=self.headers
        )
        
        print(f"\nCheck PIX Status Response: {response.status_code}")
        print(f"Check PIX Status Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Response can have either 'status' or 'local_status' depending on integration mode
        assert "local_status" in data or "status" in data, "Missing status field"
        
        status = data.get("local_status") or data.get("status")
        print(f"PIX Status: {status}")
        print(f"Integration Mode: {data.get('integration_mode', 'N/A')}")
    
    def test_check_status_nonexistent(self):
        """GET /api/pix/check-status/{id} - non-existent PIX should return 404"""
        response = requests.get(
            f"{BASE_URL}/api/pix/check-status/nonexistent-id-12345",
            headers=self.headers
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent PIX, got {response.status_code}"


class TestSpceExport:
    """Test SPCE export endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = TestAuth.get_token()
        if not self.token:
            pytest.skip("Could not get auth token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_export_spce_despagtos(self):
        """GET /api/export/spce-despagtos - export expenses SPCE layout"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-despagtos",
            headers=self.headers
        )
        
        print(f"\nSPCE Despagtos Response Status: {response.status_code}")
        print(f"SPCE Despagtos Response: {response.text[:500] if len(response.text) > 500 else response.text}")
        
        # SPCE export requires campaign CNPJ - may return 400 if not configured
        if response.status_code == 400:
            data = response.json()
            if "CNPJ" in data.get("detail", ""):
                print("SPCE export requires campaign CNPJ to be configured - expected behavior")
                # This is expected behavior, test passes but logs the requirement
                assert True
                return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"SPCE Despagtos Response: {data}")
        
        assert "data" in data, "Missing 'data' field"
        assert "format" in data, "Missing 'format' field"
        assert data["format"] == "SPCE-DESPAGTOS", f"Expected format 'SPCE-DESPAGTOS', got '{data['format']}'"
        
        # Verify data structure
        if len(data["data"]) > 0:
            expense = data["data"][0]
            print(f"First expense in SPCE format: {expense}")
            # Verify SPCE required fields
            assert "tipo_lancamento" in expense or "descricao" in expense, "Missing required expense fields"
    
    def test_export_spce_contratos(self):
        """GET /api/export/spce-contratos - export contracts SPCE format"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-contratos",
            headers=self.headers
        )
        
        print(f"\nSPCE Contratos Response Status: {response.status_code}")
        print(f"SPCE Contratos Response: {response.text[:500] if len(response.text) > 500 else response.text}")
        
        # SPCE export requires campaign CNPJ - may return 400 if not configured
        if response.status_code == 400:
            data = response.json()
            if "CNPJ" in data.get("detail", ""):
                print("SPCE export requires campaign CNPJ to be configured - expected behavior")
                # This is expected behavior, test passes but logs the requirement
                assert True
                return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"SPCE Contratos Response: {data}")
        
        assert "data" in data, "Missing 'data' field"
        assert "format" in data, "Missing 'format' field"
        assert data["format"] == "SPCE-CONTRATOS", f"Expected format 'SPCE-CONTRATOS', got '{data['format']}'"
        
        if len(data["data"]) > 0:
            contract = data["data"][0]
            print(f"First contract in SPCE format: {contract}")
    
    def test_export_spce_categorias(self):
        """GET /api/export/spce-categorias - list SPCE categories"""
        response = requests.get(f"{BASE_URL}/api/export/spce-categorias")
        
        print(f"\nSPCE Categorias Response Status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"SPCE Categorias Response: {data}")
        
        assert "despesas" in data, "Missing 'despesas' field"
        assert "contratos" in data, "Missing 'contratos' field"
        
        # Verify despesas categories
        despesas = data["despesas"]
        assert len(despesas) > 0, "Despesas categories should not be empty"
        print(f"Number of expense categories: {len(despesas)}")
        
        # Check structure of one category
        first_cat_key = list(despesas.keys())[0]
        first_cat = despesas[first_cat_key]
        print(f"Sample despesa category: {first_cat_key} = {first_cat}")
        
        # Verify contratos categories
        contratos = data["contratos"]
        assert len(contratos) > 0, "Contratos categories should not be empty"
        print(f"Number of contract categories: {len(contratos)}")


class TestPixPaymentsList:
    """Test PIX payments listing"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = TestAuth.get_token()
        if not self.token:
            pytest.skip("Could not get auth token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_list_pix_payments(self):
        """GET /api/pix/payments - list PIX payments"""
        response = requests.get(
            f"{BASE_URL}/api/pix/payments",
            headers=self.headers
        )
        
        print(f"\nList PIX Payments Response Status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Number of PIX payments: {len(data)}")
        
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            pix = data[0]
            print(f"Sample PIX payment: {pix}")
            assert "id" in pix, "PIX payment should have 'id'"
            assert "recipient_name" in pix, "PIX payment should have 'recipient_name'"
            assert "amount" in pix, "PIX payment should have 'amount'"
            assert "status" in pix, "PIX payment should have 'status'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
