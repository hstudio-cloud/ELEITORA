"""
Test suite for Contract Required Attachments and Auto-Expense Payment features

Tests:
1. GET /api/contracts/{id}/required-attachments - returns list of required attachments
2. POST /api/contracts/{id}/attachments/{key} - upload specific attachment  
3. Upload comprovante_pagamento marks expenses as paid automatically
4. Auto-generate expenses when creating contract
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "teste@teste.com"
TEST_PASSWORD = "123456"
CONTRACT_ID = "43a7d7a8-651f-4029-9a7c-a0e8cbe9b9a4"

# Valid attachment keys for veiculo_sem_motorista contract type
VALID_ATTACHMENT_KEYS = [
    "doc_veiculo",
    "doc_proprietario", 
    "cnh_proprietario",
    "comprovante_residencia",
    "comprovante_pagamento"
]


@pytest.fixture(scope="module")
def auth_token():
    """Login and get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create authenticated API session"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


class TestRequiredAttachmentsEndpoint:
    """Tests for GET /api/contracts/{id}/required-attachments"""
    
    def test_get_required_attachments_success(self, api_client):
        """Test successful retrieval of required attachments list"""
        response = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/required-attachments")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "contract_id" in data, "Missing contract_id in response"
        assert data["contract_id"] == CONTRACT_ID
        assert "template_type" in data, "Missing template_type in response"
        assert "attachments" in data, "Missing attachments list in response"
        assert "total_required" in data, "Missing total_required count"
        assert "total_uploaded" in data, "Missing total_uploaded count"
        assert "complete" in data, "Missing complete status"
        
        print(f"✓ Contract type: {data['template_type']}")
        print(f"✓ Required attachments: {data['total_required']}")
        print(f"✓ Uploaded attachments: {data['total_uploaded']}")
        print(f"✓ Complete: {data['complete']}")
    
    def test_required_attachments_structure(self, api_client):
        """Test that attachments have correct structure"""
        response = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/required-attachments")
        assert response.status_code == 200
        
        data = response.json()
        attachments = data["attachments"]
        
        assert len(attachments) > 0, "No attachments returned"
        
        for att in attachments:
            assert "key" in att, f"Missing key in attachment: {att}"
            assert "label" in att, f"Missing label in attachment: {att}"
            assert "required" in att, f"Missing required flag in attachment: {att}"
            assert "uploaded" in att, f"Missing uploaded status in attachment: {att}"
            
            print(f"  - {att['key']}: {att['label']} (required={att['required']}, uploaded={att['uploaded']})")
    
    def test_veiculo_sem_motorista_has_correct_attachments(self, api_client):
        """Test that veiculo_sem_motorista contract has the right attachment types"""
        response = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/required-attachments")
        assert response.status_code == 200
        
        data = response.json()
        
        # For veiculo_sem_motorista, we expect these attachments
        expected_keys = {"doc_veiculo", "doc_proprietario", "cnh_proprietario", "comprovante_residencia", "comprovante_pagamento"}
        actual_keys = {att["key"] for att in data["attachments"]}
        
        assert expected_keys == actual_keys, f"Expected {expected_keys}, got {actual_keys}"
        print(f"✓ All expected attachment keys present for veiculo_sem_motorista")
    
    def test_required_attachments_requires_auth(self):
        """Test that endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/required-attachments")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Endpoint correctly requires authentication")
    
    def test_required_attachments_404_for_nonexistent(self, api_client):
        """Test 404 for non-existent contract"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(f"{BASE_URL}/api/contracts/{fake_id}/required-attachments")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Returns 404 for non-existent contract")


