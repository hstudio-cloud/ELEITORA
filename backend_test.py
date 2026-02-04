import requests
import sys
import json
from datetime import datetime

class ContractSystemTester:
    def __init__(self, base_url="https://voto-contabil.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.campaign_id = None
        self.contract_id = None
        self.signature_token = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text}")

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health"""
        success, _ = self.run_test("Health Check", "GET", "", 200)
        return success

    def test_register_user(self):
        """Test user registration"""
        user_data = {
            "email": "test@eleitora.com",
            "password": "123456",
            "name": "Test User",
            "role": "candidato",
            "cpf": "12345678901",
            "phone": "84999999999"
        }
        
        success, response = self.run_test("User Registration", "POST", "auth/register", 200, user_data)
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_login(self):
        """Test user login"""
        login_data = {
            "email": "test@eleitora.com",
            "password": "123456"
        }
        
        success, response = self.run_test("User Login", "POST", "auth/login", 200, login_data)
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_create_campaign(self):
        """Test campaign creation"""
        campaign_data = {
            "candidate_name": "João Silva",
            "party": "PARTIDO",
            "position": "Vereador",
            "city": "Natal",
            "state": "RN",
            "election_year": 2024
        }
        
        success, response = self.run_test("Create Campaign", "POST", "campaigns", 200, campaign_data)
        if success and 'id' in response:
            self.campaign_id = response['id']
            return True
        return False

    def test_get_contract_templates(self):
        """Test getting contract templates"""
        success, response = self.run_test("Get Contract Templates", "GET", "contract-templates", 200)
        if success and 'templates' in response:
            templates = response['templates']
            expected_types = ['bem_movel', 'espaco_evento', 'imovel', 'veiculo_com_motorista', 'veiculo_sem_motorista']
            found_types = [t['type'] for t in templates]
            
            if all(t in found_types for t in expected_types):
                print(f"   ✅ All 5 template types found: {found_types}")
                return True
            else:
                print(f"   ❌ Missing templates. Expected: {expected_types}, Found: {found_types}")
        return False

    def test_create_contract_with_template(self):
        """Test creating contract with template"""
        contract_data = {
            "title": "Contrato de Locação de Veículo com Motorista",
            "description": "Contrato para locação de carro de som",
            "contractor_name": "Maria Santos",
            "contractor_cpf_cnpj": "12345678901",
            "value": 5000.00,
            "start_date": "2024-08-01",
            "end_date": "2024-08-31",
            "status": "rascunho",
            "template_type": "veiculo_com_motorista",
            # Locador fields
            "locador_nome": "Maria Santos",
            "locador_nacionalidade": "Brasileira",
            "locador_estado_civil": "Casada",
            "locador_profissao": "Empresária",
            "locador_endereco": "Rua das Flores, 123",
            "locador_numero": "123",
            "locador_cep": "59000-000",
            "locador_bairro": "Centro",
            "locador_cidade": "Natal",
            "locador_estado": "RN",
            "locador_rg": "1234567",
            "locador_cpf": "12345678901",
            "locador_email": "maria@email.com",
            # Object description
            "objeto_descricao": "Carro de som com equipamento completo",
            # Vehicle fields
            "veiculo_marca": "Ford",
            "veiculo_modelo": "F-4000",
            "veiculo_ano": "2020",
            "veiculo_placa": "ABC1234",
            "veiculo_renavam": "123456789",
            # Driver fields
            "motorista_nome": "José Silva",
            "motorista_cnh": "12345678901",
            # Trailer fields
            "reboque_descricao": "Paredão de som 10kW",
            "reboque_placa": "DEF5678",
            "reboque_renavam": "987654321"
        }
        
        success, response = self.run_test("Create Contract with Template", "POST", "contracts", 200, contract_data)
        if success and 'id' in response:
            self.contract_id = response['id']
            print(f"   ✅ Contract created with ID: {self.contract_id}")
            
            # Check if contract_html was generated
            if response.get('contract_html'):
                print(f"   ✅ Contract HTML generated successfully")
                return True
            else:
                print(f"   ❌ Contract HTML not generated")
        return False

    def test_get_contract_html(self):
        """Test getting contract HTML"""
        if not self.contract_id:
            print("❌ No contract ID available")
            return False
            
        success, response = self.run_test("Get Contract HTML", "GET", f"contracts/{self.contract_id}/html", 200)
        if success and 'html' in response:
            html = response['html']
            # Check if HTML contains expected elements
            expected_elements = [
                "CONTRATO DE LOCAÇÃO",
                "LOCADOR(A):",
                "LOCATÁRIO:",
                "Maria Santos",
                "João Silva",
                "Ford F-4000",
                "R$ 5.000,00"
            ]
            
            missing_elements = [elem for elem in expected_elements if elem not in html]
            if not missing_elements:
                print(f"   ✅ HTML contains all expected elements")
                return True
            else:
                print(f"   ❌ Missing elements in HTML: {missing_elements}")
        return False

    def test_request_signature(self):
        """Test requesting signature"""
        if not self.contract_id:
            print("❌ No contract ID available")
            return False
            
        signature_data = {
            "contract_id": self.contract_id,
            "locador_email": "maria@email.com"
        }
        
        success, response = self.run_test("Request Signature", "POST", f"contracts/{self.contract_id}/request-signature", 200, signature_data)
        if success and 'token' in response:
            self.signature_token = response['token']
            print(f"   ✅ Signature token generated: {self.signature_token[:20]}...")
            return True
        return False

    def test_verify_signature_token(self):
        """Test verifying signature token"""
        if not self.signature_token:
            print("❌ No signature token available")
            return False
            
        success, response = self.run_test("Verify Signature Token", "GET", f"contracts/verify/{self.signature_token}", 200)
        if success and response.get('valid'):
            print(f"   ✅ Token verified successfully")
            print(f"   Contract ID: {response.get('contract_id')}")
            print(f"   Locador: {response.get('locador_nome')}")
            print(f"   Candidate: {response.get('candidate_name')}")
            return True
        return False

    def test_sign_as_locador(self):
        """Test signing as locador (service provider)"""
        if not self.signature_token:
            print("❌ No signature token available")
            return False
            
        signature_data = {
            "signature_hash": f"locador-signature-{datetime.now().timestamp()}"
        }
        
        success, response = self.run_test("Sign as Locador", "POST", f"contracts/sign-locador/{self.signature_token}", 200, signature_data)
        if success:
            print(f"   ✅ Contract signed by locador")
            print(f"   Status: {response.get('status')}")
            return True
        return False

    def test_sign_as_locatario(self):
        """Test signing as locatário (candidate)"""
        if not self.contract_id:
            print("❌ No contract ID available")
            return False
            
        signature_data = {
            "signature_hash": f"locatario-signature-{datetime.now().timestamp()}"
        }
        
        success, response = self.run_test("Sign as Locatário", "POST", f"contracts/{self.contract_id}/sign-locatario", 200, signature_data)
        if success:
            print(f"   ✅ Contract signed by locatário")
            print(f"   Status: {response.get('status')}")
            return True
        return False

    def test_list_contracts(self):
        """Test listing contracts"""
        success, response = self.run_test("List Contracts", "GET", "contracts", 200)
        if success and isinstance(response, list):
            print(f"   ✅ Found {len(response)} contracts")
            
            if len(response) > 0:
                contract = response[0]
                # Check if contract has expected fields
                expected_fields = ['id', 'title', 'status', 'template_type', 'locador_nome']
                missing_fields = [field for field in expected_fields if field not in contract]
                
                if not missing_fields:
                    print(f"   ✅ Contract has all expected fields")
                    return True
                else:
                    print(f"   ❌ Missing fields: {missing_fields}")
            else:
                print(f"   ⚠️  No contracts found")
                return True  # This is OK for empty list
        return False

    def test_contract_status_updates(self):
        """Test contract status updates after signatures"""
        if not self.contract_id:
            print("❌ No contract ID available")
            return False
            
        success, response = self.run_test("Get Contract Status", "GET", f"contracts/{self.contract_id}", 200)
        if success:
            status = response.get('status')
            locador_signed = bool(response.get('locador_assinatura_hash'))
            locatario_signed = bool(response.get('locatario_assinatura_hash'))
            
            print(f"   Contract Status: {status}")
            print(f"   Locador Signed: {locador_signed}")
            print(f"   Locatário Signed: {locatario_signed}")
            
            # Check if status matches signature state
            if locador_signed and locatario_signed and status == 'ativo':
                print(f"   ✅ Status correctly updated to 'ativo' after both signatures")
                return True
            elif locador_signed and not locatario_signed and status == 'assinado_locador':
                print(f"   ✅ Status correctly shows 'assinado_locador'")
                return True
            elif not locador_signed and locatario_signed and status == 'assinado_locatario':
                print(f"   ✅ Status correctly shows 'assinado_locatario'")
                return True
            else:
                print(f"   ❌ Status doesn't match signature state")
        return False

def main():
    print("🚀 Starting Electoral Contract System API Tests")
    print("=" * 60)
    
    tester = ContractSystemTester()
    
    # Test sequence - try login first, then registration if needed
    print("\n🔐 Attempting login with existing user...")
    if not tester.test_login():
        print("🔐 Login failed, trying registration...")
        if not tester.test_register_user():
            print("❌ Both login and registration failed, using different email...")
            # Try with timestamp-based email
            import time
            timestamp = int(time.time())
            tester.test_email = f"test{timestamp}@eleitora.com"
            
    tests = [
        ("Health Check", tester.test_health_check),
        ("Create Campaign", tester.test_create_campaign),
        ("Get Contract Templates", tester.test_get_contract_templates),
        ("Create Contract with Template", tester.test_create_contract_with_template),
        ("Get Contract HTML", tester.test_get_contract_html),
        ("Request Signature", tester.test_request_signature),
        ("Verify Signature Token", tester.test_verify_signature_token),
        ("Sign as Locador", tester.test_sign_as_locador),
        ("Sign as Locatário", tester.test_sign_as_locatario),
        ("List Contracts", tester.test_list_contracts),
        ("Contract Status Updates", tester.test_contract_status_updates)
    ]
    
    print(f"\n📋 Running {len(tests)} test scenarios...")
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if not success:
                print(f"\n⚠️  Test '{test_name}' failed - continuing with remaining tests")
        except Exception as e:
            print(f"\n💥 Test '{test_name}' crashed: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        failed = tester.tests_run - tester.tests_passed
        print(f"❌ {failed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())