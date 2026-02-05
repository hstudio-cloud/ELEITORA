"""
Backend API Tests for Upload Features - Electoral ERP Platform
Tests: Receipt uploads, contract expenses auto-generation, payment status changes
New features: Attach receipts to expenses/revenues/contracts, auto-status change to 'pago'
"""
import pytest
import requests
import os
import io
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "teste@teste.com"
TEST_USER_PASSWORD = "123456"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for all tests in this module"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Login failed - skipping upload feature tests")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestExpenseReceiptUpload:
    """Tests for expense receipt upload with auto-payment status change"""
    
    def test_create_expense_and_upload_receipt_marks_as_paid(self, headers):
        """Test: Uploading receipt to expense changes status to 'pago'"""
        # Step 1: Create an expense with pendente status
        expense_data = {
            "description": "TEST_Despesa para Upload",
            "amount": 500.00,
            "category": "publicidade",
            "supplier_name": "Fornecedor Upload Test",
            "supplier_cpf_cnpj": "12345678000190",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_status": "pendente"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/expenses",
            json=expense_data,
            headers=headers
        )
        assert create_response.status_code == 200, f"Create expense failed: {create_response.text}"
        expense = create_response.json()
        expense_id = expense["id"]
        assert expense.get("payment_status") == "pendente", "Initial status should be pendente"
        print(f"Created expense {expense_id} with status: {expense.get('payment_status')}")
        
        # Step 2: Upload a receipt (simulated PNG file)
        # Create a simple PNG-like binary content
        fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Minimal PNG header
        files = {'file': ('comprovante.png', io.BytesIO(fake_png), 'image/png')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        upload_data = upload_response.json()
        
        # Step 3: Verify status changed to 'pago'
        assert "expense" in upload_data
        assert upload_data["expense"]["payment_status"] == "pago", \
            f"Expected payment_status='pago', got: {upload_data['expense'].get('payment_status')}"
        assert upload_data["expense"]["attachment_id"] is not None, "attachment_id should be set"
        print(f"SUCCESS: Expense status changed to 'pago' after receipt upload")
        
        # Step 4: Verify by GET request
        get_response = requests.get(
            f"{BASE_URL}/api/expenses/{expense_id}",
            headers=headers
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["payment_status"] == "pago"
        assert fetched["attachment_id"] is not None
        print(f"Verified: GET expense shows status='pago' and attachment_id={fetched['attachment_id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)
        print(f"Cleaned up test expense {expense_id}")
    
    def test_upload_invalid_file_type_rejected(self, headers):
        """Test: Invalid file types are rejected"""
        # Create expense
        expense_data = {
            "description": "TEST_Despesa para teste de tipo de arquivo",
            "amount": 100.00,
            "category": "publicidade",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_status": "pendente"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/expenses",
            json=expense_data,
            headers=headers
        )
        expense_id = create_response.json()["id"]
        
        # Try to upload invalid file type (executable)
        fake_exe = b'MZ' + b'\x00' * 100  # EXE header
        files = {'file': ('file.exe', io.BytesIO(fake_exe), 'application/x-msdownload')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 400, \
            f"Expected 400 for invalid file type, got: {upload_response.status_code}"
        print(f"SUCCESS: Invalid file type (EXE) rejected with status 400")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)
    
    def test_upload_pdf_accepted(self, headers):
        """Test: PDF files are accepted"""
        # Create expense
        expense_data = {
            "description": "TEST_Despesa para teste de PDF",
            "amount": 200.00,
            "category": "servicos_terceiros",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "payment_status": "pendente"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/expenses",
            json=expense_data,
            headers=headers
        )
        expense_id = create_response.json()["id"]
        
        # Upload PDF
        fake_pdf = b'%PDF-1.4\n' + b'\x00' * 100  # Minimal PDF header
        files = {'file': ('comprovante.pdf', io.BytesIO(fake_pdf), 'application/pdf')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200, f"PDF upload failed: {upload_response.text}"
        print(f"SUCCESS: PDF file accepted")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)


class TestRevenueReceiptUpload:
    """Tests for revenue receipt upload"""
    
    def test_upload_receipt_to_revenue(self, headers):
        """Test: Uploading receipt to revenue"""
        # Create revenue
        revenue_data = {
            "description": "TEST_Receita para Upload",
            "amount": 1000.00,
            "category": "doacao_pf",
            "donor_name": "Doador Teste",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/revenues",
            json=revenue_data,
            headers=headers
        )
        assert create_response.status_code == 200
        revenue_id = create_response.json()["id"]
        print(f"Created revenue {revenue_id}")
        
        # Upload receipt
        fake_jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 100  # JPEG header
        files = {'file': ('recibo.jpg', io.BytesIO(fake_jpeg), 'image/jpeg')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/revenues/{revenue_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        upload_data = upload_response.json()
        
        # Verify attachment
        assert "revenue" in upload_data
        assert upload_data["revenue"]["attachment_id"] is not None
        print(f"SUCCESS: Receipt attached to revenue, attachment_id={upload_data['revenue']['attachment_id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/revenues/{revenue_id}", headers=headers)


class TestContractExpensesAutoGeneration:
    """Tests for automatic expense generation from contracts"""
    
    def test_create_contract_generates_expenses(self, headers):
        """Test: Creating a contract with gerar_despesas=True generates expenses"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        contract_data = {
            "title": "TEST_Contrato com Parcelas",
            "description": "Contrato para teste de geração automática de despesas",
            "contractor_name": "Fornecedor Teste Contrato",
            "contractor_cpf_cnpj": "12345678000190",
            "value": 10000.00,
            "start_date": start_date,
            "end_date": end_date,
            "status": "rascunho",
            "num_parcelas": 2,
            "gerar_despesas": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/contracts",
            json=contract_data,
            headers=headers
        )
        assert create_response.status_code == 200, f"Create contract failed: {create_response.text}"
        contract = create_response.json()
        contract_id = contract["id"]
        print(f"Created contract {contract_id}")
        
        # Get contract expenses
        expenses_response = requests.get(
            f"{BASE_URL}/api/contracts/{contract_id}/expenses",
            headers=headers
        )
        assert expenses_response.status_code == 200, f"Get expenses failed: {expenses_response.text}"
        expenses_data = expenses_response.json()
        
        # Verify expenses were generated
        assert "expenses" in expenses_data
        expenses = expenses_data["expenses"]
        assert len(expenses) == 2, f"Expected 2 expenses (parcelas), got: {len(expenses)}"
        
        # Verify expense values (R$ 10.000 / 2 parcelas = R$ 5.000 each)
        for i, expense in enumerate(expenses):
            assert expense["amount"] == 5000.00, f"Expected amount 5000.00, got: {expense['amount']}"
            assert expense["payment_status"] == "pendente", "New expenses should be pendente"
            assert expense["contract_id"] == contract_id
            print(f"Expense {i+1}: {expense['description']}, amount={expense['amount']}, status={expense['payment_status']}")
        
        print(f"SUCCESS: Contract created with {len(expenses)} auto-generated expenses")
        
        # Cleanup - delete contract and generated expenses
        for expense in expenses:
            requests.delete(f"{BASE_URL}/api/expenses/{expense['id']}", headers=headers)
        requests.delete(f"{BASE_URL}/api/contracts/{contract_id}", headers=headers)
        print(f"Cleaned up contract and expenses")
    
    def test_contract_expenses_show_payment_summary(self, headers):
        """Test: Contract expenses endpoint shows payment summary"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        contract_data = {
            "title": "TEST_Contrato para Resumo",
            "description": "Teste de resumo de pagamentos",
            "contractor_name": "Fornecedor Resumo",
            "contractor_cpf_cnpj": "98765432000110",
            "value": 6000.00,
            "start_date": start_date,
            "end_date": end_date,
            "status": "rascunho",
            "num_parcelas": 3,
            "gerar_despesas": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/contracts",
            json=contract_data,
            headers=headers
        )
        contract_id = create_response.json()["id"]
        
        # Get expenses and verify summary
        expenses_response = requests.get(
            f"{BASE_URL}/api/contracts/{contract_id}/expenses",
            headers=headers
        )
        expenses_data = expenses_response.json()
        
        assert "total_value" in expenses_data
        assert "total_paid" in expenses_data
        assert "total_pending" in expenses_data
        assert expenses_data["total_value"] == 6000.00
        assert expenses_data["total_pending"] == 6000.00  # All pendente
        assert expenses_data["total_paid"] == 0.0
        print(f"Contract summary: total={expenses_data['total_value']}, paid={expenses_data['total_paid']}, pending={expenses_data['total_pending']}")
        
        # Cleanup
        for expense in expenses_data["expenses"]:
            requests.delete(f"{BASE_URL}/api/expenses/{expense['id']}", headers=headers)
        requests.delete(f"{BASE_URL}/api/contracts/{contract_id}", headers=headers)


class TestContractDocumentUpload:
    """Tests for contract document upload"""
    
    def test_upload_document_to_contract(self, headers):
        """Test: Uploading document to contract"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        contract_data = {
            "title": "TEST_Contrato para Upload Doc",
            "description": "Teste de upload de documento",
            "contractor_name": "Fornecedor Doc",
            "contractor_cpf_cnpj": "11222333000181",
            "value": 2000.00,
            "start_date": start_date,
            "end_date": end_date,
            "status": "rascunho",
            "gerar_despesas": False  # Don't generate expenses for this test
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/contracts",
            json=contract_data,
            headers=headers
        )
        contract_id = create_response.json()["id"]
        print(f"Created contract {contract_id}")
        
        # Upload document
        fake_pdf = b'%PDF-1.4\n' + b'\x00' * 100
        files = {'file': ('contrato_assinado.pdf', io.BytesIO(fake_pdf), 'application/pdf')}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/contracts/{contract_id}/attach",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        upload_data = upload_response.json()
        
        assert "contract" in upload_data
        assert upload_data["contract"]["attachment_id"] is not None
        print(f"SUCCESS: Document attached to contract, attachment_id={upload_data['contract']['attachment_id']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/contracts/{contract_id}", headers=headers)


class TestExpenseStatusColumn:
    """Tests for expense payment status (pendente/pago)"""
    
    def test_expense_list_includes_payment_status(self, headers):
        """Test: Expense list includes payment_status field"""
        response = requests.get(
            f"{BASE_URL}/api/expenses",
            headers=headers
        )
        assert response.status_code == 200
        expenses = response.json()
        
        if expenses:
            # Check that all expenses have payment_status field
            for expense in expenses:
                assert "payment_status" in expense, \
                    f"Expense {expense.get('id')} missing payment_status"
                assert expense["payment_status"] in ["pendente", "pago", None], \
                    f"Invalid payment_status: {expense['payment_status']}"
            
            # Count statuses
            pendente_count = sum(1 for e in expenses if e.get("payment_status") == "pendente")
            pago_count = sum(1 for e in expenses if e.get("payment_status") == "pago")
            print(f"Expenses status: {pendente_count} pendente, {pago_count} pago, total {len(expenses)}")
        else:
            print("No expenses found to verify status")


class TestFileTypeValidation:
    """Tests for allowed file types validation (JPEG, PNG, PDF only)"""
    
    def test_allowed_jpeg(self, headers):
        """Test: JPEG files are accepted"""
        expense_data = {
            "description": "TEST_File Type JPEG",
            "amount": 100.00,
            "category": "outros",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=headers)
        expense_id = create_response.json()["id"]
        
        files = {'file': ('test.jpg', io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 50), 'image/jpeg')}
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200
        print("SUCCESS: JPEG accepted")
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)
    
    def test_allowed_png(self, headers):
        """Test: PNG files are accepted"""
        expense_data = {
            "description": "TEST_File Type PNG",
            "amount": 100.00,
            "category": "outros",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=headers)
        expense_id = create_response.json()["id"]
        
        files = {'file': ('test.png', io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50), 'image/png')}
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200
        print("SUCCESS: PNG accepted")
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)
    
    def test_allowed_pdf(self, headers):
        """Test: PDF files are accepted"""
        expense_data = {
            "description": "TEST_File Type PDF",
            "amount": 100.00,
            "category": "outros",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=headers)
        expense_id = create_response.json()["id"]
        
        files = {'file': ('test.pdf', io.BytesIO(b'%PDF-1.4\n' + b'\x00' * 50), 'application/pdf')}
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 200
        print("SUCCESS: PDF accepted")
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)
    
    def test_rejected_gif(self, headers):
        """Test: GIF files are rejected"""
        expense_data = {
            "description": "TEST_File Type GIF",
            "amount": 100.00,
            "category": "outros",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        create_response = requests.post(f"{BASE_URL}/api/expenses", json=expense_data, headers=headers)
        expense_id = create_response.json()["id"]
        
        files = {'file': ('test.gif', io.BytesIO(b'GIF89a' + b'\x00' * 50), 'image/gif')}
        upload_response = requests.post(
            f"{BASE_URL}/api/expenses/{expense_id}/attach-receipt",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 400
        print("SUCCESS: GIF rejected (400)")
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