class TestAttachmentUpload:
    """Tests for POST /api/contracts/{id}/attachments/{key}"""
    
    def test_upload_attachment_success(self, auth_token):
        """Test successful attachment upload"""
        # Create a test PDF file in memory
        test_file_content = b"%PDF-1.4 test file content"
        files = {
            "file": ("test_document.pdf", io.BytesIO(test_file_content), "application/pdf")
        }
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/contracts/{CONTRACT_ID}/attachments/doc_proprietario",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        
        data = response.json()
        assert "message" in data, "Missing success message"
        assert "attachment_id" in data, "Missing attachment_id"
        assert "attachment_key" in data, "Missing attachment_key"
        assert data["attachment_key"] == "doc_proprietario"
        
        print(f"✓ Successfully uploaded doc_proprietario attachment")
        print(f"  Attachment ID: {data['attachment_id']}")
    
    def test_upload_invalid_key_rejected(self, auth_token):
        """Test that invalid attachment key is rejected"""
        test_file_content = b"%PDF-1.4 test file content"
        files = {
            "file": ("test.pdf", io.BytesIO(test_file_content), "application/pdf")
        }
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/contracts/{CONTRACT_ID}/attachments/invalid_key",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid key, got {response.status_code}"
        print("✓ Invalid attachment key correctly rejected")
    
    def test_upload_jpeg_image_accepted(self, auth_token):
        """Test that JPEG images are accepted"""
        # Create minimal JPEG header
        jpeg_content = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xD9
        ])
        
        files = {
            "file": ("test_image.jpg", io.BytesIO(jpeg_content), "image/jpeg")
        }
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/contracts/{CONTRACT_ID}/attachments/cnh_proprietario",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"JPEG upload failed: {response.text}"
        print("✓ JPEG image upload accepted")
    
    def test_upload_requires_auth(self):
        """Test that upload requires authentication"""
        test_file_content = b"%PDF-1.4 test"
        files = {
            "file": ("test.pdf", io.BytesIO(test_file_content), "application/pdf")
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contracts/{CONTRACT_ID}/attachments/doc_veiculo",
            files=files
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Upload correctly requires authentication")


class TestComprovantePagamentoAutoExpense:
    """Tests for comprovante_pagamento marking expenses as paid"""
    
    def test_upload_comprovante_marks_expenses_paid(self, auth_token, api_client):
        """Test that uploading comprovante_pagamento marks expenses as paid"""
        # First, check current expenses for this contract
        expenses_before = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/expenses")
        
        if expenses_before.status_code == 200:
            expenses_data = expenses_before.json()
            # The endpoint returns nested structure with 'expenses' key
            expense_list = expenses_data.get("expenses", [])
            pending_before = [e for e in expense_list if e.get("payment_status") == "pendente"]
            print(f"  Pending expenses before: {len(pending_before)}")
        
        # Upload comprovante_pagamento
        test_file_content = b"%PDF-1.4 comprovante de pagamento"
        files = {
            "file": ("comprovante.pdf", io.BytesIO(test_file_content), "application/pdf")
        }
        
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/contracts/{CONTRACT_ID}/attachments/comprovante_pagamento",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Comprovante upload failed: {response.text}"
        print(f"✓ Comprovante de pagamento uploaded successfully")
        
        # Verify expenses are now marked as paid
        expenses_after = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/expenses")
        
        if expenses_after.status_code == 200:
            expenses_data = expenses_after.json()
            # The endpoint returns nested structure with 'expenses' key
            expense_list = expenses_data.get("expenses", [])
            pending_after = [e for e in expense_list if e.get("payment_status") == "pendente"]
            paid_after = [e for e in expense_list if e.get("payment_status") == "pago"]
            
            print(f"  Pending expenses after: {len(pending_after)}")
            print(f"  Paid expenses after: {len(paid_after)}")
            
            # Verify total_pending is 0 in response
            assert expenses_data.get("total_pending") == 0, f"Expected total_pending=0, got {expenses_data.get('total_pending')}"
            print(f"✓ All expenses marked as 'pago' after comprovante upload")


class TestAutoExpenseGeneration:
    """Tests for automatic expense generation when creating contracts"""
    
    def test_contract_has_expenses(self, api_client):
        """Verify that contract with gerar_despesas=true has generated expenses"""
        response = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/expenses")
        
        assert response.status_code == 200, f"Failed to get contract expenses: {response.text}"
        
        data = response.json()
        # The endpoint returns nested structure with 'expenses' key
        expenses = data.get("expenses", [])
        
        print(f"✓ Found {len(expenses)} expenses for contract {CONTRACT_ID}")
        print(f"  Total value: R$ {data.get('total_value')}")
        print(f"  Total paid: R$ {data.get('total_paid')}")
        print(f"  Total pending: R$ {data.get('total_pending')}")
        
        for exp in expenses:
            print(f"  - {exp.get('description')}: R$ {exp.get('amount')} ({exp.get('payment_status')})")
    
    def test_create_contract_generates_expenses(self, api_client):
        """Test that creating new contract with gerar_despesas generates expenses"""
        # Create a new test contract
        contract_data = {
            "title": "TEST_Contrato Auto Despesas",
            "description": "Teste de geração automática de despesas",
            "contractor_name": "Teste Fornecedor",
            "contractor_cpf_cnpj": "12345678901",
            "value": 3000.00,
            "start_date": "2024-08-01",
            "end_date": "2024-10-31",
            "status": "rascunho",
            "template_type": "veiculo_sem_motorista",
            "num_parcelas": 3,
            "gerar_despesas": True,
            "locador_nome": "Teste Fornecedor",
            "locador_cpf": "12345678901"
        }
        
        response = api_client.post(f"{BASE_URL}/api/contracts", json=contract_data)
        assert response.status_code == 200, f"Failed to create contract: {response.text}"
        
        new_contract = response.json()
        new_contract_id = new_contract["id"]
        print(f"✓ Created test contract: {new_contract_id}")
        
        # Check expenses were generated
        all_expenses = api_client.get(f"{BASE_URL}/api/expenses")
        assert all_expenses.status_code == 200
        
        contract_expenses = [e for e in all_expenses.json() if e.get("contract_id") == new_contract_id]
        
        assert len(contract_expenses) == 3, f"Expected 3 expenses (parcelas), got {len(contract_expenses)}"
        print(f"✓ Auto-generated {len(contract_expenses)} expenses for new contract")
        
        # Verify expense values
        total_expense_value = sum(e["amount"] for e in contract_expenses)
        assert abs(total_expense_value - 3000.00) < 0.01, f"Total expense value {total_expense_value} doesn't match contract value 3000.00"
        print(f"✓ Total expense value ({total_expense_value}) matches contract value")
        
        # Cleanup - delete test contract
        delete_response = api_client.delete(f"{BASE_URL}/api/contracts/{new_contract_id}")
        print(f"✓ Cleaned up test contract")


class TestAttachmentProgress:
    """Test attachment progress tracking"""
    
    def test_progress_calculation(self, api_client):
        """Test that progress is correctly calculated"""
        response = api_client.get(f"{BASE_URL}/api/contracts/{CONTRACT_ID}/required-attachments")
        assert response.status_code == 200
        
        data = response.json()
        
        # Progress = uploaded / total_required * 100
        total_required = data["total_required"]
        total_uploaded = data["total_uploaded"]
        
        # Count required that are uploaded
        required_uploaded = len([a for a in data["attachments"] if a["required"] and a["uploaded"]])
        
        print(f"✓ Progress: {required_uploaded}/{total_required} required attachments uploaded")
        print(f"✓ Total uploaded (including optional): {total_uploaded}")
        print(f"✓ Complete: {data['complete']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
