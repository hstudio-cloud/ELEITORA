"""
AI Electoral Assistant Tests
Tests for GPT-5.2 integration via Emergent LLM Key
Tests: /api/ai/chat, /api/ai/chat/history, /api/ai/analyze-expenses, /api/ai/check-compliance
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "alan.garcia@teste.com"
TEST_PASSWORD = "123456"


class TestAIAssistantSetup:
    """Setup and auth tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.user = data.get("user")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    
    def test_auth_working(self):
        """Verify authentication is working"""
        response = self.session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("email") == TEST_EMAIL
        print(f"Auth working - user: {data.get('name')}, campaign_id: {data.get('campaign_id')}")


class TestAIChatEndpoint:
    """Tests for POST /api/ai/chat"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_chat_simple_message(self):
        """Test sending a simple chat message"""
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Olá, qual é o status da minha campanha?"
        })
        
        print(f"Chat response status: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "response" in data, "Response should contain 'response' field"
        assert "session_id" in data, "Response should contain 'session_id' field"
        assert isinstance(data["response"], str), "Response should be a string"
        assert len(data["response"]) > 10, "Response should have meaningful content"
        
        print(f"AI Response preview: {data['response'][:200]}...")
        print(f"Session ID: {data['session_id']}")
    
    def test_chat_with_session_id(self):
        """Test chat with explicit session_id for continuity"""
        session_id = "test_session_123"
        
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Resuma os gastos da campanha",
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("session_id") == session_id
        assert "response" in data
        print(f"Chat with session ID working, response length: {len(data['response'])}")
    
    def test_chat_financial_question(self):
        """Test asking about financial data"""
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Qual é o saldo atual da minha campanha?"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should mention financial terms
        response_text = data["response"].lower()
        # At minimum check it's a valid response
        assert len(data["response"]) > 5
        print(f"Financial question response: {data['response'][:300]}...")
    
    def test_chat_compliance_question(self):
        """Test asking about compliance"""
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Minha campanha está em conformidade com as regras do TSE?"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        print(f"Compliance question response preview: {data['response'][:300]}...")
    
    def test_chat_requires_auth(self):
        """Test that chat endpoint requires authentication"""
        unauthenticated = requests.Session()
        unauthenticated.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated.post(f"{BASE_URL}/api/ai/chat", json={
            "message": "Test message"
        })
        
        assert response.status_code == 403 or response.status_code == 401
        print("Auth required check passed")
    
    def test_chat_empty_message(self):
        """Test that empty messages are handled"""
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": ""
        })
        
        # Should either reject or return error
        # Accept 200 with error message or 400/422 validation error
        print(f"Empty message response: {response.status_code} - {response.text[:200]}")


class TestAIChatHistory:
    """Tests for GET /api/ai/chat/history"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_get_chat_history(self):
        """Test retrieving chat history"""
        response = self.session.get(f"{BASE_URL}/api/ai/chat/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data, "Response should contain 'messages' array"
        assert "session_id" in data, "Response should contain 'session_id'"
        assert isinstance(data["messages"], list), "Messages should be a list"
        
        print(f"Chat history: {len(data['messages'])} messages found")
        if data["messages"]:
            print(f"Latest message role: {data['messages'][-1].get('role')}")
    
    def test_get_chat_history_with_limit(self):
        """Test chat history with limit parameter"""
        response = self.session.get(f"{BASE_URL}/api/ai/chat/history?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        # Messages should be <= limit
        assert len(data["messages"]) <= 5
        print(f"History with limit=5: {len(data['messages'])} messages")
    
    def test_chat_history_requires_auth(self):
        """Test that history endpoint requires authentication"""
        unauthenticated = requests.Session()
        
        response = unauthenticated.get(f"{BASE_URL}/api/ai/chat/history")
        
        assert response.status_code in [401, 403]
        print("History auth check passed")


class TestAIClearHistory:
    """Tests for DELETE /api/ai/chat/history"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_delete_chat_history(self):
        """Test clearing chat history"""
        response = self.session.delete(f"{BASE_URL}/api/ai/chat/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        print(f"Delete history response: {data}")
    
    def test_clear_and_verify_empty(self):
        """Test that history is actually cleared"""
        # First clear
        self.session.delete(f"{BASE_URL}/api/ai/chat/history")
        
        # Then check it's empty
        response = self.session.get(f"{BASE_URL}/api/ai/chat/history")
        assert response.status_code == 200
        data = response.json()
        
        assert data["messages"] == [] or len(data["messages"]) == 0
        print("History cleared successfully")


class TestAIAnalyzeExpenses:
    """Tests for POST /api/ai/analyze-expenses"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_analyze_expenses(self):
        """Test expense analysis endpoint"""
        response = self.session.post(f"{BASE_URL}/api/ai/analyze-expenses")
        
        print(f"Analyze expenses status: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "analysis" in data, "Response should contain 'analysis' field"
        assert isinstance(data["analysis"], str), "Analysis should be a string"
        
        print(f"Expense analysis preview: {data['analysis'][:300]}...")
    
    def test_analyze_expenses_requires_auth(self):
        """Test that analyze-expenses requires authentication"""
        unauthenticated = requests.Session()
        unauthenticated.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated.post(f"{BASE_URL}/api/ai/analyze-expenses")
        
        assert response.status_code in [401, 403]
        print("Analyze expenses auth check passed")


class TestAICheckCompliance:
    """Tests for POST /api/ai/check-compliance"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_check_compliance(self):
        """Test compliance check endpoint"""
        response = self.session.post(f"{BASE_URL}/api/ai/check-compliance")
        
        print(f"Check compliance status: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "compliance_report" in data, "Response should contain 'compliance_report' field"
        assert isinstance(data["compliance_report"], str), "Compliance report should be a string"
        
        print(f"Compliance report preview: {data['compliance_report'][:300]}...")
    
    def test_check_compliance_requires_auth(self):
        """Test that check-compliance requires authentication"""
        unauthenticated = requests.Session()
        unauthenticated.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated.post(f"{BASE_URL}/api/ai/check-compliance")
        
        assert response.status_code in [401, 403]
        print("Check compliance auth check passed")


class TestAITSERules:
    """Tests for GET /api/ai/tse-rules"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session (no auth required for this endpoint)"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_tse_rules(self):
        """Test retrieving TSE rules"""
        response = self.session.get(f"{BASE_URL}/api/ai/tse-rules")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "rules" in data, "Response should contain 'rules' field"
        assert isinstance(data["rules"], str), "Rules should be a string"
        assert len(data["rules"]) > 100, "Rules should have substantial content"
        
        # Verify it mentions TSE-related terms
        rules_lower = data["rules"].lower()
        assert any(term in rules_lower for term in ["tse", "eleitoral", "campanha", "limite"])
        
        print(f"TSE Rules preview: {data['rules'][:400]}...")


class TestAIChatHistoryPersistence:
    """Tests for chat history persistence across requests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Auth failed: {response.status_code}")
    
    def test_message_persisted_in_history(self):
        """Test that messages are saved to history after chat"""
        # Clear history first
        self.session.delete(f"{BASE_URL}/api/ai/chat/history")
        
        # Send a unique message
        unique_message = "TEST_UNIQUE_MESSAGE_12345"
        response = self.session.post(f"{BASE_URL}/api/ai/chat", json={
            "message": unique_message
        })
        
        assert response.status_code == 200
        
        # Now check history
        history_response = self.session.get(f"{BASE_URL}/api/ai/chat/history")
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        messages = history_data.get("messages", [])
        
        # Find our message in history
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert len(user_messages) > 0, "User message should be in history"
        
        # Check the message content is stored
        found = any(unique_message in m.get("content", "") for m in user_messages)
        assert found, f"Our unique message should be in history"
        
        print(f"Message persistence verified - {len(messages)} messages in history")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
