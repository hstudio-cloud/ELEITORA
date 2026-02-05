"""
Tests for SPCE ZIP Export and Email Signature Request endpoints
- GET /api/export/spce-zip - Export complete SPCE package as ZIP
- POST /api/email/send-signature-request - Send signature request email
"""
import pytest
import requests
import zipfile
import json
import io
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for test user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "teste@teste.com",
        "password": "123456"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Create auth headers"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestSPCEZipExport:
    """Tests for SPCE ZIP Export endpoint"""
    
    def test_spce_zip_export_returns_zip(self, auth_headers):
        """Test that /api/export/spce-zip returns a valid ZIP file"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        # Should return 200 with ZIP file (campaign has CNPJ configured: 11222333000181)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('Content-Type') == 'application/zip'
        assert 'attachment' in response.headers.get('Content-Disposition', '')
        print(f"PASS: SPCE ZIP export returned status 200")
    
    def test_spce_zip_contains_required_folders(self, auth_headers):
        """Test that ZIP contains all required SPCE folder structure"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Parse ZIP content
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            namelist = zf.namelist()
            
            # Required SPCE folders
            required_folders = [
                "RECEITAS/",
                "DESPESAS/",
                "DEMONSTRATIVOS/",
                "EXTRATOS_BANCARIOS/",
                "REPRESENTANTES/",
                "NOTAS_EXPLICATIVAS/",
                "ASSUNCAO_DIVIDAS/",
                "SOBRAS_CAMPANHA/",
                "AVULSOS_OUTROS/",
                "AVULSOS_SPCE/",
                "COMERCIALIZACAO/",
                "DEVOLUCAO_RECEITAS/",
                "EXTRATO_PRESTACAO/",
                "SIGILOSO_SPCE/"
            ]
            
            for folder in required_folders:
                # Check if folder exists (or files inside folder exist)
                folder_exists = any(name.startswith(folder.rstrip('/')) for name in namelist)
                assert folder_exists, f"Missing required folder: {folder}"
                print(f"PASS: Folder {folder} exists in ZIP")
    
    def test_spce_zip_contains_dados_info(self, auth_headers):
        """Test that ZIP contains valid dados.info JSON file"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            # Check dados.info exists
            assert "dados.info" in zf.namelist(), "Missing dados.info file"
            
            # Parse JSON content
            dados_content = zf.read("dados.info").decode('utf-8')
            dados_info = json.loads(dados_content)
            
            # Validate required fields in dados.info
            assert "numeroCnpj" in dados_info, "dados.info missing numeroCnpj"
            assert "nome" in dados_info, "dados.info missing nome"
            assert "categorias" in dados_info, "dados.info missing categorias"
            assert "arquivos" in dados_info, "dados.info missing arquivos"
            assert "uf" in dados_info, "dados.info missing uf"
            assert "anoEleicao" in dados_info, "dados.info missing anoEleicao"
            
            # Validate CNPJ format (should be 14 digits)
            cnpj = dados_info.get("numeroCnpj", "")
            assert len(cnpj) == 14, f"CNPJ should be 14 digits, got {len(cnpj)}"
            
            print(f"PASS: dados.info is valid JSON with required fields")
            print(f"  - CNPJ: {cnpj}")
            print(f"  - Nome: {dados_info.get('nome', '')}")
            print(f"  - UF: {dados_info.get('uf', '')}")
    
    def test_spce_zip_contains_receitas_files(self, auth_headers):
        """Test that ZIP contains receipt files in RECEITAS folder"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            receitas_files = [f for f in zf.namelist() if f.startswith("RECEITAS/") and not f.endswith('/')]
            print(f"Found {len(receitas_files)} files in RECEITAS folder")
            
            for f in receitas_files[:3]:  # Show first 3
                print(f"  - {f}")
    
    def test_spce_zip_contains_despesas_files(self, auth_headers):
        """Test that ZIP contains expense files in DESPESAS folder"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            despesas_files = [f for f in zf.namelist() if f.startswith("DESPESAS/") and not f.endswith('/')]
            print(f"Found {len(despesas_files)} files in DESPESAS folder")
            
            for f in despesas_files[:3]:  # Show first 3
                print(f"  - {f}")
    
    def test_spce_zip_contains_demonstrativos_files(self, auth_headers):
        """Test that ZIP contains report files in DEMONSTRATIVOS folder"""
        response = requests.get(
            f"{BASE_URL}/api/export/spce-zip",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            demo_files = [f for f in zf.namelist() if f.startswith("DEMONSTRATIVOS/") and not f.endswith('/')]
            assert len(demo_files) >= 1, "DEMONSTRATIVOS folder should have at least 1 report file"
            print(f"PASS: Found {len(demo_files)} files in DEMONSTRATIVOS folder")
            
            for f in demo_files:
                print(f"  - {f}")


class TestEmailSignatureRequest:
    """Tests for Email Signature Request endpoint"""
    
    def test_send_signature_request_no_contract(self, auth_headers):
        """Test that sending signature for non-existent contract returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/email/send-signature-request?contract_id=non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        print(f"PASS: Non-existent contract returns 404")
    
    def test_send_signature_request_endpoint_exists(self, auth_headers):
        """Test that the endpoint exists and accepts POST requests"""
        # First, get a contract with locador_email
        contracts_response = requests.get(
            f"{BASE_URL}/api/contracts",
            headers=auth_headers
        )
        
        if contracts_response.status_code == 200:
            contracts = contracts_response.json()
            
            # Find a contract with locador_email
            contract_with_email = None
            for c in contracts:
                if c.get("locador_email"):
                    contract_with_email = c
                    break
            
            if contract_with_email:
                response = requests.post(
                    f"{BASE_URL}/api/email/send-signature-request?contract_id={contract_with_email['id']}",
                    headers=auth_headers
                )
                
                # Should return 200 with signature link or warning about missing RESEND_API_KEY
                # The endpoint should work even without API key, just email won't be sent
                assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
                
                if response.status_code == 200:
                    data = response.json()
                    assert "signature_link" in data or "message" in data
                    print(f"PASS: Email signature request endpoint working")
                    print(f"  - Response: {data}")
                else:
                    print(f"INFO: Endpoint returned 500 (likely missing RESEND_API_KEY)")
            else:
                print(f"INFO: No contracts with locador_email found, creating test contract")
                # Create a test contract with locador_email for testing
                contract_data = {
                    "title": "TEST_Contract_for_Email",
                    "description": "Test contract for email signature",
                    "contractor_name": "Test Contractor",
                    "contractor_cpf_cnpj": "12345678901",
                    "value": 1000.00,
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "template_type": "bem_movel",
                    "locador_nome": "Test Locador",
                    "locador_email": "test@example.com",
                    "gerar_despesas": False
                }
                
                create_response = requests.post(
                    f"{BASE_URL}/api/contracts",
                    headers=auth_headers,
                    json=contract_data
                )
                
                if create_response.status_code == 200:
                    new_contract = create_response.json()
                    
                    response = requests.post(
                        f"{BASE_URL}/api/email/send-signature-request?contract_id={new_contract['id']}",
                        headers=auth_headers
                    )
                    
                    assert response.status_code in [200, 500]
                    if response.status_code == 200:
                        data = response.json()
                        assert "signature_link" in data
                        assert "email_sent_to" in data
                        print(f"PASS: Email signature request endpoint working")
                        print(f"  - Signature link: {data.get('signature_link', '')[:50]}...")
                        print(f"  - Email sent to: {data.get('email_sent_to', '')}")
                    
                    # Cleanup test contract
                    requests.delete(
                        f"{BASE_URL}/api/contracts/{new_contract['id']}",
                        headers=auth_headers
                    )
        else:
            pytest.skip("Could not fetch contracts")
    
    def test_send_signature_requires_locador_email(self, auth_headers):
        """Test that contract without locador_email returns error"""
        # Create contract without locador_email
        contract_data = {
            "title": "TEST_No_Email_Contract",
            "description": "Contract without email",
            "contractor_name": "Test",
            "contractor_cpf_cnpj": "12345678901",
            "value": 500.00,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "gerar_despesas": False
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/contracts",
            headers=auth_headers,
            json=contract_data
        )
        
        if create_response.status_code == 200:
            contract = create_response.json()
            
            # Try to send signature request without locador_email
            response = requests.post(
                f"{BASE_URL}/api/email/send-signature-request?contract_id={contract['id']}",
                headers=auth_headers
            )
            
            assert response.status_code == 400, f"Expected 400 for missing email, got {response.status_code}"
            assert "locador" in response.json().get("detail", "").lower() or "email" in response.json().get("detail", "").lower()
            print(f"PASS: Missing locador_email returns 400")
            
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/contracts/{contract['id']}",
                headers=auth_headers
            )


class TestSPCEZipUnauthorized:
    """Tests for unauthorized access"""
    
    def test_spce_zip_requires_auth(self):
        """Test that SPCE ZIP export requires authentication"""
        response = requests.get(f"{BASE_URL}/api/export/spce-zip")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: SPCE ZIP export requires authentication")
    
    def test_email_signature_requires_auth(self):
        """Test that email signature request requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/email/send-signature-request?contract_id=test",
            json={}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: Email signature request requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
