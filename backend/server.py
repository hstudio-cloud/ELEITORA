from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Query, BackgroundTasks, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import base64
import hashlib
import re
import json
import zipfile
import io
import httpx
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr, validator
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from enum import Enum
from io import BytesIO

# Optional imports for PDF and Email
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

# OFX Parser for bank statements
try:
    from ofxparse import OfxParser
    OFX_AVAILABLE = True
except ImportError:
    OFX_AVAILABLE = False

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET', 'eleitora360-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Email Config
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
APP_URL = os.environ.get('APP_URL', 'https://brasil-voting.preview.emergentagent.com')

if RESEND_AVAILABLE and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Banco do Brasil PIX API Config
BB_APP_KEY = os.environ.get('BB_APP_KEY', '')
BB_CLIENT_ID = os.environ.get('BB_CLIENT_ID', '')
BB_CLIENT_SECRET = os.environ.get('BB_CLIENT_SECRET', '')
BB_ENVIRONMENT = os.environ.get('BB_ENVIRONMENT', 'homologacao')

# BB API URLs based on environment
if BB_ENVIRONMENT == 'producao':
    BB_OAUTH_URL = "https://oauth.bb.com.br/oauth/token"
    BB_API_URL = "https://api.bb.com.br/pix/v2"
else:
    BB_OAUTH_URL = "https://oauth.hm.bb.com.br/oauth/token"
    BB_API_URL = "https://api.hm.bb.com.br/pix/v2"

BB_PIX_AVAILABLE = bool(BB_APP_KEY and BB_CLIENT_ID and BB_CLIENT_SECRET)

# File upload config
UPLOAD_DIR = ROOT_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# ============== BANCO DO BRASIL PIX INTEGRATION ==============
class BancoDoBrasilPIX:
    """Classe para integração com a API PIX do Banco do Brasil"""
    
    def __init__(self):
        self.app_key = BB_APP_KEY
        self.client_id = BB_CLIENT_ID
        self.client_secret = BB_CLIENT_SECRET
        self.oauth_url = BB_OAUTH_URL
        self.api_url = BB_API_URL
        self.access_token = None
        self.token_expires_at = None
        
    async def get_access_token(self) -> str:
        """Obtém token de acesso OAuth2"""
        # Check if token is still valid
        if self.access_token and self.token_expires_at:
            if datetime.now(timezone.utc) < self.token_expires_at:
                return self.access_token
        
        # Request new token using Basic Auth
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = "grant_type=client_credentials&scope=pix.read pix.write cob.read cob.write"
        
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            try:
                response = await client.post(
                    self.oauth_url,
                    headers=headers,
                    content=data
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logging.error(f"BB PIX OAuth Error: {response.status_code} - {error_text}")
                    # Try alternative auth method
                    return await self._get_token_alternative(client)
                
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                
                logging.info("BB PIX: Token obtido com sucesso")
                return self.access_token
                
            except httpx.HTTPError as e:
                logging.error(f"BB PIX: Erro ao obter token: {e}")
                raise HTTPException(status_code=500, detail=f"Erro de autenticação com Banco do Brasil: {str(e)}")
    
    async def _get_token_alternative(self, client: httpx.AsyncClient) -> str:
        """Tenta método alternativo de autenticação"""
        # Some BB environments require the app key in the auth flow
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "gw-dev-app-key": self.app_key
        }
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "pix.read pix.write cob.read cob.write"
        }
        
        try:
            response = await client.post(
                self.oauth_url,
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                logging.info("BB PIX: Token obtido via método alternativo")
                return self.access_token
            else:
                logging.error(f"BB PIX Alt Auth Error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=500, detail="Falha na autenticação com Banco do Brasil")
        except Exception as e:
            logging.error(f"BB PIX: Erro no método alternativo: {e}")
            raise HTTPException(status_code=500, detail=f"Erro de autenticação: {str(e)}")
    
    async def create_pix_payment(self, pix_data: dict) -> dict:
        """Cria um pagamento PIX"""
        token = await self.get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "gw-dev-app-key": self.app_key
        }
        
        # Generate unique transaction ID (txid)
        txid = f"ELT{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:10].upper()}"
        
        # Prepare payload according to BB API
        payload = {
            "calendario": {
                "dataDeVencimento": pix_data.get("scheduled_date", datetime.now().strftime("%Y-%m-%d")),
                "validadeAposVencimento": 30
            },
            "devedor": {
                "cpf" if len(pix_data.get("recipient_cpf_cnpj", "").replace(".", "").replace("-", "").replace("/", "")) == 11 else "cnpj": pix_data.get("recipient_cpf_cnpj", "").replace(".", "").replace("-", "").replace("/", ""),
                "nome": pix_data.get("recipient_name", "")
            },
            "valor": {
                "original": f"{pix_data.get('amount', 0):.2f}"
            },
            "chave": pix_data.get("pix_key", ""),
            "solicitacaoPagador": pix_data.get("description", "Pagamento via Eleitora 360")[:140]
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            try:
                # Create cobrança (billing request)
                response = await client.put(
                    f"{self.api_url}/cobv/{txid}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                logging.info(f"BB PIX: Cobrança criada - txid: {txid}")
                
                return {
                    "success": True,
                    "txid": txid,
                    "location": result.get("location", ""),
                    "pixCopiaECola": result.get("pixCopiaECola", ""),
                    "status": result.get("status", "ATIVA"),
                    "calendario": result.get("calendario", {}),
                    "valor": result.get("valor", {}),
                    "raw_response": result
                }
                
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text if e.response else str(e)
                logging.error(f"BB PIX: Erro ao criar cobrança: {error_detail}")
                return {
                    "success": False,
                    "error": error_detail,
                    "status_code": e.response.status_code if e.response else 500
                }
            except Exception as e:
                logging.error(f"BB PIX: Erro inesperado: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def check_pix_status(self, txid: str) -> dict:
        """Consulta o status de um PIX"""
        token = await self.get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "gw-dev-app-key": self.app_key
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.get(f"{self.api_url}/cobv/{txid}", headers=headers)
                response.raise_for_status()
                
                result = response.json()
                return {
                    "success": True,
                    "txid": txid,
                    "status": result.get("status", "UNKNOWN"),
                    "valor": result.get("valor", {}),
                    "pix": result.get("pix", []),  # Lista de pagamentos recebidos
                    "raw_response": result
                }
                
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def list_pix_received(self, start_date: str, end_date: str) -> dict:
        """Lista PIX recebidos em um período"""
        token = await self.get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "gw-dev-app-key": self.app_key
        }
        
        params = {
            "inicio": f"{start_date}T00:00:00Z",
            "fim": f"{end_date}T23:59:59Z"
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.get(f"{self.api_url}/pix", headers=headers, params=params)
                response.raise_for_status()
                
                result = response.json()
                return {
                    "success": True,
                    "pix": result.get("pix", []),
                    "parametros": result.get("parametros", {})
                }
                
            except httpx.HTTPError as e:
                return {
                    "success": False,
                    "error": str(e)
                }

# Initialize BB PIX client
bb_pix_client = BancoDoBrasilPIX() if BB_PIX_AVAILABLE else None

# Create the main app
app = FastAPI(title="Eleitora 360 API", version="1.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# ============== VALIDATION HELPERS ==============
def validate_cpf(cpf: str) -> bool:
    """Validate Brazilian CPF"""
    cpf = re.sub(r'[^0-9]', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    
    # First digit
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[9]) != digito1:
        return False
    
    # Second digit
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    return int(cpf[10]) == digito2

def validate_cnpj(cnpj: str) -> bool:
    """Validate Brazilian CNPJ"""
    cnpj = re.sub(r'[^0-9]', '', cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    
    # First digit
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cnpj[12]) != digito1:
        return False
    
    # Second digit
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    return int(cnpj[13]) == digito2

def format_cpf(cpf: str) -> str:
    """Format CPF to XXX.XXX.XXX-XX"""
    cpf = re.sub(r'[^0-9]', '', cpf)
    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf

def format_cnpj(cnpj: str) -> str:
    """Format CNPJ to XX.XXX.XXX/XXXX-XX"""
    cnpj = re.sub(r'[^0-9]', '', cnpj)
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

# ============== ENUMS ==============
class UserRole(str, Enum):
    CANDIDATO = "candidato"
    CONTADOR = "contador"

class ContractStatus(str, Enum):
    RASCUNHO = "rascunho"
    AGUARDANDO_ASSINATURA = "aguardando_assinatura"
    ASSINADO_LOCADOR = "assinado_locador"
    ASSINADO_LOCATARIO = "assinado_locatario"
    ATIVO = "ativo"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"

class ContractTemplateType(str, Enum):
    BEM_MOVEL = "bem_movel"
    ESPACO_EVENTO = "espaco_evento"
    IMOVEL = "imovel"
    VEICULO_COM_MOTORISTA = "veiculo_com_motorista"
    VEICULO_SEM_MOTORISTA = "veiculo_sem_motorista"

# Required attachments by contract type
CONTRACT_REQUIRED_ATTACHMENTS = {
    "veiculo_com_motorista": [
        {"key": "doc_veiculo", "label": "Documento do Veículo (CRLV)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do Proprietário (RG/CPF)", "required": True},
        {"key": "cnh_motorista", "label": "CNH do Motorista", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de Residência", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "veiculo_sem_motorista": [
        {"key": "doc_veiculo", "label": "Documento do Veículo (CRLV)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do Proprietário (RG/CPF)", "required": True},
        {"key": "cnh_proprietario", "label": "CNH do Proprietário", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de Residência", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "imovel": [
        {"key": "doc_imovel", "label": "Documento do Imóvel (Escritura/Contrato)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do Proprietário/Locador (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de Residência do Locador", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "bem_movel": [
        {"key": "doc_proprietario", "label": "Documento do Proprietário (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de Residência", "required": True},
        {"key": "doc_bem", "label": "Documento do Bem (se houver)", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "espaco_evento": [
        {"key": "doc_proprietario", "label": "Documento do Proprietário/Responsável (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de Residência", "required": True},
        {"key": "doc_espaco", "label": "Documento do Espaço (se houver)", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ]
}

class PaymentStatus(str, Enum):
    PENDENTE = "pendente"
    PAGO = "pago"
    CANCELADO = "cancelado"

class RevenueCategory(str, Enum):
    DOACAO_PF = "doacao_pf"
    DOACAO_PJ = "doacao_pj"
    RECURSOS_PROPRIOS = "recursos_proprios"
    FUNDO_ELEITORAL = "fundo_eleitoral"
    FUNDO_PARTIDARIO = "fundo_partidario"
    OUTROS = "outros"

class ExpenseCategory(str, Enum):
    PUBLICIDADE = "publicidade"
    MATERIAL_GRAFICO = "material_grafico"
    SERVICOS_TERCEIROS = "servicos_terceiros"
    TRANSPORTE = "transporte"
    ALIMENTACAO = "alimentacao"
    PESSOAL = "pessoal"
    EVENTOS = "eventos"
    OUTROS = "outros"

# ============== MODELS ==============
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.CANDIDATO
    cpf: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: UserRole
    cpf: Optional[str] = None
    phone: Optional[str] = None
    campaign_id: Optional[str] = None
    created_at: str

class CampaignCreate(BaseModel):
    candidate_name: str
    party: str
    position: str  # Prefeito, Vereador, etc.
    city: str
    state: str
    election_year: int
    # TSE Spending Limits
    eleitores: Optional[int] = None  # Número de eleitores do município (para cálculo do limite TSE)
    codigo_ibge: Optional[str] = None  # Código IBGE do município
    # SPCE Required Fields
    cnpj: Optional[str] = None  # CNPJ da campanha
    numero_candidato: Optional[str] = None  # Número do candidato
    # Candidate personal data
    cpf_candidato: Optional[str] = None
    titulo_eleitor: Optional[str] = None
    # Bank accounts (3 types required by TSE)
    conta_doacao_banco: Optional[str] = None
    conta_doacao_agencia: Optional[str] = None
    conta_doacao_numero: Optional[str] = None
    conta_doacao_digito: Optional[str] = None
    
    conta_fundo_partidario_banco: Optional[str] = None
    conta_fundo_partidario_agencia: Optional[str] = None
    conta_fundo_partidario_numero: Optional[str] = None
    conta_fundo_partidario_digito: Optional[str] = None
    
    conta_fefec_banco: Optional[str] = None  # FEFEC - Fundo Especial de Financiamento de Campanha
    conta_fefec_agencia: Optional[str] = None
    conta_fefec_numero: Optional[str] = None
    conta_fefec_digito: Optional[str] = None
    # Address
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None

class CampaignResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    candidate_name: str
    party: str
    position: str
    city: str
    state: str
    election_year: int
    owner_id: str
    created_at: str
    # TSE Spending Limits
    eleitores: Optional[int] = None
    codigo_ibge: Optional[str] = None
    # SPCE Fields
    cnpj: Optional[str] = None
    numero_candidato: Optional[str] = None
    cpf_candidato: Optional[str] = None
    titulo_eleitor: Optional[str] = None
    # Bank accounts
    conta_doacao_banco: Optional[str] = None
    conta_doacao_agencia: Optional[str] = None
    conta_doacao_numero: Optional[str] = None
    conta_doacao_digito: Optional[str] = None
    
    conta_fundo_partidario_banco: Optional[str] = None
    conta_fundo_partidario_agencia: Optional[str] = None
    conta_fundo_partidario_numero: Optional[str] = None
    conta_fundo_partidario_digito: Optional[str] = None
    
    conta_fefec_banco: Optional[str] = None
    conta_fefec_agencia: Optional[str] = None
    conta_fefec_numero: Optional[str] = None
    conta_fefec_digito: Optional[str] = None
    # Address
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None

# SPCE Revenue Types
class TipoReceita(str, Enum):
    DOACAO_FINANCEIRA = "doacao_financeira"
    DOACAO_ESTIMAVEL = "doacao_estimavel"
    RECURSOS_PROPRIOS = "recursos_proprios"
    FUNDO_PARTIDARIO = "fundo_partidario"
    FUNDO_ELEITORAL = "fundo_eleitoral"
    COMERCIALIZACAO = "comercializacao"
    RENDIMENTO_APLICACAO = "rendimento_aplicacao"
    SOBRAS_CAMPANHA = "sobras_campanha"
    OUTROS = "outros"

class TipoDoador(str, Enum):
    PESSOA_FISICA = "pessoa_fisica"
    PESSOA_JURIDICA = "pessoa_juridica"
    PARTIDO = "partido"
    CANDIDATO = "candidato"
    COMITE = "comite"
    FUNDO_PARTIDARIO = "fundo_partidario"
    FUNDO_ELEITORAL = "fundo_eleitoral"

class FormaRecebimento(str, Enum):
    PIX = "pix"
    TRANSFERENCIA = "transferencia"
    DEPOSITO = "deposito"
    CHEQUE = "cheque"
    ESPECIE = "especie"
    CARTAO_CREDITO = "cartao_credito"
    CARTAO_DEBITO = "cartao_debito"
    ESTIMAVEL = "estimavel"

# SPCE Payment Types
class TipoPagamento(str, Enum):
    PIX = "pix"
    TRANSFERENCIA = "transferencia"
    BOLETO = "boleto"
    CHEQUE = "cheque"
    ESPECIE = "especie"
    CARTAO_CREDITO = "cartao_credito"
    CARTAO_DEBITO = "cartao_debito"
    DEBITO_AUTOMATICO = "debito_automatico"

class RevenueCreate(BaseModel):
    description: str
    amount: float
    category: RevenueCategory
    donor_name: Optional[str] = None
    donor_cpf_cnpj: Optional[str] = None
    date: str
    receipt_number: Optional[str] = None
    notes: Optional[str] = None
    attachment_id: Optional[str] = None
    # SPCE Required Fields
    tipo_receita: Optional[TipoReceita] = TipoReceita.DOACAO_FINANCEIRA
    tipo_doador: Optional[TipoDoador] = TipoDoador.PESSOA_FISICA
    forma_recebimento: Optional[FormaRecebimento] = FormaRecebimento.TRANSFERENCIA
    recibo_eleitoral: Optional[str] = None  # Número do recibo eleitoral (auto-gerado)
    donor_titulo_eleitor: Optional[str] = None  # Título de eleitor do doador PF

class RevenueResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    description: str
    amount: float
    category: RevenueCategory
    donor_name: Optional[str] = None
    donor_cpf_cnpj: Optional[str] = None
    date: str
    receipt_number: Optional[str] = None
    notes: Optional[str] = None
    campaign_id: str
    created_at: str
    attachment_id: Optional[str] = None
    # SPCE Fields
    tipo_receita: Optional[str] = None
    tipo_doador: Optional[str] = None
    forma_recebimento: Optional[str] = None
    recibo_eleitoral: Optional[str] = None
    donor_titulo_eleitor: Optional[str] = None

class ExpenseCreate(BaseModel):
    description: str
    amount: float
    category: ExpenseCategory
    supplier_name: Optional[str] = None
    supplier_cpf_cnpj: Optional[str] = None
    date: str
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    attachment_id: Optional[str] = None
    payment_status: Optional[str] = "pendente"  # pendente, pago
    contract_id: Optional[str] = None  # Link to contract if auto-generated
    # SPCE Required Fields
    tipo_pagamento: Optional[TipoPagamento] = None
    numero_parcela: Optional[int] = None
    total_parcelas: Optional[int] = None
    numero_documento_fiscal: Optional[str] = None
    data_pagamento: Optional[str] = None

class ExpenseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    description: str
    amount: float
    category: ExpenseCategory
    supplier_name: Optional[str] = None
    supplier_cpf_cnpj: Optional[str] = None
    date: str
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    campaign_id: str
    created_at: str
    attachment_id: Optional[str] = None
    payment_status: Optional[str] = "pendente"
    contract_id: Optional[str] = None
    # SPCE Fields
    tipo_pagamento: Optional[str] = None
    numero_parcela: Optional[int] = None
    total_parcelas: Optional[int] = None
    numero_documento_fiscal: Optional[str] = None
    data_pagamento: Optional[str] = None

class ContractCreate(BaseModel):
    title: str
    description: str
    contractor_name: str
    contractor_cpf_cnpj: str
    value: float
    start_date: str
    end_date: str
    status: ContractStatus = ContractStatus.RASCUNHO
    notes: Optional[str] = None
    attachment_id: Optional[str] = None  # Contract attachment (legacy)
    attachments: Optional[dict] = None  # New: multiple attachments by key
    # Payment installments
    num_parcelas: int = 1  # Number of installments
    parcelas_config: Optional[List[dict]] = None  # [{percentual: 50, data_vencimento: "2024-08-15"}, ...]
    gerar_despesas: bool = True  # Auto-generate expenses
    # New fields for template contracts
    template_type: Optional[ContractTemplateType] = None
    # Locador (Prestador de Serviço) fields
    locador_nome: Optional[str] = None
    locador_nacionalidade: Optional[str] = "Brasileiro(a)"
    locador_estado_civil: Optional[str] = None
    locador_profissao: Optional[str] = None
    locador_endereco: Optional[str] = None
    locador_numero: Optional[str] = None
    locador_cep: Optional[str] = None
    locador_bairro: Optional[str] = None
    locador_cidade: Optional[str] = None
    locador_estado: Optional[str] = None
    locador_rg: Optional[str] = None
    locador_cpf: Optional[str] = None
    locador_email: Optional[str] = None
    # Object description
    objeto_descricao: Optional[str] = None
    # Vehicle specific fields
    veiculo_marca: Optional[str] = None
    veiculo_modelo: Optional[str] = None
    veiculo_ano: Optional[str] = None
    veiculo_placa: Optional[str] = None
    veiculo_renavam: Optional[str] = None
    # Property specific fields
    imovel_descricao: Optional[str] = None
    imovel_registro: Optional[str] = None
    # Motorista fields
    motorista_nome: Optional[str] = None
    motorista_cnh: Optional[str] = None
    # Reboque/Paredão fields
    reboque_descricao: Optional[str] = None
    reboque_placa: Optional[str] = None
    reboque_renavam: Optional[str] = None
    # Event specific fields
    evento_horario_inicio: Optional[str] = None
    evento_horario_fim: Optional[str] = None
    # Signature fields
    locador_assinatura_data: Optional[str] = None
    locador_assinatura_hash: Optional[str] = None
    locatario_assinatura_data: Optional[str] = None
    locatario_assinatura_hash: Optional[str] = None
    signature_request_token: Optional[str] = None

class ContractResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    description: str
    contractor_name: str
    contractor_cpf_cnpj: str
    value: float
    start_date: str
    end_date: str
    status: ContractStatus
    notes: Optional[str] = None
    campaign_id: str
    created_at: str
    attachment_id: Optional[str] = None
    attachments: Optional[dict] = None  # Multiple attachments by key
    num_parcelas: Optional[int] = 1
    parcelas_config: Optional[List[dict]] = None
    gerar_despesas: Optional[bool] = True
    # New fields
    template_type: Optional[str] = None
    locador_nome: Optional[str] = None
    locador_nacionalidade: Optional[str] = None
    locador_estado_civil: Optional[str] = None
    locador_profissao: Optional[str] = None
    locador_endereco: Optional[str] = None
    locador_numero: Optional[str] = None
    locador_cep: Optional[str] = None
    locador_bairro: Optional[str] = None
    locador_cidade: Optional[str] = None
    locador_estado: Optional[str] = None
    locador_rg: Optional[str] = None
    locador_cpf: Optional[str] = None
    locador_email: Optional[str] = None
    objeto_descricao: Optional[str] = None
    veiculo_marca: Optional[str] = None
    veiculo_modelo: Optional[str] = None
    veiculo_ano: Optional[str] = None
    veiculo_placa: Optional[str] = None
    veiculo_renavam: Optional[str] = None
    imovel_descricao: Optional[str] = None
    imovel_registro: Optional[str] = None
    motorista_nome: Optional[str] = None
    motorista_cnh: Optional[str] = None
    reboque_descricao: Optional[str] = None
    reboque_placa: Optional[str] = None
    reboque_renavam: Optional[str] = None
    evento_horario_inicio: Optional[str] = None
    evento_horario_fim: Optional[str] = None
    locador_assinatura_data: Optional[str] = None
    locador_assinatura_hash: Optional[str] = None
    locatario_assinatura_data: Optional[str] = None
    locatario_assinatura_hash: Optional[str] = None
    signature_request_token: Optional[str] = None
    contract_html: Optional[str] = None

class PaymentCreate(BaseModel):
    description: str
    amount: float
    due_date: str
    payment_date: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDENTE
    expense_id: Optional[str] = None
    contract_id: Optional[str] = None
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    description: str
    amount: float
    due_date: str
    payment_date: Optional[str] = None
    status: PaymentStatus
    expense_id: Optional[str] = None
    contract_id: Optional[str] = None
    notes: Optional[str] = None
    campaign_id: str
    created_at: str

# ============== PROFESSIONAL MODELS ==============
class ProfessionalType(str, Enum):
    CONTADOR = "contador"
    ADVOGADO = "advogado"

class ProfessionalCreate(BaseModel):
    type: ProfessionalType
    name: str
    email: str
    phone: Optional[str] = None
    # Contador fields
    crc: Optional[str] = None  # Registro no CRC
    crc_state: Optional[str] = None
    # Advogado fields
    oab: Optional[str] = None  # Número OAB
    oab_state: Optional[str] = None
    # Common fields
    cpf: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    notes: Optional[str] = None
    # Account access
    has_system_access: bool = False
    password: Optional[str] = None

class ProfessionalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: ProfessionalType
    name: str
    email: str
    phone: Optional[str] = None
    crc: Optional[str] = None
    crc_state: Optional[str] = None
    oab: Optional[str] = None
    oab_state: Optional[str] = None
    cpf: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    notes: Optional[str] = None
    has_system_access: bool = False
    is_active: bool = True
    campaigns: Optional[List[str]] = None  # List of campaign IDs this professional has access to
    created_at: str

# ============== PIX MODELS ==============
class PixPaymentCreate(BaseModel):
    expense_id: Optional[str] = None  # Optional: link to expense
    pix_key: str
    pix_key_type: str  # cpf, cnpj, email, phone, random
    recipient_name: str  # Name of recipient
    recipient_cpf_cnpj: Optional[str] = None
    amount: float
    description: Optional[str] = None
    scheduled_date: Optional[str] = None  # For scheduled payments

class PixPaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    expense_id: Optional[str] = None
    pix_key: str
    pix_key_type: str
    recipient_name: str
    recipient_cpf_cnpj: Optional[str] = None
    amount: float
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    status: str  # agendado, processando, executado, falhou, cancelado
    transaction_id: Optional[str] = None
    campaign_id: str
    created_at: str


class DashboardStats(BaseModel):
    total_revenues: float
    total_expenses: float
    balance: float
    pending_payments: int
    active_contracts: int
    revenues_by_category: dict
    expenses_by_category: dict
    monthly_flow: List[dict]

# ============== BANK STATEMENT MODELS ==============
class BankTransactionType(str, Enum):
    CREDIT = "credit"  # Entrada (receita)
    DEBIT = "debit"    # Saída (despesa)

class ReconciliationStatus(str, Enum):
    PENDING = "pending"           # Aguardando conciliação
    RECONCILED = "reconciled"     # Conciliado automaticamente
    MANUAL = "manual"             # Conciliado manualmente
    DIVERGENT = "divergent"       # Divergência encontrada
    IGNORED = "ignored"           # Ignorado pelo usuário

class BankStatementCreate(BaseModel):
    bank_name: str
    account_number: str
    account_type: Optional[str] = None
    start_date: str
    end_date: str
    currency: str = "BRL"

class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    statement_id: str
    transaction_id: str  # ID original do banco
    date: str
    amount: float
    type: BankTransactionType
    description: str
    memo: Optional[str] = None
    payee: Optional[str] = None
    check_number: Optional[str] = None
    # Reconciliation fields
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.PENDING
    reconciled_with_id: Optional[str] = None  # ID da receita ou despesa
    reconciled_with_type: Optional[str] = None  # "revenue" ou "expense"
    reconciled_at: Optional[str] = None
    match_confidence: Optional[float] = None  # 0-100% de confiança do match
    campaign_id: str
    created_at: str

class BankStatementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    bank_name: str
    account_number: str
    account_type: Optional[str] = None
    start_date: str
    end_date: str
    currency: str
    total_credits: float
    total_debits: float
    transaction_count: int
    reconciled_count: int
    pending_count: int
    campaign_id: str
    created_at: str

# ============== AUTH HELPERS ==============
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_current_user_or_contador(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user - accepts both regular user and contador tokens"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # First try to find as regular user
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if user:
            return user
        
        # If not found, try to find as professional/contador
        professional = await db.professionals.find_one({"id": payload["user_id"]}, {"_id": 0, "password_hash": 0})
        if professional:
            return professional
        
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ============== CONTRACT TEMPLATE GENERATORS ==============
def format_currency(value):
    """Format value as Brazilian currency"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_date_br(date_str):
    """Format date to Brazilian format"""
    if not date_str:
        return ""
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        months = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 
                  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        return f"{date.day} de {months[date.month-1]} de {date.year}"
    except:
        return date_str

def generate_contract_html(contract_data: dict, campaign: dict) -> str:
    """Generate HTML contract based on template type"""
    template_type = contract_data.get("template_type", "bem_movel")
    
    # Common header
    header = f"""
    <div style="font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.8;">
        <h1 style="text-align: center; font-size: 16pt; margin-bottom: 30px;">
            CONTRATO DE LOCAÇÃO DE {get_contract_title(template_type)}
        </h1>
        <p style="text-align: justify;">
            Pelo presente instrumento particular, os signatários têm entre si justa e contratada a locação 
            do bem abaixo descrito, mediante as seguintes cláusulas.
        </p>
    """
    
    # Locador section
    locador_section = f"""
        <h2 style="font-size: 14pt; margin-top: 30px;">IDENTIFICAÇÃO DAS PARTES</h2>
        
        <p><strong>LOCADOR(A):</strong></p>
        <p style="text-align: justify;">
            <strong>Nome:</strong> {contract_data.get('locador_nome', '_______________')}<br>
            <strong>Nacionalidade:</strong> {contract_data.get('locador_nacionalidade', 'Brasileiro(a)')}<br>
            <strong>Estado Civil:</strong> {contract_data.get('locador_estado_civil', '_______________')}<br>
            <strong>Profissão:</strong> {contract_data.get('locador_profissao', '_______________')}<br>
            <strong>Endereço:</strong> {contract_data.get('locador_endereco', '_______________')}, 
            nº {contract_data.get('locador_numero', '___')}, 
            CEP: {contract_data.get('locador_cep', '_______________')}, 
            Bairro: {contract_data.get('locador_bairro', '_______________')}, 
            {contract_data.get('locador_cidade', '_______________')}/{contract_data.get('locador_estado', '__')}<br>
            <strong>RG:</strong> {contract_data.get('locador_rg', '_______________')}<br>
            <strong>CPF:</strong> {contract_data.get('locador_cpf', '_______________')}
        </p>
    """
    
    # Locatário section (Candidate - auto-filled)
    locatario_section = f"""
        <p><strong>LOCATÁRIO:</strong></p>
        <p style="text-align: justify;">
            <strong>Campanha:</strong> ELEIÇÃO {campaign.get('election_year', '2024')} - {campaign.get('candidate_name', '_______________')} - {campaign.get('position', 'VEREADOR').upper()}<br>
            <strong>Partido:</strong> {campaign.get('party', '_______________')}<br>
            <strong>Endereço:</strong> {campaign.get('city', '_______________')}/{campaign.get('state', '__')}
        </p>
    """
    
    # Object clause based on template type
    object_clause = generate_object_clause(template_type, contract_data)
    
    # Value and term clauses
    value_clause = f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO VALOR DO ALUGUEL</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA TERCEIRA.</strong> Pela locação ora ajustada, o LOCATÁRIO pagará a quantia de 
            <strong>{format_currency(contract_data.get('value', 0))}</strong>, cujo pagamento será efetuado 
            até o dia {format_date_br(contract_data.get('end_date', ''))}.
        </p>
    """
    
    term_clause = f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DA VIGÊNCIA</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA SEGUNDA.</strong> O presente contrato terá vigência a partir de 
            {format_date_br(contract_data.get('start_date', ''))} até {format_date_br(contract_data.get('end_date', ''))}.
        </p>
    """
    
    # Forum clause
    forum_clause = f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO FORO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA QUARTA.</strong> As partes elegem o Foro da Comarca de 
            {campaign.get('city', '_______________')}/{campaign.get('state', '__')} para dirimir eventuais 
            controvérsias decorrentes deste contrato, com renúncia a qualquer outro, por mais privilegiado que seja.
        </p>
    """
    
    # Signature section
    signature_section = f"""
        <p style="margin-top: 40px; text-align: justify;">
            E, por estarem assim ajustados e contratados, assinam o presente em 02 (Duas) vias de igual forma 
            e teor, na presença das testemunhas abaixo.
        </p>
        
        <p style="text-align: right; margin-top: 30px;">
            {campaign.get('city', '_______________')}/{campaign.get('state', '__')}, {format_date_br(datetime.now(timezone.utc).isoformat())}
        </p>
        
        <div style="margin-top: 60px; display: flex; justify-content: space-between;">
            <div style="text-align: center; width: 45%;">
                <div style="border-bottom: 1px solid #000; padding-bottom: 5px; margin-bottom: 10px;">
                    {get_signature_status(contract_data, 'locador')}
                </div>
                <p><strong>{contract_data.get('locador_nome', '_______________')}</strong><br>LOCADOR</p>
            </div>
            <div style="text-align: center; width: 45%;">
                <div style="border-bottom: 1px solid #000; padding-bottom: 5px; margin-bottom: 10px;">
                    {get_signature_status(contract_data, 'locatario')}
                </div>
                <p><strong>{campaign.get('candidate_name', '_______________')}</strong><br>LOCATÁRIO</p>
            </div>
        </div>
        
        <h3 style="font-size: 12pt; margin-top: 40px;">TESTEMUNHAS:</h3>
        <div style="display: flex; justify-content: space-between; margin-top: 20px;">
            <div style="width: 45%;">
                <p>Nome: _________________________________<br>
                RG: ________________<br>
                CPF: _______________</p>
            </div>
            <div style="width: 45%;">
                <p>Nome: _________________________________<br>
                RG: ________________<br>
                CPF: _______________</p>
            </div>
        </div>
    </div>
    """
    
    return header + locador_section + locatario_section + object_clause + term_clause + value_clause + forum_clause + signature_section

def get_contract_title(template_type: str) -> str:
    titles = {
        "bem_movel": "BEM MÓVEL PARA CAMPANHA ELEITORAL",
        "espaco_evento": "ESPAÇO PARA EVENTO ELEITORAL",
        "imovel": "IMÓVEL PARA CAMPANHA ELEITORAL",
        "veiculo_com_motorista": "VEÍCULO COM MOTORISTA PARA CAMPANHA ELEITORAL",
        "veiculo_sem_motorista": "VEÍCULO SEM MOTORISTA PARA CAMPANHA ELEITORAL"
    }
    return titles.get(template_type, "BEM MÓVEL PARA CAMPANHA ELEITORAL")

def generate_object_clause(template_type: str, contract_data: dict) -> str:
    if template_type == "bem_movel":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para uso exclusivo 
            da campanha eleitoral do LOCATÁRIO, do seguinte bem móvel de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCATÁRIO é obrigado a conservar o bem móvel ora alugado, 
            ficando responsável pelo seu bom estado de conservação.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> São vedados a transferência, a sublocação, a cessão ou o empréstimo, 
            total ou parcial, do bem locado sem prévia anuência expressa do LOCADOR.
        </p>
        """
    elif template_type == "espaco_evento":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para realização 
            de atividade da campanha eleitoral do LOCATÁRIO, do seguinte espaço de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCADOR colocará o espaço à disposição do LOCATÁRIO entre as 
            {contract_data.get('evento_horario_inicio', '___')} e {contract_data.get('evento_horario_fim', '___')} horas.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> O LOCATÁRIO usará com zelo as dependências, devendo restituí-lo 
            ao término do período em seu estado inicial.
        </p>
        """
    elif template_type == "imovel":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para uso exclusivo 
            da campanha eleitoral do LOCATÁRIO, do seguinte bem imóvel de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;">
            <strong>{contract_data.get('imovel_descricao', '_______________')}</strong><br>
            Registro: {contract_data.get('imovel_registro', '_______________')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCATÁRIO é obrigado a conservar o bem imóvel ora alugado, 
            ficando responsável pelas obras necessárias ao seu bom estado de conservação.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> São vedados a transferência, a sublocação, a cessão ou o empréstimo, 
            total ou parcial, do imóvel locado sem prévia anuência expressa do LOCADOR.
        </p>
        """
    elif template_type == "veiculo_com_motorista":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação do veículo:
        </p>
        <p style="margin-left: 40px;">
            <strong>Veículo:</strong> {contract_data.get('veiculo_marca', '___')} {contract_data.get('veiculo_modelo', '___')}<br>
            <strong>Ano:</strong> {contract_data.get('veiculo_ano', '___')}<br>
            <strong>Placa:</strong> {contract_data.get('veiculo_placa', '___')}<br>
            <strong>RENAVAM:</strong> {contract_data.get('veiculo_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <strong>Motorista:</strong> {contract_data.get('motorista_nome', '_______________')}, 
            CNH nº {contract_data.get('motorista_cnh', '_______________')}
        </p>
        <p style="text-align: justify;">
            <strong>Equipamento a ser puxado (se aplicável):</strong><br>
            {contract_data.get('reboque_descricao', '_______________')}<br>
            Placa: {contract_data.get('reboque_placa', '___')} - RENAVAM: {contract_data.get('reboque_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo único.</em> O LOCATÁRIO deverá devolver o veículo ao LOCADOR nas mesmas condições 
            em que o recebeu, respondendo por danos ou prejuízos causados.
        </p>
        """
    else:  # veiculo_sem_motorista
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÁUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação do veículo:
        </p>
        <p style="margin-left: 40px;">
            <strong>Veículo:</strong> {contract_data.get('veiculo_marca', '___')} {contract_data.get('veiculo_modelo', '___')}<br>
            <strong>Ano:</strong> {contract_data.get('veiculo_ano', '___')}<br>
            <strong>Placa:</strong> {contract_data.get('veiculo_placa', '___')}<br>
            <strong>RENAVAM:</strong> {contract_data.get('veiculo_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O automóvel será utilizado exclusivamente pelo LOCATÁRIO ou 
            terceiros sob sua responsabilidade.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo segundo.</em> O LOCATÁRIO deverá devolver o automóvel ao LOCADOR nas mesmas 
            condições em que o recebeu, respondendo por danos ou prejuízos causados.
        </p>
        """

def get_signature_status(contract_data: dict, party: str) -> str:
    if party == "locador":
        if contract_data.get('locador_assinatura_hash'):
            return f"<span style='color: green;'>✓ Assinado digitalmente em {contract_data.get('locador_assinatura_data', '')}</span>"
        return "<span style='color: #999;'>Aguardando assinatura</span>"
    else:
        if contract_data.get('locatario_assinatura_hash'):
            return f"<span style='color: green;'>✓ Assinado digitalmente em {contract_data.get('locatario_assinatura_data', '')}</span>"
        return "<span style='color: #999;'>Aguardando assinatura</span>"

def generate_signature_token(contract_id: str, email: str, party: str) -> str:
    """Generate a unique token for signature request"""
    payload = {
        "contract_id": contract_id,
        "email": email,
        "party": party,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# ============== AUTH ROUTES ==============
@api_router.post("/auth/register", response_model=dict)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": user_data.role.value,
        "cpf": user_data.cpf,
        "phone": user_data.phone,
        "campaign_id": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    
    token = create_token(user_id, user_data.email, user_data.role.value)
    user_doc.pop("password")
    user_doc.pop("_id", None)
    
    return {"token": token, "user": user_doc}

@api_router.post("/auth/login", response_model=dict)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    token = create_token(user["id"], user["email"], user["role"])
    user.pop("password")
    user.pop("_id", None)
    
    return {"token": token, "user": user}

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# ============== CAMPAIGN ROUTES ==============
@api_router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(data: CampaignCreate, current_user: dict = Depends(get_current_user)):
    campaign_id = str(uuid.uuid4())
    campaign_doc = {
        "id": campaign_id,
        "candidate_name": data.candidate_name,
        "party": data.party,
        "position": data.position,
        "city": data.city,
        "state": data.state,
        "election_year": data.election_year,
        "owner_id": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.campaigns.insert_one(campaign_doc)
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"campaign_id": campaign_id}})
    
    campaign_doc.pop("_id", None)
    return campaign_doc

@api_router.get("/campaigns/my", response_model=Optional[CampaignResponse])
async def get_my_campaign(current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        return None
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    return campaign

@api_router.put("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: str, data: CampaignCreate, current_user: dict = Depends(get_current_user)):
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if campaign["owner_id"] != current_user["id"] and current_user["role"] != "contador":
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    update_data = data.model_dump()
    await db.campaigns.update_one({"id": campaign_id}, {"$set": update_data})
    
    updated = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    return updated

# ============== REVENUE ROUTES ==============
async def generate_recibo_eleitoral(campaign_id: str) -> str:
    """Generate sequential electoral receipt number"""
    # Get campaign info for the prefix
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        return None
    
    # Count existing revenues to generate sequence
    count = await db.revenues.count_documents({"campaign_id": campaign_id})
    sequence = count + 1
    
    # Format: UF-ANO-NUMCANDIDATO-SEQUENCIA
    uf = campaign.get("state", "XX")
    ano = campaign.get("election_year", datetime.now().year)
    num_cand = campaign.get("numero_candidato", "00000")
    
    return f"{uf}{ano}{num_cand}{sequence:05d}"

@api_router.post("/revenues", response_model=RevenueResponse)
async def create_revenue(data: RevenueCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    revenue_id = str(uuid.uuid4())
    revenue_data = data.model_dump()
    
    # Auto-generate recibo eleitoral if not provided
    if not revenue_data.get("recibo_eleitoral"):
        revenue_data["recibo_eleitoral"] = await generate_recibo_eleitoral(current_user["campaign_id"])
    
    revenue_doc = {
        "id": revenue_id,
        **revenue_data,
        "campaign_id": current_user["campaign_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.revenues.insert_one(revenue_doc)
    revenue_doc.pop("_id", None)
    return revenue_doc

@api_router.get("/revenues", response_model=List[RevenueResponse])
async def list_revenues(current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        return []
    revenues = await db.revenues.find({"campaign_id": current_user["campaign_id"]}, {"_id": 0}).to_list(1000)
    return revenues

@api_router.get("/revenues/{revenue_id}", response_model=RevenueResponse)
async def get_revenue(revenue_id: str, current_user: dict = Depends(get_current_user)):
    revenue = await db.revenues.find_one({"id": revenue_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not revenue:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    return revenue

@api_router.put("/revenues/{revenue_id}", response_model=RevenueResponse)
async def update_revenue(revenue_id: str, data: RevenueCreate, current_user: dict = Depends(get_current_user)):
    revenue = await db.revenues.find_one({"id": revenue_id, "campaign_id": current_user.get("campaign_id")})
    if not revenue:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    
    await db.revenues.update_one({"id": revenue_id}, {"$set": data.model_dump()})
    updated = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    return updated

@api_router.delete("/revenues/{revenue_id}")
async def delete_revenue(revenue_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.revenues.delete_one({"id": revenue_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    return {"message": "Receita excluída"}

@api_router.get("/revenues/{revenue_id}/recibo-pdf")
async def generate_recibo_pdf(revenue_id: str, current_user: dict = Depends(get_current_user)):
    """Generate electoral receipt PDF"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    revenue = await db.revenues.find_one(
        {"id": revenue_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not revenue:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER, fontSize=12))
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=16, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='RightAlign', alignment=2, fontSize=10))  # 2 = TA_RIGHT
    
    elements = []
    
    # Header
    elements.append(Paragraph("RECIBO ELEITORAL", styles['Title2']))
    elements.append(Paragraph(f"<b>Nº {revenue.get('recibo_eleitoral', 'N/A')}</b>", styles['Center']))
    elements.append(Spacer(1, 30))
    
    # Campaign info
    elements.append(Paragraph(f"<b>CANDIDATO(A):</b> {campaign.get('candidate_name', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CARGO:</b> {campaign.get('position', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>PARTIDO:</b> {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ DA CAMPANHA:</b> {campaign.get('cnpj', 'Não informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CIDADE/UF:</b> {campaign.get('city', '')}/{campaign.get('state', '')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Donation info
    elements.append(Paragraph("_" * 70, styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>DADOS DA DOAÇÃO</b>", styles['Center']))
    elements.append(Spacer(1, 10))
    
    tipo_receita_labels = {
        "doacao_financeira": "Doação Financeira",
        "doacao_estimavel": "Doação Estimável em Dinheiro",
        "recursos_proprios": "Recursos Próprios",
        "fundo_partidario": "Fundo Partidário",
        "fundo_eleitoral": "Fundo Especial de Financiamento de Campanha",
        "comercializacao": "Comercialização de Bens/Serviços",
        "rendimento_aplicacao": "Rendimento de Aplicação",
        "sobras_campanha": "Sobras de Campanha Anterior",
        "outros": "Outros"
    }
    
    forma_labels = {
        "pix": "PIX",
        "transferencia": "Transferência Bancária",
        "deposito": "Depósito em Conta",
        "cheque": "Cheque",
        "especie": "Espécie",
        "cartao_credito": "Cartão de Crédito",
        "cartao_debito": "Cartão de Débito",
        "estimavel": "Estimável em Dinheiro"
    }
    
    elements.append(Paragraph(f"<b>Tipo de Receita:</b> {tipo_receita_labels.get(revenue.get('tipo_receita'), revenue.get('tipo_receita', 'Não informado'))}", styles['Normal']))
    elements.append(Paragraph(f"<b>Forma de Recebimento:</b> {forma_labels.get(revenue.get('forma_recebimento'), revenue.get('forma_recebimento', 'Não informado'))}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data:</b> {revenue.get('date', '')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # Amount
    amount = revenue.get('amount', 0)
    elements.append(Paragraph(f"<b>VALOR: R$ {amount:,.2f}</b>", styles['Title2']))
    elements.append(Spacer(1, 20))
    
    # Donor info
    elements.append(Paragraph("_" * 70, styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>DADOS DO DOADOR</b>", styles['Center']))
    elements.append(Spacer(1, 10))
    
    tipo_doador_labels = {
        "pessoa_fisica": "Pessoa Física",
        "pessoa_juridica": "Pessoa Jurídica",
        "partido": "Partido Político",
        "candidato": "Candidato",
        "comite": "Comitê Financeiro",
        "fundo_partidario": "Fundo Partidário",
        "fundo_eleitoral": "Fundo Eleitoral"
    }
    
    elements.append(Paragraph(f"<b>Nome:</b> {revenue.get('donor_name', 'Não informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CPF/CNPJ:</b> {revenue.get('donor_cpf_cnpj', 'Não informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Tipo de Doador:</b> {tipo_doador_labels.get(revenue.get('tipo_doador'), revenue.get('tipo_doador', 'Não informado'))}", styles['Normal']))
    if revenue.get('donor_titulo_eleitor'):
        elements.append(Paragraph(f"<b>Título de Eleitor:</b> {revenue.get('donor_titulo_eleitor')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Descrição:</b> {revenue.get('description', '')}", styles['Normal']))
    elements.append(Spacer(1, 30))
    
    # Footer
    elements.append(Paragraph("_" * 70, styles['Normal']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"{campaign.get('city', '')}, {datetime.now().strftime('%d de %B de %Y')}", styles['RightAlign']))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("_" * 40, styles['Center']))
    elements.append(Paragraph(f"{campaign.get('candidate_name', '')}", styles['Center']))
    elements.append(Paragraph("Assinatura do Candidato", styles['Center']))
    elements.append(Spacer(1, 30))
    
    # Legal notice
    elements.append(Paragraph("<i>Este recibo foi emitido em conformidade com a Resolução TSE nº 23.607/2019</i>", styles['Center']))
    elements.append(Paragraph(f"<i>Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</i>", styles['Center']))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"recibo_eleitoral_{revenue.get('recibo_eleitoral', revenue_id)}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ============== EXPENSE ROUTES ==============
@api_router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(data: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    expense_id = str(uuid.uuid4())
    expense_doc = {
        "id": expense_id,
        **data.model_dump(),
        "campaign_id": current_user["campaign_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.expenses.insert_one(expense_doc)
    expense_doc.pop("_id", None)
    return expense_doc

@api_router.get("/expenses", response_model=List[ExpenseResponse])
async def list_expenses(current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        return []
    expenses = await db.expenses.find({"campaign_id": current_user["campaign_id"]}, {"_id": 0}).to_list(1000)
    return expenses

@api_router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    expense = await db.expenses.find_one({"id": expense_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")
    return expense

@api_router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: str, data: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    expense = await db.expenses.find_one({"id": expense_id, "campaign_id": current_user.get("campaign_id")})
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")
    
    await db.expenses.update_one({"id": expense_id}, {"$set": data.model_dump()})
    updated = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return updated

@api_router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.expenses.delete_one({"id": expense_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")
    return {"message": "Despesa excluída"}

# ============== CONTRACT ROUTES ==============
@api_router.post("/contracts", response_model=ContractResponse)
async def create_contract(data: ContractCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Get campaign data for contract generation
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    
    contract_id = str(uuid.uuid4())
    contract_doc = {
        "id": contract_id,
        **data.model_dump(),
        "campaign_id": current_user["campaign_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Generate contract HTML if template type is specified
    if data.template_type:
        contract_doc["contract_html"] = generate_contract_html(contract_doc, campaign)
    
    await db.contracts.insert_one(contract_doc)
    contract_doc.pop("_id", None)
    
    # Auto-generate expenses based on installment config
    if data.gerar_despesas:
        await generate_contract_expenses(contract_id, data, current_user["campaign_id"])
    
    return contract_doc

async def generate_contract_expenses(contract_id: str, data: ContractCreate, campaign_id: str):
    """Generate expenses based on contract installment configuration"""
    total_value = data.value
    
    # If parcelas_config is provided, use it
    if data.parcelas_config and len(data.parcelas_config) > 0:
        for i, parcela in enumerate(data.parcelas_config):
            percentual = parcela.get("percentual", 100 / len(data.parcelas_config))
            data_vencimento = parcela.get("data_vencimento", data.start_date)
            parcela_value = total_value * (percentual / 100)
            
            expense_doc = {
                "id": str(uuid.uuid4()),
                "description": f"{data.title} - Parcela {i+1}/{len(data.parcelas_config)}",
                "amount": round(parcela_value, 2),
                "category": "servicos_terceiros",
                "supplier_name": data.contractor_name,
                "supplier_cpf_cnpj": data.contractor_cpf_cnpj,
                "date": data_vencimento,
                "payment_status": "pendente",
                "contract_id": contract_id,
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.expenses.insert_one(expense_doc)
    else:
        # Default: split equally based on num_parcelas
        num_parcelas = data.num_parcelas or 1
        parcela_value = total_value / num_parcelas
        
        for i in range(num_parcelas):
            # Calculate due date based on start and end date
            if num_parcelas == 1:
                due_date = data.start_date
            elif num_parcelas == 2:
                due_date = data.start_date if i == 0 else data.end_date
            else:
                # Distribute evenly between start and end
                start = datetime.fromisoformat(data.start_date)
                end = datetime.fromisoformat(data.end_date)
                days_diff = (end - start).days
                days_offset = int(days_diff * i / (num_parcelas - 1)) if num_parcelas > 1 else 0
                due_date = (start + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            
            expense_doc = {
                "id": str(uuid.uuid4()),
                "description": f"{data.title} - Parcela {i+1}/{num_parcelas}" if num_parcelas > 1 else f"{data.title}",
                "amount": round(parcela_value, 2),
                "category": "servicos_terceiros",
                "supplier_name": data.contractor_name,
                "supplier_cpf_cnpj": data.contractor_cpf_cnpj,
                "date": due_date,
                "payment_status": "pendente",
                "contract_id": contract_id,
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.expenses.insert_one(expense_doc)

@api_router.get("/contracts", response_model=List[ContractResponse])
async def list_contracts(current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        return []
    contracts = await db.contracts.find({"campaign_id": current_user["campaign_id"]}, {"_id": 0}).to_list(1000)
    return contracts

@api_router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: str, current_user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return contract

@api_router.get("/contracts/{contract_id}/html")
async def get_contract_html(contract_id: str, current_user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    html = generate_contract_html(contract, campaign)
    return {"html": html}

@api_router.put("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(contract_id: str, data: ContractCreate, current_user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    update_data = data.model_dump()
    
    # Regenerate HTML if template type exists
    if data.template_type:
        update_data["contract_html"] = generate_contract_html({**contract, **update_data}, campaign)
    
    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
    updated = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    return updated

@api_router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.contracts.delete_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return {"message": "Contrato excluído"}

# ============== SIGNATURE ROUTES ==============
class SignatureRequest(BaseModel):
    contract_id: str
    locador_email: str

class SignContract(BaseModel):
    signature_hash: str

@api_router.post("/contracts/{contract_id}/request-signature")
async def request_signature(contract_id: str, data: SignatureRequest, current_user: dict = Depends(get_current_user)):
    """Request signature from locador (service provider)"""
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    # Generate signature token
    token = generate_signature_token(contract_id, data.locador_email, "locador")
    
    # Update contract with signature request
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {
            "signature_request_token": token,
            "locador_email": data.locador_email,
            "status": "aguardando_assinatura"
        }}
    )
    
    # In production, send email with signature link
    # For now, return the token for testing
    return {
        "message": "Solicitação de assinatura enviada",
        "signature_link": f"/assinar/{token}",
        "token": token
    }

@api_router.post("/contracts/{contract_id}/sign-locatario")
async def sign_as_locatario(contract_id: str, data: SignContract, current_user: dict = Depends(get_current_user)):
    """Sign contract as locatário (candidate)"""
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update with signature
    update_data = {
        "locatario_assinatura_hash": data.signature_hash,
        "locatario_assinatura_data": now
    }
    
    # Check if both parties signed
    both_signed = False
    if contract.get("locador_assinatura_hash"):
        update_data["status"] = "ativo"
        both_signed = True
    else:
        update_data["status"] = "assinado_locatario"
    
    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
    
    # Regenerate HTML with signature
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    html = generate_contract_html(updated_contract, campaign)
    await db.contracts.update_one({"id": contract_id}, {"$set": {"contract_html": html}})
    
    # Generate PDF automatically when both parties sign
    pdf_generated = False
    if both_signed:
        try:
            pdf_path = await generate_and_store_contract_pdf(contract_id, updated_contract, campaign)
            if pdf_path:
                await db.contracts.update_one(
                    {"id": contract_id},
                    {"$set": {"pdf_path": pdf_path, "pdf_generated_at": now}}
                )
                pdf_generated = True
        except Exception as e:
            logging.error(f"Failed to generate contract PDF: {e}")
    
    return {
        "message": "Contrato assinado pelo locatário",
        "status": update_data["status"],
        "pdf_generated": pdf_generated
    }

@api_router.post("/contracts/sign-locador/{token}")
async def sign_as_locador(token: str, data: SignContract):
    """Sign contract as locador (service provider) using token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        contract_id = payload["contract_id"]
        
        contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        if not contract:
            raise HTTPException(status_code=404, detail="Contrato não encontrado")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update with signature
        update_data = {
            "locador_assinatura_hash": data.signature_hash,
            "locador_assinatura_data": now
        }
        
        # Check if both parties signed
        both_signed = False
        if contract.get("locatario_assinatura_hash"):
            update_data["status"] = "ativo"
            both_signed = True
        else:
            update_data["status"] = "assinado_locador"
        
        await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
        
        # Regenerate HTML
        campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
        updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        html = generate_contract_html(updated_contract, campaign)
        await db.contracts.update_one({"id": contract_id}, {"$set": {"contract_html": html}})
        
        # Generate PDF automatically when both parties sign
        pdf_generated = False
        if both_signed:
            try:
                pdf_path = await generate_and_store_contract_pdf(contract_id, updated_contract, campaign)
                if pdf_path:
                    await db.contracts.update_one(
                        {"id": contract_id},
                        {"$set": {"pdf_path": pdf_path, "pdf_generated_at": now}}
                    )
                    pdf_generated = True
            except Exception as e:
                logging.error(f"Failed to generate contract PDF: {e}")
        
        return {
            "message": "Contrato assinado pelo locador",
            "status": update_data["status"],
            "pdf_generated": pdf_generated
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token inválido")

async def generate_and_store_contract_pdf(contract_id: str, contract: dict, campaign: dict) -> str:
    """Generate PDF of signed contract and store it"""
    if not PDF_AVAILABLE:
        return None
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER, fontSize=11))
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=16, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Signature', alignment=TA_CENTER, fontSize=9, textColor=colors.darkblue))
    
    elements = []
    
    # Header with campaign info
    elements.append(Paragraph(f"<b>CAMPANHA ELEITORAL {campaign.get('election_year', '')}</b>", styles['Center']))
    elements.append(Paragraph(f"{campaign.get('candidate_name', '')} - {campaign.get('party', '')}", styles['Center']))
    elements.append(Spacer(1, 20))
    
    # Title
    title = contract.get("title", "CONTRATO DE PRESTAÇÃO DE SERVIÇOS")
    elements.append(Paragraph(title.upper(), styles['Title2']))
    elements.append(Spacer(1, 20))
    
    # Contract HTML content converted to paragraphs
    contract_html = contract.get("contract_html", "")
    if contract_html:
        import re
        text = re.sub(r'<br\s*/?>', '\n', contract_html)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        for para in text.split('\n\n'):
            if para.strip():
                elements.append(Paragraph(para.strip(), styles['Justify']))
                elements.append(Spacer(1, 8))
    
    # Signature section
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("<b>===== ASSINATURAS DIGITAIS =====</b>", styles['Center']))
    elements.append(Spacer(1, 20))
    
    # Locatário signature
    if contract.get("locatario_assinatura_hash"):
        elements.append(Paragraph("<b>LOCATÁRIO / CONTRATANTE:</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {campaign.get('candidate_name', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data da assinatura: {contract.get('locatario_assinatura_data', 'N/A')[:19].replace('T', ' ')}", styles['Normal']))
        elements.append(Paragraph(f"Hash de validação: {contract.get('locatario_assinatura_hash', '')[:32]}...", styles['Signature']))
        elements.append(Spacer(1, 20))
    
    # Locador signature
    if contract.get("locador_assinatura_hash"):
        elements.append(Paragraph("<b>LOCADOR / CONTRATADO:</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {contract.get('locador_nome', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"CPF/CNPJ: {contract.get('locador_cpf', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data da assinatura: {contract.get('locador_assinatura_data', 'N/A')[:19].replace('T', ' ')}", styles['Normal']))
        elements.append(Paragraph(f"Hash de validação: {contract.get('locador_assinatura_hash', '')[:32]}...", styles['Signature']))
        elements.append(Spacer(1, 20))
    
    # Footer with validation info
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 60, styles['Center']))
    elements.append(Paragraph("<i>Documento gerado eletronicamente pelo sistema Eleitora 360</i>", styles['Center']))
    elements.append(Paragraph(f"<i>ID do Contrato: {contract_id}</i>", styles['Signature']))
    elements.append(Paragraph(f"<i>Gerado em: {datetime.now(timezone.utc).strftime('%d/%m/%Y às %H:%M:%S')} UTC</i>", styles['Signature']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Store PDF in database
    pdf_data = buffer.getvalue()
    pdf_id = str(uuid.uuid4())
    
    pdf_doc = {
        "id": pdf_id,
        "contract_id": contract_id,
        "campaign_id": campaign.get("id"),
        "filename": f"contrato_assinado_{contract_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        "data": pdf_data,
        "size": len(pdf_data),
        "content_type": "application/pdf",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.contract_pdfs.insert_one(pdf_doc)
    
    return pdf_id

@api_router.get("/contracts/verify/{token}")
async def verify_signature_token(token: str):
    """Verify signature token and get contract preview"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        contract_id = payload["contract_id"]
        
        contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        if not contract:
            raise HTTPException(status_code=404, detail="Contrato não encontrado")
        
        campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
        html = generate_contract_html(contract, campaign)
        
        return {
            "valid": True,
            "contract_id": contract_id,
            "contract_html": html,
            "locador_nome": contract.get("locador_nome"),
            "candidate_name": campaign.get("candidate_name"),
            "value": contract.get("value"),
            "status": contract.get("status")
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token inválido")

@api_router.get("/contract-templates")
async def get_contract_templates():
    """Get available contract templates"""
    return {
        "templates": [
            {
                "type": "bem_movel",
                "name": "Locação de Bem Móvel",
                "description": "Contrato para locação de equipamentos, rádios, etc."
            },
            {
                "type": "espaco_evento",
                "name": "Locação de Espaço para Evento",
                "description": "Contrato para locação de espaço para evento eleitoral"
            },
            {
                "type": "imovel",
                "name": "Locação de Imóvel",
                "description": "Contrato para locação de imóvel (comitê, escritório)"
            },
            {
                "type": "veiculo_com_motorista",
                "name": "Locação de Veículo com Motorista",
                "description": "Contrato para veículo com motorista (carro de som, paredão)"
            },
            {
                "type": "veiculo_sem_motorista",
                "name": "Locação de Veículo sem Motorista",
                "description": "Contrato para locação de veículo sem motorista"
            }
        ]
    }

# ============== REFERENCE DATA ROUTES ==============
@api_router.get("/reference/partidos")
async def get_partidos():
    """Get list of Brazilian political parties"""
    return {
        "partidos": [
            {"sigla": "AGIR", "nome": "Agir", "numero": 36},
            {"sigla": "AVANTE", "nome": "Avante", "numero": 70},
            {"sigla": "CIDADANIA", "nome": "Cidadania", "numero": 23},
            {"sigla": "DC", "nome": "Democracia Cristã", "numero": 27},
            {"sigla": "MDB", "nome": "Movimento Democrático Brasileiro", "numero": 15},
            {"sigla": "MOBILIZA", "nome": "Mobiliza", "numero": 33},
            {"sigla": "NOVO", "nome": "Partido Novo", "numero": 30},
            {"sigla": "PATRIOTA", "nome": "Patriota", "numero": 51},
            {"sigla": "PCB", "nome": "Partido Comunista Brasileiro", "numero": 21},
            {"sigla": "PCdoB", "nome": "Partido Comunista do Brasil", "numero": 65},
            {"sigla": "PCO", "nome": "Partido da Causa Operária", "numero": 29},
            {"sigla": "PDT", "nome": "Partido Democrático Trabalhista", "numero": 12},
            {"sigla": "PL", "nome": "Partido Liberal", "numero": 22},
            {"sigla": "PMB", "nome": "Partido da Mulher Brasileira", "numero": 35},
            {"sigla": "PMN", "nome": "Partido da Mobilização Nacional", "numero": 33},
            {"sigla": "PODE", "nome": "Podemos", "numero": 20},
            {"sigla": "PP", "nome": "Progressistas", "numero": 11},
            {"sigla": "PRD", "nome": "Partido Renovação Democrática", "numero": 25},
            {"sigla": "PROS", "nome": "Partido Republicano da Ordem Social", "numero": 90},
            {"sigla": "PRTB", "nome": "Partido Renovador Trabalhista Brasileiro", "numero": 28},
            {"sigla": "PSB", "nome": "Partido Socialista Brasileiro", "numero": 40},
            {"sigla": "PSC", "nome": "Partido Social Cristão", "numero": 20},
            {"sigla": "PSD", "nome": "Partido Social Democrático", "numero": 55},
            {"sigla": "PSDB", "nome": "Partido da Social Democracia Brasileira", "numero": 45},
            {"sigla": "PSOL", "nome": "Partido Socialismo e Liberdade", "numero": 50},
            {"sigla": "PSTU", "nome": "Partido Socialista dos Trabalhadores Unificado", "numero": 16},
            {"sigla": "PT", "nome": "Partido dos Trabalhadores", "numero": 13},
            {"sigla": "PTB", "nome": "Partido Trabalhista Brasileiro", "numero": 14},
            {"sigla": "PV", "nome": "Partido Verde", "numero": 43},
            {"sigla": "REDE", "nome": "Rede Sustentabilidade", "numero": 18},
            {"sigla": "REPUBLICANOS", "nome": "Republicanos", "numero": 10},
            {"sigla": "SOLIDARIEDADE", "nome": "Solidariedade", "numero": 77},
            {"sigla": "UNIÃO", "nome": "União Brasil", "numero": 44},
            {"sigla": "UP", "nome": "Unidade Popular", "numero": 80}
        ]
    }

@api_router.get("/reference/estados")
async def get_estados():
    """Get list of Brazilian states with regions"""
    return {
        "estados": [
            {"uf": "AC", "nome": "Acre", "regiao": "Norte"},
            {"uf": "AL", "nome": "Alagoas", "regiao": "Nordeste"},
            {"uf": "AP", "nome": "Amapá", "regiao": "Norte"},
            {"uf": "AM", "nome": "Amazonas", "regiao": "Norte"},
            {"uf": "BA", "nome": "Bahia", "regiao": "Nordeste"},
            {"uf": "CE", "nome": "Ceará", "regiao": "Nordeste"},
            {"uf": "DF", "nome": "Distrito Federal", "regiao": "Centro-Oeste"},
            {"uf": "ES", "nome": "Espírito Santo", "regiao": "Sudeste"},
            {"uf": "GO", "nome": "Goiás", "regiao": "Centro-Oeste"},
            {"uf": "MA", "nome": "Maranhão", "regiao": "Nordeste"},
            {"uf": "MT", "nome": "Mato Grosso", "regiao": "Centro-Oeste"},
            {"uf": "MS", "nome": "Mato Grosso do Sul", "regiao": "Centro-Oeste"},
            {"uf": "MG", "nome": "Minas Gerais", "regiao": "Sudeste"},
            {"uf": "PA", "nome": "Pará", "regiao": "Norte"},
            {"uf": "PB", "nome": "Paraíba", "regiao": "Nordeste"},
            {"uf": "PR", "nome": "Paraná", "regiao": "Sul"},
            {"uf": "PE", "nome": "Pernambuco", "regiao": "Nordeste"},
            {"uf": "PI", "nome": "Piauí", "regiao": "Nordeste"},
            {"uf": "RJ", "nome": "Rio de Janeiro", "regiao": "Sudeste"},
            {"uf": "RN", "nome": "Rio Grande do Norte", "regiao": "Nordeste"},
            {"uf": "RS", "nome": "Rio Grande do Sul", "regiao": "Sul"},
            {"uf": "RO", "nome": "Rondônia", "regiao": "Norte"},
            {"uf": "RR", "nome": "Roraima", "regiao": "Norte"},
            {"uf": "SC", "nome": "Santa Catarina", "regiao": "Sul"},
            {"uf": "SP", "nome": "São Paulo", "regiao": "Sudeste"},
            {"uf": "SE", "nome": "Sergipe", "regiao": "Nordeste"},
            {"uf": "TO", "nome": "Tocantins", "regiao": "Norte"}
        ],
        "regioes": ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
    }

@api_router.get("/reference/bancos")
async def get_bancos():
    """Get list of Brazilian banks"""
    return {
        "bancos": [
            {"codigo": "001", "nome": "Banco do Brasil"},
            {"codigo": "033", "nome": "Santander"},
            {"codigo": "104", "nome": "Caixa Econômica Federal"},
            {"codigo": "237", "nome": "Bradesco"},
            {"codigo": "341", "nome": "Itaú"},
            {"codigo": "399", "nome": "HSBC"},
            {"codigo": "422", "nome": "Safra"},
            {"codigo": "745", "nome": "Citibank"},
            {"codigo": "756", "nome": "Sicoob"},
            {"codigo": "041", "nome": "Banrisul"},
            {"codigo": "070", "nome": "BRB"},
            {"codigo": "077", "nome": "Inter"},
            {"codigo": "212", "nome": "Original"},
            {"codigo": "260", "nome": "Nubank"},
            {"codigo": "290", "nome": "PagBank"},
            {"codigo": "336", "nome": "C6 Bank"},
            {"codigo": "380", "nome": "PicPay"},
            {"codigo": "748", "nome": "Sicredi"}
        ]
    }

@api_router.get("/reference/cargos")
async def get_cargos():
    """Get list of electoral positions"""
    return {
        "cargos": [
            {"codigo": "1", "nome": "Presidente"},
            {"codigo": "2", "nome": "Vice-Presidente"},
            {"codigo": "3", "nome": "Governador"},
            {"codigo": "4", "nome": "Vice-Governador"},
            {"codigo": "5", "nome": "Senador"},
            {"codigo": "6", "nome": "Deputado Federal"},
            {"codigo": "7", "nome": "Deputado Estadual"},
            {"codigo": "8", "nome": "Deputado Distrital"},
            {"codigo": "11", "nome": "Prefeito"},
            {"codigo": "12", "nome": "Vice-Prefeito"},
            {"codigo": "13", "nome": "Vereador"}
        ]
    }

# ============== SPCE EXPORT ROUTES ==============
@api_router.get("/export/spce-doacoes")
async def export_spce_doacoes(current_user: dict = Depends(get_current_user)):
    """Export donations in SPCE format (DOACINTE layout)"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    if not campaign.get("cnpj"):
        raise HTTPException(status_code=400, detail="CNPJ da campanha não configurado")
    
    # Generate SPCE format file
    lines = []
    
    # HEADER (Record type 1)
    cnpj = campaign.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "").zfill(14)
    now = datetime.now(timezone.utc)
    data_mov = now.strftime("%d%m%Y%H%M")
    banco = campaign.get("conta_doacao_banco", "").zfill(3)
    agencia = campaign.get("conta_doacao_agencia", "").zfill(8)
    agencia_dv = "00"
    conta = campaign.get("conta_doacao_numero", "").zfill(18)
    conta_dv = campaign.get("conta_doacao_digito", "").zfill(2)
    
    header = f"1{cnpj}{data_mov}{banco}{agencia}{agencia_dv}{conta}{conta_dv}400DOACINTE{' ' * 96}"
    lines.append(header[:167])
    
    # DETAILS (Record type 2) - Only donations (PF)
    donation_count = 0
    for rev in revenues:
        if rev.get("category") in ["doacao_pf", "recursos_proprios"]:
            donation_count += 1
            
            tipo_doacao = "03" if rev.get("category") == "doacao_pf" else "02"
            especie = "19"  # PIX by default
            cpf = rev.get("donor_cpf_cnpj", "").replace(".", "").replace("-", "").zfill(11)
            nome = rev.get("donor_name", "DOADOR NAO IDENTIFICADO")[:60].ljust(60)
            
            date_str = rev.get("date", "")
            try:
                date_obj = datetime.fromisoformat(date_str)
                data_doacao = date_obj.strftime("%d%m%Y")
            except:
                data_doacao = now.strftime("%d%m%Y")
            
            valor = int(rev.get("amount", 0) * 100)
            valor_str = str(valor).zfill(18)
            
            recibo = rev.get("receipt_number", "")[:21].ljust(21)
            doc = " " * 23
            autorizacao = " " * 20
            
            detail = f"2{recibo}{doc}{autorizacao}{tipo_doacao}{especie}{cpf}F{nome}{data_doacao}{valor_str}"
            lines.append(detail[:167])
    
    # TRAILER (Record type 9)
    trailer = f"9{str(donation_count).zfill(9)}{' ' * 157}"
    lines.append(trailer[:167])
    
    # Generate filename
    filename = f"ATSEDOACINTE{now.strftime('%Y%m%d')}001.TXT"
    
    return {
        "filename": filename,
        "content": "\n".join(lines),
        "total_doacoes": donation_count,
        "format": "SPCE-DOACINTE"
    }

# ============== PAYMENT ROUTES ==============
@api_router.post("/payments", response_model=PaymentResponse)
async def create_payment(data: PaymentCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    payment_id = str(uuid.uuid4())
    payment_doc = {
        "id": payment_id,
        **data.model_dump(),
        "campaign_id": current_user["campaign_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_doc)
    payment_doc.pop("_id", None)
    return payment_doc

@api_router.get("/payments", response_model=List[PaymentResponse])
async def list_payments(current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        return []
    payments = await db.payments.find({"campaign_id": current_user["campaign_id"]}, {"_id": 0}).to_list(1000)
    return payments

@api_router.get("/payments/alerts")
async def get_payment_alerts(
    days_ahead: int = Query(default=7, description="Days to look ahead"),
    current_user: dict = Depends(get_current_user)
):
    """Get payments due within the next X days"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return {"alerts": [], "total": 0}
    
    today = datetime.now(timezone.utc).date()
    future_date = today + timedelta(days=days_ahead)
    
    # Get all pending payments
    payments = await db.payments.find(
        {"campaign_id": campaign_id, "status": "pendente"},
        {"_id": 0}
    ).to_list(1000)
    
    alerts = []
    for p in payments:
        try:
            due_date = datetime.fromisoformat(p["due_date"]).date()
            if due_date <= future_date:
                days_until = (due_date - today).days
                alerts.append({
                    **p,
                    "days_until_due": days_until,
                    "is_overdue": days_until < 0,
                    "urgency": "high" if days_until <= 2 else ("medium" if days_until <= 5 else "low")
                })
        except:
            pass
    
    # Sort by due date
    alerts.sort(key=lambda x: x.get("days_until_due", 999))
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "overdue_count": len([a for a in alerts if a.get("is_overdue")]),
        "due_today": len([a for a in alerts if a.get("days_until_due") == 0])
    }

@api_router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, current_user: dict = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return payment

@api_router.put("/payments/{payment_id}", response_model=PaymentResponse)
async def update_payment(payment_id: str, data: PaymentCreate, current_user: dict = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id, "campaign_id": current_user.get("campaign_id")})
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    
    await db.payments.update_one({"id": payment_id}, {"$set": data.model_dump()})
    updated = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    return updated

@api_router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.payments.delete_one({"id": payment_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return {"message": "Pagamento excluído"}

# ============== DASHBOARD ROUTES ==============
@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return DashboardStats(
            total_revenues=0,
            total_expenses=0,
            balance=0,
            pending_payments=0,
            active_contracts=0,
            revenues_by_category={},
            expenses_by_category={},
            monthly_flow=[]
        )
    
    # Get totals
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    payments = await db.payments.find({"campaign_id": campaign_id, "status": "pendente"}, {"_id": 0}).to_list(1000)
    contracts = await db.contracts.find({"campaign_id": campaign_id, "status": "ativo"}, {"_id": 0}).to_list(1000)
    
    total_revenues = sum(r.get("amount", 0) for r in revenues)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    # Group by category
    revenues_by_cat = {}
    for r in revenues:
        cat = r.get("category", "outros")
        revenues_by_cat[cat] = revenues_by_cat.get(cat, 0) + r.get("amount", 0)
    
    expenses_by_cat = {}
    for e in expenses:
        cat = e.get("category", "outros")
        expenses_by_cat[cat] = expenses_by_cat.get(cat, 0) + e.get("amount", 0)
    
    # Monthly flow
    monthly_flow = []
    months = {}
    for r in revenues:
        month = r.get("date", "")[:7]
        if month not in months:
            months[month] = {"month": month, "receitas": 0, "despesas": 0}
        months[month]["receitas"] += r.get("amount", 0)
    
    for e in expenses:
        month = e.get("date", "")[:7]
        if month not in months:
            months[month] = {"month": month, "receitas": 0, "despesas": 0}
        months[month]["despesas"] += e.get("amount", 0)
    
    monthly_flow = sorted(months.values(), key=lambda x: x["month"])
    
    return DashboardStats(
        total_revenues=total_revenues,
        total_expenses=total_expenses,
        balance=total_revenues - total_expenses,
        pending_payments=len(payments),
        active_contracts=len(contracts),
        revenues_by_category=revenues_by_cat,
        expenses_by_category=expenses_by_cat,
        monthly_flow=monthly_flow
    )

@api_router.get("/dashboard/conformidade-tse")
async def get_conformidade_tse(current_user: dict = Depends(get_current_user)):
    """Dashboard de conformidade TSE - verifica completude dos dados para prestação de contas"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return {
            "status": "sem_campanha",
            "message": "Configure uma campanha primeiro",
            "completude_geral": 0,
            "itens": []
        }
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    itens = []
    total_peso = 0
    peso_completo = 0
    
    # 1. DADOS DA CAMPANHA (peso 20)
    dados_campanha = []
    campos_campanha = [
        ("candidate_name", "Nome do Candidato"),
        ("party", "Partido"),
        ("position", "Cargo"),
        ("city", "Cidade"),
        ("state", "Estado"),
        ("election_year", "Ano da Eleição"),
        ("cnpj", "CNPJ da Campanha"),
        ("numero_candidato", "Número do Candidato"),
        ("cpf_candidato", "CPF do Candidato"),
        ("eleitores", "Número de Eleitores")
    ]
    
    for campo, label in campos_campanha:
        valor = campaign.get(campo)
        if valor:
            dados_campanha.append({"campo": label, "status": "ok", "valor": str(valor)[:50]})
        else:
            dados_campanha.append({"campo": label, "status": "pendente", "valor": None})
    
    completos_campanha = len([d for d in dados_campanha if d["status"] == "ok"])
    total_campanha = len(dados_campanha)
    perc_campanha = (completos_campanha / total_campanha * 100) if total_campanha > 0 else 0
    
    itens.append({
        "categoria": "Dados da Campanha",
        "peso": 20,
        "completude": round(perc_campanha, 1),
        "completos": completos_campanha,
        "total": total_campanha,
        "detalhes": dados_campanha,
        "prioridade": "alta" if perc_campanha < 80 else "baixa"
    })
    total_peso += 20
    peso_completo += (perc_campanha / 100) * 20
    
    # 2. RECEITAS (peso 25)
    receitas_completas = 0
    receitas_pendentes = []
    
    for r in revenues:
        campos_obrigatorios = ["description", "amount", "date", "donor_name", "donor_cpf_cnpj", "tipo_receita", "forma_recebimento", "recibo_eleitoral"]
        campos_faltando = [c for c in campos_obrigatorios if not r.get(c)]
        
        if not campos_faltando:
            receitas_completas += 1
        else:
            receitas_pendentes.append({
                "id": r.get("id"),
                "descricao": r.get("description", "Sem descrição")[:30],
                "campos_faltando": campos_faltando
            })
    
    perc_receitas = (receitas_completas / len(revenues) * 100) if revenues else 100
    
    itens.append({
        "categoria": "Receitas",
        "peso": 25,
        "completude": round(perc_receitas, 1),
        "completos": receitas_completas,
        "total": len(revenues),
        "pendentes": receitas_pendentes[:5],  # Mostrar apenas 5 primeiros
        "prioridade": "alta" if perc_receitas < 80 else "baixa"
    })
    total_peso += 25
    peso_completo += (perc_receitas / 100) * 25
    
    # 3. DESPESAS (peso 25)
    despesas_completas = 0
    despesas_pendentes = []
    
    for e in expenses:
        campos_obrigatorios = ["description", "amount", "date", "supplier_name", "supplier_cpf_cnpj", "category"]
        campos_faltando = [c for c in campos_obrigatorios if not e.get(c)]
        
        if not campos_faltando:
            despesas_completas += 1
        else:
            despesas_pendentes.append({
                "id": e.get("id"),
                "descricao": e.get("description", "Sem descrição")[:30],
                "campos_faltando": campos_faltando
            })
    
    perc_despesas = (despesas_completas / len(expenses) * 100) if expenses else 100
    
    itens.append({
        "categoria": "Despesas",
        "peso": 25,
        "completude": round(perc_despesas, 1),
        "completos": despesas_completas,
        "total": len(expenses),
        "pendentes": despesas_pendentes[:5],
        "prioridade": "alta" if perc_despesas < 80 else "baixa"
    })
    total_peso += 25
    peso_completo += (perc_despesas / 100) * 25
    
    # 4. CONTRATOS (peso 15)
    contratos_completos = 0
    contratos_pendentes = []
    
    for c in contracts:
        problemas = []
        if c.get("status") != "ativo":
            problemas.append("status_invalido")
        if not c.get("locador_assinatura_hash"):
            problemas.append("falta_assinatura_locador")
        if not c.get("locatario_assinatura_hash"):
            problemas.append("falta_assinatura_locatario")
        if not c.get("locador_cpf"):
            problemas.append("falta_cpf_locador")
        
        if not problemas:
            contratos_completos += 1
        else:
            contratos_pendentes.append({
                "id": c.get("id"),
                "titulo": c.get("title", "Sem título")[:30],
                "problemas": problemas
            })
    
    perc_contratos = (contratos_completos / len(contracts) * 100) if contracts else 100
    
    itens.append({
        "categoria": "Contratos",
        "peso": 15,
        "completude": round(perc_contratos, 1),
        "completos": contratos_completos,
        "total": len(contracts),
        "pendentes": contratos_pendentes[:5],
        "prioridade": "media" if perc_contratos < 80 else "baixa"
    })
    total_peso += 15
    peso_completo += (perc_contratos / 100) * 15
    
    # 5. DOCUMENTOS/ANEXOS (peso 15)
    total_docs = 0
    docs_com_anexo = 0
    
    # Check receitas with attachments
    for r in revenues:
        total_docs += 1
        if r.get("attachment_id"):
            docs_com_anexo += 1
    
    # Check despesas with attachments
    for e in expenses:
        total_docs += 1
        if e.get("attachment_id"):
            docs_com_anexo += 1
    
    perc_docs = (docs_com_anexo / total_docs * 100) if total_docs > 0 else 100
    
    itens.append({
        "categoria": "Documentos Comprobatórios",
        "peso": 15,
        "completude": round(perc_docs, 1),
        "completos": docs_com_anexo,
        "total": total_docs,
        "prioridade": "media" if perc_docs < 50 else "baixa"
    })
    total_peso += 15
    peso_completo += (perc_docs / 100) * 15
    
    # Calcular completude geral
    completude_geral = (peso_completo / total_peso * 100) if total_peso > 0 else 0
    
    # Status geral
    if completude_geral >= 90:
        status = "pronto"
        message = "Sua prestação de contas está praticamente completa!"
    elif completude_geral >= 70:
        status = "quase_pronto"
        message = "Alguns ajustes são necessários antes de enviar."
    elif completude_geral >= 50:
        status = "em_andamento"
        message = "Ainda há campos importantes pendentes de preenchimento."
    else:
        status = "incompleto"
        message = "Muitos dados obrigatórios estão faltando."
    
    # Alertas e sugestões
    alertas = []
    if not campaign.get("cnpj"):
        alertas.append({
            "tipo": "erro",
            "mensagem": "CNPJ da campanha não configurado - obrigatório para exportação SPCE",
            "acao": "Vá em Configurações e preencha o CNPJ"
        })
    
    if not campaign.get("eleitores"):
        alertas.append({
            "tipo": "aviso",
            "mensagem": "Número de eleitores não configurado - necessário para cálculo de limite TSE",
            "acao": "Vá em Configurações e informe o número de eleitores do município"
        })
    
    receitas_sem_recibo = len([r for r in revenues if not r.get("recibo_eleitoral")])
    if receitas_sem_recibo > 0:
        alertas.append({
            "tipo": "aviso",
            "mensagem": f"{receitas_sem_recibo} receita(s) sem número de recibo eleitoral",
            "acao": "Edite as receitas e gere os recibos eleitorais"
        })
    
    despesas_sem_comprovante = len([e for e in expenses if not e.get("attachment_id")])
    if despesas_sem_comprovante > 0:
        alertas.append({
            "tipo": "info",
            "mensagem": f"{despesas_sem_comprovante} despesa(s) sem comprovante anexado",
            "acao": "Anexe os comprovantes de pagamento"
        })
    
    return {
        "status": status,
        "message": message,
        "completude_geral": round(completude_geral, 1),
        "itens": itens,
        "alertas": alertas,
        "resumo": {
            "total_receitas": len(revenues),
            "total_despesas": len(expenses),
            "total_contratos": len(contracts),
            "valor_receitas": sum(r.get("amount", 0) for r in revenues),
            "valor_despesas": sum(e.get("amount", 0) for e in expenses)
        }
    }

# ============== REPORTS ROUTES ==============
@api_router.get("/reports/tse")
async def generate_tse_report(current_user: dict = Depends(get_current_user)):
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Format TSE report data
    report = {
        "campanha": campaign,
        "receitas": [
            {
                "data": r.get("date"),
                "descricao": r.get("description"),
                "valor": r.get("amount"),
                "categoria": r.get("category"),
                "doador": r.get("donor_name"),
                "cpf_cnpj": r.get("donor_cpf_cnpj"),
                "recibo": r.get("receipt_number")
            }
            for r in revenues
        ],
        "despesas": [
            {
                "data": e.get("date"),
                "descricao": e.get("description"),
                "valor": e.get("amount"),
                "categoria": e.get("category"),
                "fornecedor": e.get("supplier_name"),
                "cpf_cnpj": e.get("supplier_cpf_cnpj"),
                "nota_fiscal": e.get("invoice_number")
            }
            for e in expenses
        ],
        "totais": {
            "total_receitas": sum(r.get("amount", 0) for r in revenues),
            "total_despesas": sum(e.get("amount", 0) for e in expenses),
            "saldo": sum(r.get("amount", 0) for r in revenues) - sum(e.get("amount", 0) for e in expenses)
        },
        "gerado_em": datetime.now(timezone.utc).isoformat()
    }
    
    return report

# ============== SPCE ZIP EXPORT ==============

@api_router.get("/export/spce-zip")
async def export_spce_zip(current_user: dict = Depends(get_current_user)):
    """Export complete SPCE package as ZIP file with all required folders and files"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    # Validate required SPCE fields
    cnpj = campaign.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha inválido ou não configurado")
    
    # Get all data
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    attachments = await db.attachments.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    date_str = datetime.now().strftime("%d%m%Y")
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Create SPCE folder structure
        folders = [
            "ASSUNCAO_DIVIDAS",
            "AVULSOS_OUTROS",
            "AVULSOS_SPCE",
            "COMERCIALIZACAO",
            "DEMONSTRATIVOS",
            "DESPESAS",
            "DEVOLUCAO_RECEITAS",
            "EXTRATOS_BANCARIOS",
            "EXTRATO_PRESTACAO",
            "NOTAS_EXPLICATIVAS",
            "RECEITAS",
            "REPRESENTANTES",
            "SIGILOSO_SPCE",
            "SOBRAS_CAMPANHA"
        ]
        
        # Create empty folders
        for folder in folders:
            zf.writestr(f"{folder}/", "")
        
        # Generate receipts for RECEITAS folder
        receitas_arquivos = []
        for i, rev in enumerate(revenues):
            donor_cpf = (rev.get("donor_cpf_cnpj") or "").replace(".", "").replace("-", "").replace("/", "")
            date_rev = rev.get("date", "").replace("-", "")
            if date_rev:
                date_rev = date_rev[6:8] + date_rev[4:6] + date_rev[0:4]  # DDMMYYYY
            
            # Generate hash for unique ID
            hash_id = hashlib.sha1(f"{rev.get('id', str(i))}".encode()).hexdigest()
            filename = f"REC_DOA_{hash_id}_{date_rev}_{donor_cpf}.pdf"
            
            # Create simple receipt content
            receipt_content = f"""RECIBO DE DOAÇÃO ELEITORAL

Campanha: {campaign.get('candidate_name', '')}
CNPJ: {cnpj}
Partido: {campaign.get('party', '')}

Doador: {rev.get('donor_name', '')}
CPF/CNPJ: {rev.get('donor_cpf_cnpj', '')}

Descrição: {rev.get('description', '')}
Valor: R$ {rev.get('amount', 0):,.2f}
Data: {rev.get('date', '')}
Categoria: {rev.get('category', '')}

Número do Recibo: {i + 1}
"""
            zf.writestr(f"RECEITAS/{filename}", receipt_content.encode('utf-8'))
            
            receitas_arquivos.append({
                "codigo": filename,
                "descricao": f"REC_DOA_{rev.get('donor_name', '').replace(' ', '_')[:20]}_{donor_cpf}_{date_rev}_R${rev.get('amount', 0):.2f}_{i+1}"
            })
        
        # Generate documents for DESPESAS folder
        despesas_arquivos = []
        for i, exp in enumerate(expenses):
            supplier_cpf = (exp.get("supplier_cpf_cnpj") or "").replace(".", "").replace("-", "").replace("/", "")
            date_exp = exp.get("date", "").replace("-", "")
            if date_exp:
                date_exp = date_exp[6:8] + date_exp[4:6] + date_exp[0:4]  # DDMMYYYY
            
            filename = f"DESP_{i+247}_{date_exp}_{supplier_cpf}.pdf"
            
            # Create expense document content
            expense_content = f"""COMPROVANTE DE DESPESA ELEITORAL

Campanha: {campaign.get('candidate_name', '')}
CNPJ: {cnpj}

Fornecedor: {exp.get('supplier_name', '')}
CPF/CNPJ: {exp.get('supplier_cpf_cnpj', '')}

Descrição: {exp.get('description', '')}
Valor: R$ {exp.get('amount', 0):,.2f}
Data: {exp.get('date', '')}
Categoria: {exp.get('category', '')}
Status: {exp.get('payment_status', 'pendente')}

Nota Fiscal: {exp.get('invoice_number', '-')}
"""
            zf.writestr(f"DESPESAS/{filename}", expense_content.encode('utf-8'))
            
            category_desc = exp.get('category', '').replace('_', ' ').title()
            despesas_arquivos.append({
                "codigo": filename,
                "descricao": f"DESP_{category_desc}_{exp.get('supplier_name', '').replace(' ', '_')[:20]}_{supplier_cpf}_{date_exp}_R${exp.get('amount', 0):.2f}_{i+247}"
            })
        
        # Generate DEMONSTRATIVOS
        demonstrativos_arquivos = []
        total_receitas = sum(r.get("amount", 0) for r in revenues)
        total_despesas = sum(e.get("amount", 0) for e in expenses)
        saldo = total_receitas - total_despesas
        
        # Relatório de Receitas e Despesas
        rel_content = f"""DEMONSTRATIVO DE RECEITAS E DESPESAS
Campanha: {campaign.get('candidate_name', '')}
CNPJ: {cnpj}
Data: {datetime.now().strftime('%d/%m/%Y')}

RESUMO FINANCEIRO
-----------------
Total de Receitas: R$ {total_receitas:,.2f}
Total de Despesas: R$ {total_despesas:,.2f}
Saldo: R$ {saldo:,.2f}

RECEITAS DETALHADAS
-------------------
"""
        for r in revenues:
            rel_content += f"- {r.get('date', '')} | {r.get('description', '')} | R$ {r.get('amount', 0):,.2f} | {r.get('donor_name', '')}\n"
        
        rel_content += f"\nDESPESAS DETALHADAS\n-------------------\n"
        for e in expenses:
            rel_content += f"- {e.get('date', '')} | {e.get('description', '')} | R$ {e.get('amount', 0):,.2f} | {e.get('supplier_name', '')}\n"
        
        rel_filename = f"REL_RECEITADESPESA_{cnpj}_{date_str}.pdf"
        zf.writestr(f"DEMONSTRATIVOS/{rel_filename}", rel_content.encode('utf-8'))
        demonstrativos_arquivos.append({"codigo": rel_filename, "descricao": rel_filename})
        
        # Relatório de Despesas Efetuadas
        desp_efetuadas = f"""RELATÓRIO DE DESPESAS EFETUADAS
Campanha: {campaign.get('candidate_name', '')}
CNPJ: {cnpj}
Data: {datetime.now().strftime('%d/%m/%Y')}

Total de Despesas: R$ {total_despesas:,.2f}
Despesas Pagas: R$ {sum(e.get('amount', 0) for e in expenses if e.get('payment_status') == 'pago'):,.2f}
Despesas Pendentes: R$ {sum(e.get('amount', 0) for e in expenses if e.get('payment_status') == 'pendente'):,.2f}
"""
        desp_filename = f"REL_DESPESAS_EFETUADAS_{cnpj}_{date_str}.pdf"
        zf.writestr(f"DEMONSTRATIVOS/{desp_filename}", desp_efetuadas.encode('utf-8'))
        demonstrativos_arquivos.append({"codigo": desp_filename, "descricao": desp_filename})
        
        # Include attached files in appropriate folders
        for att in attachments:
            entity_type = att.get("entity_type", "")
            file_path = UPLOAD_DIR / att.get("filename", "")
            
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    if entity_type == "revenue":
                        zf.writestr(f"RECEITAS/{att.get('original_name', att.get('filename'))}", file_content)
                    elif entity_type == "expense":
                        zf.writestr(f"DESPESAS/{att.get('original_name', att.get('filename'))}", file_content)
                    elif entity_type == "contract":
                        zf.writestr(f"AVULSOS_OUTROS/{att.get('original_name', att.get('filename'))}", file_content)
                except:
                    pass
        
        # Generate dados.info
        dados_info = {
            "codigoUnidadeEleitoral": campaign.get("city", "")[:5].upper().replace(" ", ""),
            "codigoEleicao": 619,
            "tipoPessoa": "CA",
            "descricaoUnidadeEleitoral": campaign.get("city", "").upper(),
            "numeroCandidatura": campaign.get("numero_candidato", ""),
            "categorias": [
                {"codigo": f, "descricao": f.replace("_", " ").title()}
                for f in folders
            ],
            "arquivos": {
                "RECEITAS": receitas_arquivos,
                "DESPESAS": despesas_arquivos,
                "DEMONSTRATIVOS": demonstrativos_arquivos
            },
            "tipoEntrega": "PARCIAL",
            "nome": campaign.get("candidate_name", ""),
            "turno": 1,
            "numeroCnpj": cnpj,
            "codigoPartido": campaign.get("party", "")[:2],
            "uf": campaign.get("state", ""),
            "anoEleicao": campaign.get("election_year", 2024),
            "descricaoCargoOrgao": campaign.get("position", ""),
            "numeroCpf": (campaign.get("cpf_candidato") or "").replace(".", "").replace("-", ""),
            "siglaPartido": campaign.get("party", ""),
            "numeroControle": f"000{cnpj}{campaign.get('state', '')}",
            "codigoTipoEntrega": "PAR",
            "codigoCargoOrgao": "11"
        }
        
        zf.writestr("dados.info", json.dumps(dados_info, ensure_ascii=False, indent=2))
    
    zip_buffer.seek(0)
    
    # Generate filename
    control_number = f"ATSEPJE_{cnpj}{campaign.get('state', 'XX')}_PAR"
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{control_number}.zip"'
        }
    )

# ============== FILE UPLOAD ROUTES ==============
ALLOWED_FILE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf"
}

@api_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file attachment (JPEG, PNG, PDF only)"""
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB)")
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, '.bin')
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    # Save file
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    # Save metadata to DB
    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    attachment_doc.pop("_id", None)
    
    return attachment_doc

@api_router.post("/expenses/{expense_id}/attach-receipt")
async def attach_expense_receipt(
    expense_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Attach receipt to expense and automatically mark as paid"""
    expense = await db.expenses.find_one(
        {"id": expense_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB)")
    
    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, '.bin')
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "entity_type": "expense",
        "entity_id": expense_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    
    # Update expense with attachment and mark as PAID
    await db.expenses.update_one(
        {"id": expense_id},
        {"$set": {"attachment_id": file_id, "payment_status": "pago"}}
    )
    
    updated_expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return {
        "message": "Comprovante anexado e despesa marcada como paga",
        "expense": updated_expense,
        "attachment": {**attachment_doc, "_id": None}
    }

@api_router.post("/revenues/{revenue_id}/attach-receipt")
async def attach_revenue_receipt(
    revenue_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Attach receipt to revenue"""
    revenue = await db.revenues.find_one(
        {"id": revenue_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not revenue:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB)")
    
    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, '.bin')
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "entity_type": "revenue",
        "entity_id": revenue_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    
    # Update revenue with attachment
    await db.revenues.update_one(
        {"id": revenue_id},
        {"$set": {"attachment_id": file_id}}
    )
    
    updated_revenue = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    return {
        "message": "Comprovante anexado com sucesso",
        "revenue": updated_revenue
    }

@api_router.post("/contracts/{contract_id}/attach")
async def attach_contract_document(
    contract_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Attach document to contract"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB)")
    
    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, '.bin')
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "entity_type": "contract",
        "entity_id": contract_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    
    # Update contract with attachment
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {"attachment_id": file_id}}
    )
    
    updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    return {
        "message": "Documento anexado com sucesso",
        "contract": updated_contract
    }

@api_router.get("/contracts/{contract_id}/expenses")
async def get_contract_expenses(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Get all expenses linked to a contract"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    expenses = await db.expenses.find(
        {"contract_id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "contract_id": contract_id,
        "contract_title": contract.get("title"),
        "total_value": contract.get("value"),
        "expenses": expenses,
        "total_paid": sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pago"),
        "total_pending": sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente")
    }

@api_router.get("/contracts/attachment-types")
async def get_attachment_types():
    """Get all available contract attachment types by contract template"""
    return CONTRACT_REQUIRED_ATTACHMENTS

@api_router.get("/contracts/{contract_id}/required-attachments")
async def get_contract_required_attachments(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Get list of required attachments for a contract based on its type"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    template_type = contract.get("template_type")
    required_list = CONTRACT_REQUIRED_ATTACHMENTS.get(template_type, [])
    
    # Get current attachments
    current_attachments = contract.get("attachments") or {}
    
    # Build response with status
    attachments_status = []
    for req in required_list:
        attachment_id = current_attachments.get(req["key"])
        attachment_info = None
        if attachment_id:
            attachment_info = await db.attachments.find_one({"id": attachment_id}, {"_id": 0})
        
        attachments_status.append({
            "key": req["key"],
            "label": req["label"],
            "required": req["required"],
            "uploaded": attachment_id is not None,
            "attachment_id": attachment_id,
            "attachment_info": attachment_info
        })
    
    return {
        "contract_id": contract_id,
        "template_type": template_type,
        "attachments": attachments_status,
        "total_required": len([a for a in attachments_status if a["required"]]),
        "total_uploaded": len([a for a in attachments_status if a["uploaded"]]),
        "complete": all(a["uploaded"] for a in attachments_status if a["required"])
    }

@api_router.post("/contracts/{contract_id}/attachments/{attachment_key}")
async def upload_contract_attachment(
    contract_id: str,
    attachment_key: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a specific attachment for a contract (doc_veiculo, cnh_motorista, etc.)"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    # Validate attachment key
    template_type = contract.get("template_type")
    valid_keys = [a["key"] for a in CONTRACT_REQUIRED_ATTACHMENTS.get(template_type, [])]
    if attachment_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Tipo de anexo inválido. Válidos: {', '.join(valid_keys)}")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB)")
    
    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, '.bin')
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    # Save attachment metadata
    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "entity_type": "contract_attachment",
        "entity_id": contract_id,
        "attachment_key": attachment_key,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    
    # Update contract attachments dict
    current_attachments = contract.get("attachments") or {}
    current_attachments[attachment_key] = file_id
    
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {"attachments": current_attachments}}
    )
    
    # Check if this is payment receipt - update expense status
    if attachment_key == "comprovante_pagamento":
        # Find related expenses and mark as paid
        await db.expenses.update_many(
            {"contract_id": contract_id, "payment_status": "pendente"},
            {"$set": {"payment_status": "pago", "attachment_id": file_id}}
        )
    
    # Get attachment label
    attachment_label = next(
        (a["label"] for a in CONTRACT_REQUIRED_ATTACHMENTS.get(template_type, []) if a["key"] == attachment_key),
        attachment_key
    )
    
    return {
        "message": f"{attachment_label} anexado com sucesso",
        "attachment_id": file_id,
        "attachment_key": attachment_key
    }

@api_router.get("/attachments/{attachment_id}")
async def get_attachment(attachment_id: str, current_user: dict = Depends(get_current_user)):
    """Get attachment metadata"""
    attachment = await db.attachments.find_one(
        {"id": attachment_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return attachment

@api_router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, current_user: dict = Depends(get_current_user)):
    """Download attachment file"""
    attachment = await db.attachments.find_one(
        {"id": attachment_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    file_path = UPLOAD_DIR / attachment["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor")
    
    return StreamingResponse(
        open(file_path, 'rb'),
        media_type=attachment.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename={attachment['original_name']}"}
    )

@api_router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str, current_user: dict = Depends(get_current_user)):
    """Delete attachment"""
    attachment = await db.attachments.find_one(
        {"id": attachment_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Delete file
    file_path = UPLOAD_DIR / attachment["filename"]
    if file_path.exists():
        file_path.unlink()
    
    # Delete from DB
    await db.attachments.delete_one({"id": attachment_id})
    
    return {"message": "Arquivo excluído"}

# ============== VALIDATION ROUTES ==============
@api_router.post("/validate/cpf")
async def validate_cpf_endpoint(cpf: str):
    """Validate CPF"""
    is_valid = validate_cpf(cpf)
    return {
        "cpf": cpf,
        "valid": is_valid,
        "formatted": format_cpf(cpf) if is_valid else None
    }

@api_router.post("/validate/cnpj")
async def validate_cnpj_endpoint(cnpj: str):
    """Validate CNPJ"""
    is_valid = validate_cnpj(cnpj)
    return {
        "cnpj": cnpj,
        "valid": is_valid,
        "formatted": format_cnpj(cnpj) if is_valid else None
    }

# ============== PDF GENERATION ROUTES ==============
@api_router.get("/reports/pdf")
async def generate_pdf_report(current_user: dict = Depends(get_current_user)):
    """Generate PDF report"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER, fontSize=14, spaceAfter=20))
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=18, spaceAfter=30, fontName='Helvetica-Bold'))
    
    elements = []
    
    # Title
    elements.append(Paragraph("PRESTAÇÃO DE CONTAS ELEITORAL", styles['Title2']))
    elements.append(Spacer(1, 20))
    
    # Campaign Info
    if campaign:
        info_text = f"""
        <b>Candidato:</b> {campaign.get('candidate_name', '')}<br/>
        <b>Partido:</b> {campaign.get('party', '')} - {campaign.get('position', '')}<br/>
        <b>Cidade/UF:</b> {campaign.get('city', '')}/{campaign.get('state', '')}<br/>
        <b>Ano:</b> {campaign.get('election_year', '')}<br/>
        <b>CNPJ:</b> {campaign.get('cnpj', 'Não informado')}
        """
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 30))
    
    # Summary
    total_revenues = sum(r.get("amount", 0) for r in revenues)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    balance = total_revenues - total_expenses
    
    summary_data = [
        ["RESUMO FINANCEIRO", ""],
        ["Total de Receitas", f"R$ {total_revenues:,.2f}"],
        ["Total de Despesas", f"R$ {total_expenses:,.2f}"],
        ["Saldo", f"R$ {balance:,.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[10*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Revenues table
    if revenues:
        elements.append(Paragraph("<b>RECEITAS</b>", styles['Heading2']))
        revenue_data = [["Data", "Descrição", "Categoria", "Valor"]]
        for r in revenues[:50]:  # Limit to 50 items
            revenue_data.append([
                r.get("date", "")[:10],
                r.get("description", "")[:40],
                r.get("category", ""),
                f"R$ {r.get('amount', 0):,.2f}"
            ])
        
        revenue_table = Table(revenue_data, colWidths=[2.5*cm, 8*cm, 3*cm, 3*cm])
        revenue_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(revenue_table)
        elements.append(Spacer(1, 20))
    
    # Expenses table
    if expenses:
        elements.append(Paragraph("<b>DESPESAS</b>", styles['Heading2']))
        expense_data = [["Data", "Descrição", "Categoria", "Valor"]]
        for e in expenses[:50]:
            expense_data.append([
                e.get("date", "")[:10],
                e.get("description", "")[:40],
                e.get("category", ""),
                f"R$ {e.get('amount', 0):,.2f}"
            ])
        
        expense_table = Table(expense_data, colWidths=[2.5*cm, 8*cm, 3*cm, 3*cm])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(expense_table)
    
    # Footer
    elements.append(Spacer(1, 40))
    elements.append(Paragraph(
        f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        styles['Normal']
    ))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"prestacao_contas_{campaign.get('candidate_name', 'campanha').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api_router.get("/contracts/{contract_id}/pdf")
async def generate_contract_pdf(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF of contract"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=11, leading=16))
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER, fontSize=12))
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=14, spaceAfter=20, fontName='Helvetica-Bold'))
    
    elements = []
    
    # Title
    elements.append(Paragraph(contract.get("title", "CONTRATO"), styles['Title2']))
    elements.append(Spacer(1, 20))
    
    # Contract HTML content converted to paragraphs
    contract_html = contract.get("contract_html", "")
    if contract_html:
        # Simple HTML to text conversion for PDF
        import re
        text = re.sub(r'<br\s*/?>', '\n', contract_html)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        for para in text.split('\n\n'):
            if para.strip():
                elements.append(Paragraph(para.strip(), styles['Justify']))
                elements.append(Spacer(1, 10))
    
    # Signature section
    elements.append(Spacer(1, 30))
    
    # Add signature images if available
    if contract.get("locador_selfie"):
        elements.append(Paragraph("<b>Assinatura do Locador (com validação facial):</b>", styles['Normal']))
        elements.append(Paragraph(f"Assinado em: {contract.get('locador_assinatura_data', '')}", styles['Normal']))
        elements.append(Paragraph(f"Hash: {contract.get('locador_assinatura_hash', '')[:20]}...", styles['Normal']))
        elements.append(Spacer(1, 10))
    
    if contract.get("locatario_selfie"):
        elements.append(Paragraph("<b>Assinatura do Locatário (com validação facial):</b>", styles['Normal']))
        elements.append(Paragraph(f"Assinado em: {contract.get('locatario_assinatura_data', '')}", styles['Normal']))
        elements.append(Paragraph(f"Hash: {contract.get('locatario_assinatura_hash', '')[:20]}...", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"contrato_{contract_id[:8]}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api_router.get("/contracts/{contract_id}/download-signed-pdf")
async def download_signed_contract_pdf(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Download the PDF of a signed contract"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    # Check if contract has a stored PDF
    pdf_id = contract.get("pdf_path")
    if not pdf_id:
        # Check if contract is fully signed
        if not (contract.get("locatario_assinatura_hash") and contract.get("locador_assinatura_hash")):
            raise HTTPException(status_code=400, detail="Contrato não está completamente assinado")
        
        # Generate PDF now
        campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
        pdf_id = await generate_and_store_contract_pdf(contract_id, contract, campaign)
        if pdf_id:
            await db.contracts.update_one(
                {"id": contract_id},
                {"$set": {"pdf_path": pdf_id, "pdf_generated_at": datetime.now(timezone.utc).isoformat()}}
            )
    
    # Get PDF from database
    pdf_doc = await db.contract_pdfs.find_one({"id": pdf_id})
    if not pdf_doc:
        raise HTTPException(status_code=404, detail="PDF não encontrado")
    
    buffer = BytesIO(pdf_doc["data"])
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pdf_doc.get('filename', 'contrato.pdf')}"}
    )

# ============== EMAIL ROUTES ==============
async def send_email_async(to_email: str, subject: str, html_content: str):
    """Send email using Resend"""
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        logging.warning("Email service not configured")
        return False
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

@api_router.post("/email/send-signature-request")
async def send_signature_email(
    contract_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Send signature request email"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    locador_email = contract.get("locador_email")
    if not locador_email:
        raise HTTPException(status_code=400, detail="Email do locador não informado")
    
    # Generate signature token
    token = generate_signature_token(contract_id, locador_email, "locador")
    signature_link = f"{APP_URL}/assinar/{token}"
    
    # Update contract
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {
            "signature_request_token": token,
            "status": "aguardando_assinatura"
        }}
    )
    
    # Email content
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Solicitação de Assinatura de Contrato</h2>
        <p>Olá <strong>{contract.get('locador_nome', 'Prezado(a)')}</strong>,</p>
        <p>Você recebeu uma solicitação para assinar o seguinte contrato:</p>
        <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Título:</strong> {contract.get('title', '')}</p>
            <p><strong>Valor:</strong> R$ {contract.get('value', 0):,.2f}</p>
        </div>
        <p>Para assinar o contrato, clique no botão abaixo:</p>
        <a href="{signature_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin: 20px 0;">
            Assinar Contrato
        </a>
        <p style="color: #666; font-size: 12px;">Este link é válido por 7 dias.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #999; font-size: 11px;">Este é um email automático do Eleitora 360.</p>
    </div>
    """
    
    # Send email in background
    background_tasks.add_task(
        send_email_async,
        locador_email,
        "Solicitação de Assinatura de Contrato - Eleitora 360",
        html_content
    )
    
    return {
        "message": "Email de solicitação enviado",
        "signature_link": signature_link,
        "email_sent_to": locador_email
    }

# ============== FACIAL SIGNATURE ROUTES ==============
class FacialSignature(BaseModel):
    signature_hash: str
    selfie_base64: str  # Base64 encoded image from webcam
    signer_name: str

@api_router.post("/contracts/{contract_id}/sign-with-facial")
async def sign_contract_with_facial(
    contract_id: str,
    data: FacialSignature,
    party: str = Query(..., description="locador or locatario"),
    token: Optional[str] = None,
    current_user: Optional[dict] = None
):
    """Sign contract with facial validation (selfie)"""
    
    # Validate request based on party
    if party == "locador" and token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload["contract_id"] != contract_id:
                raise HTTPException(status_code=400, detail="Token inválido para este contrato")
            contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Token expirado")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Token inválido")
    elif party == "locatario" and current_user:
        contract = await db.contracts.find_one(
            {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
            {"_id": 0}
        )
    else:
        raise HTTPException(status_code=400, detail="Autenticação necessária")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    
    # Validate selfie (must be base64 image)
    if not data.selfie_base64 or len(data.selfie_base64) < 1000:
        raise HTTPException(status_code=400, detail="Selfie inválida")
    
    # Generate unique signature hash with selfie
    now = datetime.now(timezone.utc).isoformat()
    signature_content = f"{contract_id}-{party}-{data.signer_name}-{now}-{data.selfie_base64[:100]}"
    full_hash = hashlib.sha256(signature_content.encode()).hexdigest()
    
    # Save selfie to file
    selfie_id = str(uuid.uuid4())
    try:
        # Extract base64 data (remove data:image/... prefix if present)
        selfie_data = data.selfie_base64
        if ',' in selfie_data:
            selfie_data = selfie_data.split(',')[1]
        
        selfie_bytes = base64.b64decode(selfie_data)
        selfie_path = UPLOAD_DIR / f"selfie_{selfie_id}.jpg"
        with open(selfie_path, 'wb') as f:
            f.write(selfie_bytes)
    except Exception as e:
        logging.error(f"Failed to save selfie: {e}")
        raise HTTPException(status_code=400, detail="Erro ao processar selfie")
    
    # Update contract
    update_data = {
        f"{party}_assinatura_hash": full_hash,
        f"{party}_assinatura_data": now,
        f"{party}_selfie": selfie_id,
        f"{party}_nome_assinatura": data.signer_name
    }
    
    # Check if both parties signed
    other_party = "locatario" if party == "locador" else "locador"
    if contract.get(f"{other_party}_assinatura_hash"):
        update_data["status"] = "ativo"
    else:
        update_data["status"] = f"assinado_{party}"
    
    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
    
    # Regenerate HTML with signature info
    campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
    updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    html = generate_contract_html(updated_contract, campaign)
    await db.contracts.update_one({"id": contract_id}, {"$set": {"contract_html": html}})
    
    return {
        "message": f"Contrato assinado pelo {party} com validação facial",
        "status": update_data["status"],
        "signature_hash": full_hash[:20] + "...",
        "selfie_id": selfie_id
    }

# ============== SPCE EXPORT - DESPESAS ==============
@api_router.get("/export/spce-despesas")
async def export_spce_despesas(current_user: dict = Depends(get_current_user)):
    """Export expenses in SPCE format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    if not campaign.get("cnpj"):
        raise HTTPException(status_code=400, detail="CNPJ da campanha não configurado")
    
    # Generate CSV format for SPCE import
    lines = ["DATA;DESCRICAO;VALOR;CATEGORIA;FORNECEDOR;CPF_CNPJ;NOTA_FISCAL"]
    
    for exp in expenses:
        line = ";".join([
            exp.get("date", ""),
            f'"{exp.get("description", "")}"',
            str(exp.get("amount", 0)).replace(".", ","),
            exp.get("category", ""),
            f'"{exp.get("supplier_name", "")}"',
            exp.get("supplier_cpf_cnpj", ""),
            exp.get("invoice_number", "")
        ])
        lines.append(line)
    
    now = datetime.now(timezone.utc)
    filename = f"despesas_spce_{now.strftime('%Y%m%d')}.csv"
    
    return {
        "filename": filename,
        "content": "\n".join(lines),
        "total_despesas": len(expenses),
        "format": "SPCE-DESPESAS-CSV"
    }

# ============== SPCE LAYOUT - DESPAGTOS (Despesas de Gastos) ==============
# Layout oficial conforme Resolução TSE 23.607/2019
SPCE_DESPESA_CATEGORIAS = {
    "propaganda": {"codigo": "101", "descricao": "Despesas com Propaganda"},
    "pessoal": {"codigo": "102", "descricao": "Despesas com Pessoal"},
    "transporte": {"codigo": "103", "descricao": "Despesas de Transporte"},
    "material": {"codigo": "104", "descricao": "Despesas com Material de Expediente"},
    "alimentacao": {"codigo": "105", "descricao": "Despesas com Alimentação"},
    "combustivel": {"codigo": "106", "descricao": "Despesas com Combustível e Lubrificantes"},
    "locacao_veiculo": {"codigo": "107", "descricao": "Locação/Cessão de Veículos"},
    "locacao_imovel": {"codigo": "108", "descricao": "Locação/Cessão de Imóveis"},
    "eventos": {"codigo": "109", "descricao": "Despesas com Eventos"},
    "servicos_terceiros": {"codigo": "110", "descricao": "Serviços Prestados por Terceiros"},
    "agua_luz_telefone": {"codigo": "111", "descricao": "Água, Luz, Telefone e Internet"},
    "taxa_bancaria": {"codigo": "112", "descricao": "Taxas e Tarifas Bancárias"},
    "producao_audiovisual": {"codigo": "113", "descricao": "Produção de Programas de Rádio/TV/Vídeo"},
    "impulsionamento": {"codigo": "114", "descricao": "Impulsionamento de Conteúdos"},
    "outros": {"codigo": "199", "descricao": "Outras Despesas"}
}

@api_router.get("/export/spce-despagtos")
async def export_spce_despagtos(current_user: dict = Depends(get_current_user)):
    """Export expenses in SPCE DESPAGTOS layout format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    cnpj = (campaign.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha inválido ou não configurado")
    
    # Generate DESPAGTOS format
    # Header: versao|tipo_registro|cnpj_campanha|uf|ano_eleicao
    lines = []
    header = f"100|H|{cnpj}|{campaign.get('state', '')}|{campaign.get('election_year', 2024)}"
    lines.append(header)
    
    # Detail records: versao|tipo|sequencia|data|cpf_cnpj_fornecedor|nome_fornecedor|valor|categoria|descricao|doc_fiscal
    for i, exp in enumerate(expenses, 1):
        supplier_doc = (exp.get("supplier_cpf_cnpj") or "").replace(".", "").replace("-", "").replace("/", "")
        date_fmt = exp.get("date", "").replace("-", "")  # YYYYMMDD to DDMMYYYY
        if len(date_fmt) == 8:
            date_fmt = date_fmt[6:8] + date_fmt[4:6] + date_fmt[0:4]
        
        # Get category code
        cat = exp.get("category", "outros").lower().replace(" ", "_")
        cat_info = SPCE_DESPESA_CATEGORIAS.get(cat, SPCE_DESPESA_CATEGORIAS["outros"])
        
        # Format amount with 2 decimals, comma separator
        amount = f"{exp.get('amount', 0):.2f}".replace(".", ",")
        
        detail = f"100|D|{i:05d}|{date_fmt}|{supplier_doc}|{exp.get('supplier_name', '')}|{amount}|{cat_info['codigo']}|{exp.get('description', '')}|{exp.get('invoice_number', '')}"
        lines.append(detail)
    
    # Trailer: versao|tipo|total_registros|valor_total
    total = sum(e.get("amount", 0) for e in expenses)
    trailer = f"100|T|{len(expenses):05d}|{total:.2f}".replace(".", ",")
    lines.append(trailer)
    
    now = datetime.now(timezone.utc)
    filename = f"DESPAGTOS_{cnpj}_{now.strftime('%Y%m%d%H%M%S')}.txt"
    
    return {
        "filename": filename,
        "content": "\n".join(lines),
        "total_registros": len(expenses),
        "valor_total": total,
        "valor_total_formatado": f"R$ {total:,.2f}",
        "format": "SPCE-DESPAGTOS",
        "categorias_utilizadas": list(set(
            SPCE_DESPESA_CATEGORIAS.get(e.get("category", "outros").lower().replace(" ", "_"), SPCE_DESPESA_CATEGORIAS["outros"])["descricao"]
            for e in expenses
        ))
    }

# ============== SPCE LAYOUT - CONTRATOS ==============
SPCE_CONTRATO_TIPOS = {
    "veiculo_com_motorista": {"codigo": "01", "descricao": "Locação de Veículo com Motorista"},
    "veiculo_sem_motorista": {"codigo": "02", "descricao": "Locação de Veículo sem Motorista"},
    "imovel_comite": {"codigo": "03", "descricao": "Locação de Imóvel para Comitê"},
    "imovel_evento": {"codigo": "04", "descricao": "Locação de Imóvel para Evento"},
    "servico_grafico": {"codigo": "05", "descricao": "Serviços Gráficos"},
    "servico_publicidade": {"codigo": "06", "descricao": "Serviços de Publicidade"},
    "servico_pesquisa": {"codigo": "07", "descricao": "Serviços de Pesquisa"},
    "servico_juridico": {"codigo": "08", "descricao": "Serviços Jurídicos"},
    "servico_contabil": {"codigo": "09", "descricao": "Serviços Contábeis"},
    "servico_ti": {"codigo": "10", "descricao": "Serviços de TI"},
    "producao_audiovisual": {"codigo": "11", "descricao": "Produção Audiovisual"},
    "impulsionamento": {"codigo": "12", "descricao": "Impulsionamento de Conteúdos"},
    "outros": {"codigo": "99", "descricao": "Outros Contratos"}
}

@api_router.get("/export/spce-contratos")
async def export_spce_contratos(current_user: dict = Depends(get_current_user)):
    """Export contracts in SPCE format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    cnpj = (campaign.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha inválido ou não configurado")
    
    # Generate CONTRATOS format
    lines = []
    
    # Header
    header = f"100|H|{cnpj}|{campaign.get('state', '')}|{campaign.get('election_year', 2024)}|CONTRATOS"
    lines.append(header)
    
    # Detail records
    for i, contract in enumerate(contracts, 1):
        locador_doc = (contract.get("locador_cpf") or contract.get("contractor_cpf_cnpj") or "").replace(".", "").replace("-", "").replace("/", "")
        
        # Format dates
        start_date = contract.get("start_date", "").replace("-", "")
        end_date = contract.get("end_date", "").replace("-", "")
        if len(start_date) == 8:
            start_date = start_date[6:8] + start_date[4:6] + start_date[0:4]
        if len(end_date) == 8:
            end_date = end_date[6:8] + end_date[4:6] + end_date[0:4]
        
        # Get contract type
        template = contract.get("template_type", "outros")
        tipo_info = SPCE_CONTRATO_TIPOS.get(template, SPCE_CONTRATO_TIPOS["outros"])
        
        # Format amount
        amount = f"{contract.get('value', 0):.2f}".replace(".", ",")
        
        # Status: A=Ativo, E=Encerrado, C=Cancelado, R=Rascunho
        status_map = {"ativo": "A", "encerrado": "E", "cancelado": "C", "rascunho": "R"}
        status = status_map.get(contract.get("status", "rascunho"), "R")
        
        # Signature status
        assinado_locador = "S" if contract.get("locador_assinatura_hash") else "N"
        assinado_locatario = "S" if contract.get("locatario_assinatura_hash") else "N"
        
        detail = "|".join([
            "100",
            "C",
            f"{i:05d}",
            tipo_info["codigo"],
            start_date,
            end_date,
            locador_doc,
            contract.get("locador_nome", contract.get("contractor_name", "")),
            amount,
            status,
            assinado_locador,
            assinado_locatario,
            contract.get("title", ""),
            str(contract.get("num_parcelas", 1))
        ])
        lines.append(detail)
    
    # Trailer
    total_valor = sum(c.get("value", 0) for c in contracts)
    contratos_ativos = len([c for c in contracts if c.get("status") == "ativo"])
    trailer = f"100|T|{len(contracts):05d}|{total_valor:.2f}|{contratos_ativos:05d}".replace(".", ",")
    lines.append(trailer)
    
    now = datetime.now(timezone.utc)
    filename = f"CONTRATOS_{cnpj}_{now.strftime('%Y%m%d%H%M%S')}.txt"
    
    return {
        "filename": filename,
        "content": "\n".join(lines),
        "total_contratos": len(contracts),
        "contratos_ativos": contratos_ativos,
        "valor_total": total_valor,
        "valor_total_formatado": f"R$ {total_valor:,.2f}",
        "format": "SPCE-CONTRATOS",
        "tipos_utilizados": list(set(
            SPCE_CONTRATO_TIPOS.get(c.get("template_type", "outros"), SPCE_CONTRATO_TIPOS["outros"])["descricao"]
            for c in contracts
        ))
    }

@api_router.get("/export/spce-despesas-pdf")
async def export_spce_despesas_pdf(current_user: dict = Depends(get_current_user)):
    """Export expenses as PDF in SPCE-compliant format"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=14, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Subtitle', alignment=TA_CENTER, fontSize=10, textColor=colors.grey))
    
    elements = []
    
    # Header
    elements.append(Paragraph("RELATÓRIO DE DESPESAS ELEITORAIS", styles['Title2']))
    elements.append(Paragraph(f"Campanha: {campaign.get('candidate_name', '')} - {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"CNPJ: {campaign.get('cnpj', 'Não informado')}", styles['Normal']))
    elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Subtitle']))
    elements.append(Spacer(1, 20))
    
    # Summary
    total = sum(e.get("amount", 0) for e in expenses)
    pagas = sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pago")
    pendentes = sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente")
    
    summary_data = [
        ["RESUMO FINANCEIRO", ""],
        ["Total de Despesas:", f"R$ {total:,.2f}"],
        ["Despesas Pagas:", f"R$ {pagas:,.2f}"],
        ["Despesas Pendentes:", f"R$ {pendentes:,.2f}"],
        ["Quantidade de Registros:", str(len(expenses))]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Expenses Table
    elements.append(Paragraph("<b>DETALHAMENTO DAS DESPESAS</b>", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    if expenses:
        # Sort by date
        expenses_sorted = sorted(expenses, key=lambda x: x.get("date", ""))
        
        exp_data = [["Data", "Descrição", "Fornecedor", "Valor", "Status"]]
        for exp in expenses_sorted:
            date_str = exp.get("date", "")
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_str = date_obj.strftime("%d/%m/%Y")
                except:
                    pass
            
            status = "Pago" if exp.get("payment_status") == "pago" else "Pendente"
            exp_data.append([
                date_str,
                exp.get("description", "")[:40],
                exp.get("supplier_name", "")[:25],
                f"R$ {exp.get('amount', 0):,.2f}",
                status
            ])
        
        exp_table = Table(exp_data, colWidths=[60, 150, 120, 80, 50])
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        elements.append(exp_table)
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 80, styles['Normal']))
    elements.append(Paragraph("<i>Documento gerado pelo sistema Eleitora 360 - Formato compatível SPCE/TSE</i>", styles['Subtitle']))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"despesas_spce_{campaign.get('cnpj', 'sem_cnpj').replace('.', '').replace('/', '').replace('-', '')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api_router.get("/export/spce-contratos-pdf")
async def export_spce_contratos_pdf(current_user: dict = Depends(get_current_user)):
    """Export contracts as PDF in SPCE-compliant format"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=14, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Subtitle', alignment=TA_CENTER, fontSize=10, textColor=colors.grey))
    
    elements = []
    
    # Header
    elements.append(Paragraph("RELATÓRIO DE CONTRATOS ELEITORAIS", styles['Title2']))
    elements.append(Paragraph(f"Campanha: {campaign.get('candidate_name', '')} - {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"CNPJ: {campaign.get('cnpj', 'Não informado')}", styles['Normal']))
    elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Subtitle']))
    elements.append(Spacer(1, 20))
    
    # Summary
    total = sum(c.get("value", 0) for c in contracts)
    ativos = len([c for c in contracts if c.get("status") == "ativo"])
    assinados = len([c for c in contracts if c.get("locador_assinatura_hash") and c.get("locatario_assinatura_hash")])
    
    summary_data = [
        ["RESUMO DE CONTRATOS", ""],
        ["Valor Total:", f"R$ {total:,.2f}"],
        ["Contratos Ativos:", str(ativos)],
        ["Contratos Assinados:", str(assinados)],
        ["Total de Contratos:", str(len(contracts))]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Contracts Table
    elements.append(Paragraph("<b>DETALHAMENTO DOS CONTRATOS</b>", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    if contracts:
        contract_data = [["Título", "Contratado", "Período", "Valor", "Status"]]
        for c in contracts:
            start = c.get("start_date", "")
            end = c.get("end_date", "")
            try:
                if start:
                    start = datetime.strptime(start, "%Y-%m-%d").strftime("%d/%m/%y")
                if end:
                    end = datetime.strptime(end, "%Y-%m-%d").strftime("%d/%m/%y")
            except:
                pass
            
            status_labels = {"ativo": "Ativo", "rascunho": "Rascunho", "encerrado": "Encerrado", "cancelado": "Cancelado"}
            status = status_labels.get(c.get("status", "rascunho"), c.get("status", ""))
            
            contract_data.append([
                c.get("title", "")[:35],
                c.get("locador_nome", c.get("contractor_name", ""))[:25],
                f"{start} a {end}",
                f"R$ {c.get('value', 0):,.2f}",
                status
            ])
        
        contract_table = Table(contract_data, colWidths=[140, 120, 80, 70, 50])
        contract_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        elements.append(contract_table)
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 80, styles['Normal']))
    elements.append(Paragraph("<i>Documento gerado pelo sistema Eleitora 360 - Formato compatível SPCE/TSE</i>", styles['Subtitle']))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"contratos_spce_{campaign.get('cnpj', 'sem_cnpj').replace('.', '').replace('/', '').replace('-', '')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api_router.get("/export/spce-categorias")
async def get_spce_categorias():
    """Get available SPCE categories for expenses and contracts"""
    return {
        "despesas": SPCE_DESPESA_CATEGORIAS,
        "contratos": SPCE_CONTRATO_TIPOS,
        "nota": "Categorias conforme Resolução TSE 23.607/2019"
    }

# ============== BANK STATEMENT IMPORT ==============
class BankStatementEntry(BaseModel):
    date: str
    description: str
    amount: float
    type: str  # credit or debit
    matched: bool = False
    matched_to: Optional[str] = None

@api_router.post("/import/bank-statement")
async def import_bank_statement(
    file: UploadFile = File(...),
    account_type: str = Query(..., description="doacao, fundo_partidario, or fefec"),
    current_user: dict = Depends(get_current_user)
):
    """Import bank statement (CSV/OFX)"""
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    contents = await file.read()
    content_str = contents.decode('utf-8', errors='ignore')
    
    entries = []
    
    # Parse CSV format
    if file.filename.lower().endswith('.csv'):
        lines = content_str.strip().split('\n')
        for line in lines[1:]:  # Skip header
            parts = line.split(';')
            if len(parts) >= 3:
                try:
                    date = parts[0].strip()
                    description = parts[1].strip().strip('"')
                    amount_str = parts[2].strip().replace(',', '.').replace('"', '')
                    amount = float(amount_str)
                    
                    entries.append({
                        "date": date,
                        "description": description,
                        "amount": abs(amount),
                        "type": "credit" if amount > 0 else "debit"
                    })
                except:
                    continue
    
    # Save import record
    import_id = str(uuid.uuid4())
    import_doc = {
        "id": import_id,
        "campaign_id": current_user["campaign_id"],
        "account_type": account_type,
        "filename": file.filename,
        "entries": entries,
        "total_entries": len(entries),
        "imported_at": datetime.now(timezone.utc).isoformat()
    }
    await db.bank_imports.insert_one(import_doc)
    
    return {
        "import_id": import_id,
        "total_entries": len(entries),
        "entries": entries[:20],  # Return first 20 for preview
        "message": f"Importadas {len(entries)} transações"
    }

@api_router.post("/reconcile/auto")
async def auto_reconcile(
    import_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Automatically match bank entries with revenues/expenses"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Get import
    bank_import = await db.bank_imports.find_one(
        {"id": import_id, "campaign_id": campaign_id},
        {"_id": 0}
    )
    if not bank_import:
        raise HTTPException(status_code=404, detail="Importação não encontrada")
    
    # Get revenues and expenses
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    matched_count = 0
    entries = bank_import.get("entries", [])
    
    for entry in entries:
        if entry.get("matched"):
            continue
        
        # Try to match by amount and date
        if entry["type"] == "credit":
            for rev in revenues:
                if abs(rev.get("amount", 0) - entry["amount"]) < 0.01:
                    if rev.get("date", "")[:10] == entry["date"][:10]:
                        entry["matched"] = True
                        entry["matched_to"] = f"revenue:{rev['id']}"
                        matched_count += 1
                        break
        else:
            for exp in expenses:
                if abs(exp.get("amount", 0) - entry["amount"]) < 0.01:
                    if exp.get("date", "")[:10] == entry["date"][:10]:
                        entry["matched"] = True
                        entry["matched_to"] = f"expense:{exp['id']}"
                        matched_count += 1
                        break
    
    # Update import
    await db.bank_imports.update_one(
        {"id": import_id},
        {"$set": {"entries": entries, "reconciled_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "total_entries": len(entries),
        "matched": matched_count,
        "unmatched": len(entries) - matched_count,
        "entries": entries
    }

# ============== FILTERED QUERIES ==============
@api_router.get("/revenues/filtered")
async def list_revenues_filtered(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List revenues with date and category filters"""
    if not current_user.get("campaign_id"):
        return []
    
    query = {"campaign_id": current_user["campaign_id"]}
    
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        if "date" in query:
            query["date"]["$lte"] = end_date
        else:
            query["date"] = {"$lte": end_date}
    if category:
        query["category"] = category
    
    revenues = await db.revenues.find(query, {"_id": 0}).to_list(1000)
    return revenues

@api_router.get("/expenses/filtered")
async def list_expenses_filtered(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List expenses with date and category filters"""
    if not current_user.get("campaign_id"):
        return []
    
    query = {"campaign_id": current_user["campaign_id"]}
    
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        if "date" in query:
            query["date"]["$lte"] = end_date
        else:
            query["date"] = {"$lte": end_date}
    if category:
        query["category"] = category
    
    expenses = await db.expenses.find(query, {"_id": 0}).to_list(1000)
    return expenses

# ============== AI ASSISTANT ROUTES ==============
from ai_assistant import assistant, get_tse_rules_summary

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    alerts: Optional[List[str]] = None

@api_router.post("/ai/chat")
async def ai_chat(
    data: ChatMessage,
    current_user: dict = Depends(get_current_user)
):
    """Chat with AI Electoral Assistant"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Get campaign data
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
    
    # Calculate totals
    total_revenues = sum(r.get("amount", 0) for r in revenues)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    pending_expenses = sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente")
    pending_count = len([e for e in expenses if e.get("payment_status") == "pendente"])
    
    # Count contracts with missing docs
    contracts_missing_docs = 0
    for c in contracts:
        if c.get("template_type") and not c.get("attachments"):
            contracts_missing_docs += 1
    
    # Build campaign context
    campaign_context = {
        "campaign_id": campaign_id,
        "candidate_name": campaign.get("candidate_name", ""),
        "party": campaign.get("party", ""),
        "position": campaign.get("position", ""),
        "city": campaign.get("city", ""),
        "state": campaign.get("state", ""),
        "election_year": campaign.get("election_year", 2024),
        "cnpj": campaign.get("cnpj", ""),
        "total_revenues": total_revenues,
        "total_expenses": total_expenses,
        "balance": total_revenues - total_expenses,
        "limite_gastos": campaign.get("limite_gastos", 0),
        "pending_expenses": pending_expenses,
        "pending_count": pending_count,
        "contracts_missing_docs": contracts_missing_docs,
        "total_contracts": len(contracts)
    }
    
    # Get chat history from database
    session_id = data.session_id or f"chat_{campaign_id}_{current_user['id']}"
    
    chat_history_doc = await db.chat_history.find_one({"session_id": session_id})
    chat_history = chat_history_doc.get("messages", []) if chat_history_doc else []
    
    try:
        # Get AI response
        response = await assistant.chat(
            session_id=session_id,
            message=data.message,
            campaign_context=campaign_context,
            chat_history=chat_history
        )
        
        # Save to chat history
        new_messages = [
            {"role": "user", "content": data.message, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"role": "assistant", "content": response, "timestamp": datetime.now(timezone.utc).isoformat()}
        ]
        
        await db.chat_history.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": {"$each": new_messages}},
                "$set": {"campaign_id": campaign_id, "user_id": current_user["id"], "updated_at": datetime.now(timezone.utc).isoformat()}
            },
            upsert=True
        )
        
        # Generate alerts
        alerts = []
        if campaign_context.get("limite_gastos", 0) > 0:
            percentage = (total_expenses / campaign_context["limite_gastos"]) * 100
            if percentage >= 90:
                alerts.append(f"⚠️ Gastos em {percentage:.1f}% do limite!")
        if pending_count > 0:
            alerts.append(f"📋 {pending_count} despesa(s) pendente(s)")
        if contracts_missing_docs > 0:
            alerts.append(f"📎 {contracts_missing_docs} contrato(s) sem documentação completa")
        
        return {
            "response": response,
            "session_id": session_id,
            "alerts": alerts if alerts else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")

@api_router.get("/ai/chat/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get chat history for current user"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return {"messages": []}
    
    query_session = session_id or f"chat_{campaign_id}_{current_user['id']}"
    
    chat_doc = await db.chat_history.find_one({"session_id": query_session})
    if not chat_doc:
        return {"messages": [], "session_id": query_session}
    
    messages = chat_doc.get("messages", [])[-limit:]
    
    return {
        "messages": messages,
        "session_id": query_session,
        "total": len(chat_doc.get("messages", []))
    }

@api_router.delete("/ai/chat/history")
async def clear_chat_history(
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Clear chat history"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    query_session = session_id or f"chat_{campaign_id}_{current_user['id']}"
    
    await db.chat_history.delete_one({"session_id": query_session})
    
    return {"message": "Histórico limpo com sucesso"}

@api_router.post("/ai/analyze-expenses")
async def ai_analyze_expenses(current_user: dict = Depends(get_current_user)):
    """Get AI analysis of campaign expenses"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    if not expenses:
        return {"analysis": "Não há despesas registradas para analisar."}
    
    campaign_context = {
        "campaign_id": campaign_id,
        "candidate_name": campaign.get("candidate_name", ""),
        "limite_gastos": campaign.get("limite_gastos", 0)
    }
    
    try:
        analysis = await assistant.analyze_expenses(expenses, campaign_context)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {str(e)}")

@api_router.post("/ai/check-compliance")
async def ai_check_compliance(current_user: dict = Depends(get_current_user)):
    """Check campaign compliance with electoral rules"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    campaign_context = {
        "campaign_id": campaign_id,
        "candidate_name": campaign.get("candidate_name", ""),
        "party": campaign.get("party", ""),
        "total_revenues": sum(r.get("amount", 0) for r in revenues),
        "total_expenses": sum(e.get("amount", 0) for e in expenses),
        "limite_gastos": campaign.get("limite_gastos", 0)
    }
    
    try:
        compliance = await assistant.check_compliance(campaign_context, contracts)
        return {"compliance_report": compliance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na verificação: {str(e)}")

@api_router.get("/ai/tse-rules")
async def get_tse_rules():
    """Get summary of current TSE electoral rules"""
    rules = await get_tse_rules_summary()
    return {"rules": rules}

# ============== VOICE ASSISTANT ROUTES ==============
from voice_assistant import voice_assistant, RESPONSES

@api_router.post("/voice/transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Transcribe audio to text using Whisper"""
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Read audio file
    contents = await audio.read()
    
    # Check file size (max 25MB)
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 25MB)")
    
    try:
        text = await voice_assistant.transcribe_audio(contents, audio.filename or "audio.webm")
        return {"text": text, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na transcrição: {str(e)}")

@api_router.post("/voice/speak")
async def voice_speak(
    text: str = Query(..., description="Text to convert to speech"),
    current_user: dict = Depends(get_current_user)
):
    """Convert text to speech using TTS"""
    if not text:
        raise HTTPException(status_code=400, detail="Texto não fornecido")
    
    try:
        audio_base64 = await voice_assistant.generate_speech_base64(text)
        return {
            "audio": audio_base64,
            "format": "mp3",
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na síntese de voz: {str(e)}")

@api_router.post("/voice/command")
async def voice_command(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Process voice command: transcribe, parse, execute, and respond with voice"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Read audio file
    contents = await audio.read()
    
    try:
        # Step 1: Transcribe audio
        transcribed_text = await voice_assistant.transcribe_audio(contents, audio.filename or "audio.webm")
        
        # Step 2: Parse command
        command, params = voice_assistant.parse_command(transcribed_text)
        
        # Step 3: Execute command and generate response
        response_text = ""
        action = None
        action_data = None
        
        if command == "greeting":
            response_text = RESPONSES["greeting"]
        
        elif command == "help":
            response_text = RESPONSES["help"]
        
        elif command == "query_saldo":
            # Get financial data
            revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            total_rev = sum(r.get("amount", 0) for r in revenues)
            total_exp = sum(e.get("amount", 0) for e in expenses)
            balance = total_rev - total_exp
            response_text = f"Seu saldo atual é de {voice_assistant.format_currency(balance)}. Total de receitas: {voice_assistant.format_currency(total_rev)}. Total de despesas: {voice_assistant.format_currency(total_exp)}."
        
        elif command == "query_receitas":
            revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            total = sum(r.get("amount", 0) for r in revenues)
            response_text = f"Você tem {len(revenues)} receitas registradas, totalizando {voice_assistant.format_currency(total)}."
        
        elif command == "query_despesas":
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            total = sum(e.get("amount", 0) for e in expenses)
            pending = sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente")
            response_text = f"Você tem {len(expenses)} despesas registradas, totalizando {voice_assistant.format_currency(total)}. Despesas pendentes: {voice_assistant.format_currency(pending)}."
        
        elif command == "query_resumo":
            campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
            revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
            
            total_rev = sum(r.get("amount", 0) for r in revenues)
            total_exp = sum(e.get("amount", 0) for e in expenses)
            balance = total_rev - total_exp
            
            response_text = f"Resumo da campanha de {campaign.get('candidate_name', 'candidato')}. "
            response_text += f"Receitas: {voice_assistant.format_currency(total_rev)}. "
            response_text += f"Despesas: {voice_assistant.format_currency(total_exp)}. "
            response_text += f"Saldo: {voice_assistant.format_currency(balance)}. "
            response_text += f"Você tem {len(contracts)} contratos registrados."
        
        elif command == "query_contratos":
            contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
            response_text = f"Você tem {len(contracts)} contratos registrados."
            if contracts:
                total_value = sum(c.get("value", 0) for c in contracts)
                response_text += f" Valor total: {voice_assistant.format_currency(total_value)}."
        
        elif command == "query_pendentes":
            contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
            pending_docs = [c for c in contracts if c.get("template_type") and not c.get("attachments")]
            if pending_docs:
                response_text = f"Você tem {len(pending_docs)} contratos com documentos pendentes."
            else:
                response_text = "Todos os seus contratos têm a documentação completa."
        
        elif command == "query_alertas":
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            pending_exp = [e for e in expenses if e.get("payment_status") == "pendente"]
            contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)
            pending_docs = len([c for c in contracts if c.get("template_type") and not c.get("attachments")])
            
            alerts = []
            if pending_exp:
                alerts.append(f"{len(pending_exp)} despesas pendentes de pagamento")
            if pending_docs:
                alerts.append(f"{pending_docs} contratos com documentos faltando")
            
            if alerts:
                response_text = "Alertas: " + ". ".join(alerts) + "."
            else:
                response_text = "Não há alertas no momento. Tudo está em ordem."
        
        elif command == "query_conformidade":
            # Use AI for compliance check
            campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
            revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            
            total_exp = sum(e.get("amount", 0) for e in expenses)
            limite = campaign.get("limite_gastos", 0)
            
            if limite > 0:
                percentage = (total_exp / limite) * 100
                if percentage >= 90:
                    response_text = f"Atenção! Seus gastos estão em {percentage:.1f}% do limite permitido. Cuidado para não exceder."
                elif percentage >= 75:
                    response_text = f"Seus gastos estão em {percentage:.1f}% do limite. Ainda tem margem, mas fique atento."
                else:
                    response_text = f"Seus gastos estão em {percentage:.1f}% do limite. Você está dentro da conformidade."
            else:
                response_text = "O limite de gastos não está configurado. Configure nas configurações para monitorar a conformidade."
        
        elif command == "add_expense":
            amount = params.get("amount", 0)
            category = params.get("category", "outros")
            
            # Create expense
            expense_doc = {
                "id": str(uuid.uuid4()),
                "description": f"Despesa adicionada por comando de voz",
                "amount": amount,
                "category": category,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "payment_status": "pendente",
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.expenses.insert_one(expense_doc)
            
            response_text = f"Despesa de {voice_assistant.format_currency(amount)} adicionada com sucesso na categoria {category}."
            action = "expense_added"
            action_data = {"expense_id": expense_doc["id"], "amount": amount}
        
        elif command == "add_revenue":
            amount = params.get("amount", 0)
            
            # Create revenue
            revenue_doc = {
                "id": str(uuid.uuid4()),
                "description": f"Receita adicionada por comando de voz",
                "amount": amount,
                "category": "recursos_proprios",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.revenues.insert_one(revenue_doc)
            
            response_text = f"Receita de {voice_assistant.format_currency(amount)} adicionada com sucesso."
            action = "revenue_added"
            action_data = {"revenue_id": revenue_doc["id"], "amount": amount}
        
        elif command == "navigate":
            route = params.get("route", "/dashboard")
            response_text = f"Navegando para {route.replace('/', '')}."
            action = "navigate"
            action_data = {"route": route}
        
        elif command == "ai_chat":
            # Send to AI assistant for complex queries
            message = params.get("message", transcribed_text)
            
            # Get campaign context
            campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
            revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
            
            campaign_context = {
                "campaign_id": campaign_id,
                "candidate_name": campaign.get("candidate_name", ""),
                "party": campaign.get("party", ""),
                "total_revenues": sum(r.get("amount", 0) for r in revenues),
                "total_expenses": sum(e.get("amount", 0) for e in expenses),
                "balance": sum(r.get("amount", 0) for r in revenues) - sum(e.get("amount", 0) for e in expenses),
                "limite_gastos": campaign.get("limite_gastos", 0)
            }
            
            # Get AI response
            ai_response = await assistant.chat(
                session_id=f"voice_{campaign_id}",
                message=message,
                campaign_context=campaign_context
            )
            
            # Limit response for TTS
            response_text = ai_response[:1000] if len(ai_response) > 1000 else ai_response
        
        else:
            response_text = RESPONSES["not_understood"]
        
        # Step 4: Generate voice response
        try:
            audio_base64 = await voice_assistant.generate_speech_base64(response_text)
        except:
            audio_base64 = None
        
        return {
            "transcribed_text": transcribed_text,
            "command": command,
            "response_text": response_text,
            "audio_response": audio_base64,
            "action": action,
            "action_data": action_data,
            "success": True
        }
        
    except Exception as e:
        # Generate error response
        error_text = RESPONSES["error"]
        try:
            audio_base64 = await voice_assistant.generate_speech_base64(error_text)
        except:
            audio_base64 = None
        
        return {
            "transcribed_text": "",
            "command": "error",
            "response_text": error_text,
            "audio_response": audio_base64,
            "action": None,
            "action_data": None,
            "success": False,
            "error": str(e)
        }

@api_router.get("/voice/greeting")
async def voice_greeting(current_user: dict = Depends(get_current_user)):
    """Get voice greeting from Eleitora"""
    try:
        audio_base64 = await voice_assistant.generate_speech_base64(RESPONSES["greeting"])
        return {
            "text": RESPONSES["greeting"],
            "audio": audio_base64,
            "format": "mp3"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

# ============== PROFESSIONAL (CONTADOR/ADVOGADO) ROUTES ==============
@api_router.post("/professionals", response_model=ProfessionalResponse)
async def create_professional(data: ProfessionalCreate, current_user: dict = Depends(get_current_user)):
    """Create a new professional (contador or advogado)"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Check if professional with same email already exists
    existing = await db.professionals.find_one({"email": data.email})
    if existing:
        # Add campaign to existing professional's list
        if campaign_id not in (existing.get("campaigns") or []):
            await db.professionals.update_one(
                {"id": existing["id"]},
                {"$push": {"campaigns": campaign_id}}
            )
        existing["campaigns"] = existing.get("campaigns", []) + [campaign_id]
        existing.pop("_id", None)
        existing.pop("password_hash", None)
        return existing
    
    professional_id = str(uuid.uuid4())
    professional_doc = {
        "id": professional_id,
        **data.model_dump(exclude={"password"}),
        "campaigns": [campaign_id],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Hash password if provided
    if data.password and data.has_system_access:
        professional_doc["password_hash"] = hashlib.sha256(data.password.encode()).hexdigest()
    
    await db.professionals.insert_one(professional_doc)
    professional_doc.pop("_id", None)
    professional_doc.pop("password_hash", None)
    return professional_doc

@api_router.get("/professionals", response_model=List[ProfessionalResponse])
async def list_professionals(
    type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List professionals linked to current campaign"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return []
    
    query = {"campaigns": campaign_id}
    if type:
        query["type"] = type
    
    professionals = await db.professionals.find(query, {"_id": 0, "password_hash": 0}).to_list(100)
    return professionals

@api_router.get("/professionals/{professional_id}", response_model=ProfessionalResponse)
async def get_professional(professional_id: str, current_user: dict = Depends(get_current_user)):
    """Get professional by ID"""
    campaign_id = current_user.get("campaign_id")
    professional = await db.professionals.find_one(
        {"id": professional_id, "campaigns": campaign_id},
        {"_id": 0, "password_hash": 0}
    )
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return professional

@api_router.put("/professionals/{professional_id}", response_model=ProfessionalResponse)
async def update_professional(
    professional_id: str,
    data: ProfessionalCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update professional"""
    campaign_id = current_user.get("campaign_id")
    professional = await db.professionals.find_one(
        {"id": professional_id, "campaigns": campaign_id}
    )
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    update_data = data.model_dump(exclude={"password"})
    if data.password and data.has_system_access:
        update_data["password_hash"] = hashlib.sha256(data.password.encode()).hexdigest()
    
    await db.professionals.update_one(
        {"id": professional_id},
        {"$set": update_data}
    )
    
    updated = await db.professionals.find_one({"id": professional_id}, {"_id": 0, "password_hash": 0})
    return updated

@api_router.delete("/professionals/{professional_id}")
async def remove_professional(professional_id: str, current_user: dict = Depends(get_current_user)):
    """Remove professional from campaign (not delete)"""
    campaign_id = current_user.get("campaign_id")
    
    result = await db.professionals.update_one(
        {"id": professional_id},
        {"$pull": {"campaigns": campaign_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    return {"message": "Profissional removido da campanha"}

@api_router.get("/professionals/contador/campaigns")
async def get_contador_campaigns(current_user: dict = Depends(get_current_user)):
    """Get all campaigns a contador has access to (for contador portal)"""
    # This endpoint is for contadores to view their clients' campaigns
    professional = await db.professionals.find_one(
        {"email": current_user.get("email"), "type": "contador"},
        {"_id": 0}
    )
    
    if not professional:
        return {"campaigns": [], "message": "Você não é um contador cadastrado"}
    
    campaign_ids = professional.get("campaigns", [])
    campaigns = await db.campaigns.find(
        {"id": {"$in": campaign_ids}},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "professional": professional,
        "campaigns": campaigns
    }

# ============== PIX PAYMENT ROUTES ==============
@api_router.post("/pix/payment")
async def create_pix_payment(data: PixPaymentCreate, current_user: dict = Depends(get_current_user)):
    """Create a PIX payment using Banco do Brasil API"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    # Verify expense exists if provided
    if data.expense_id:
        expense = await db.expenses.find_one(
            {"id": data.expense_id, "campaign_id": campaign_id}
        )
        if not expense:
            raise HTTPException(status_code=404, detail="Despesa não encontrada")
    
    pix_id = str(uuid.uuid4())
    bb_response = None
    txid = None
    pix_copia_cola = None
    
    # Try real BB integration if available
    if bb_pix_client and BB_PIX_AVAILABLE:
        try:
            bb_response = await bb_pix_client.create_pix_payment({
                "pix_key": data.pix_key,
                "recipient_name": data.recipient_name,
                "recipient_cpf_cnpj": data.recipient_cpf_cnpj,
                "amount": data.amount,
                "description": data.description,
                "scheduled_date": data.scheduled_date or datetime.now().strftime("%Y-%m-%d")
            })
            
            if bb_response.get("success"):
                txid = bb_response.get("txid")
                pix_copia_cola = bb_response.get("pixCopiaECola")
                logging.info(f"PIX BB criado com sucesso: {txid}")
            else:
                logging.warning(f"PIX BB falhou, usando modo simulado: {bb_response.get('error')}")
        except Exception as e:
            logging.error(f"Erro na integração BB PIX: {e}")
    
    pix_doc = {
        "id": pix_id,
        "pix_key": data.pix_key,
        "pix_key_type": data.pix_key_type,
        "recipient_name": data.recipient_name,
        "recipient_cpf_cnpj": data.recipient_cpf_cnpj,
        "amount": data.amount,
        "description": data.description,
        "scheduled_date": data.scheduled_date,
        "expense_id": data.expense_id,
        "status": "agendado" if data.scheduled_date else "processando",
        "transaction_id": txid,
        "pix_copia_cola": pix_copia_cola,
        "bb_response": bb_response if bb_response else None,
        "integration_mode": "real" if txid else "simulado",
        "campaign_id": campaign_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.pix_payments.insert_one(pix_doc)
    pix_doc.pop("_id", None)
    
    return {
        "message": "Pagamento PIX criado com sucesso",
        "pix_payment": pix_doc,
        "integration_mode": "real" if txid else "simulado",
        "bb_available": BB_PIX_AVAILABLE,
        "pix_copia_cola": pix_copia_cola
    }

@api_router.get("/pix/payments")
async def list_pix_payments(current_user: dict = Depends(get_current_user)):
    """List all PIX payments for campaign"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return []
    
    payments = await db.pix_payments.find(
        {"campaign_id": campaign_id},
        {"_id": 0}
    ).to_list(1000)
    
    return payments

@api_router.get("/pix/payment/{pix_id}")
async def get_pix_payment(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Get PIX payment by ID"""
    campaign_id = current_user.get("campaign_id")
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id},
        {"_id": 0}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return payment

@api_router.post("/pix/simulate-execution/{pix_id}")
async def simulate_pix_execution(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Simulate PIX execution (for testing - real execution requires BB API)"""
    campaign_id = current_user.get("campaign_id")
    
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    
    # Check if already executed
    if payment.get("status") == "executado":
        raise HTTPException(status_code=400, detail="PIX já foi executado")
    
    # Simulate transaction
    transaction_id = f"E{uuid.uuid4().hex[:20].upper()}"
    
    await db.pix_payments.update_one(
        {"id": pix_id},
        {
            "$set": {
                "status": "executado",
                "transaction_id": transaction_id,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # Update expense status if linked
    if payment.get("expense_id"):
        await db.expenses.update_one(
            {"id": payment.get("expense_id")},
            {"$set": {"payment_status": "pago", "pix_transaction_id": transaction_id}}
        )
    
    return {
        "message": "PIX executado com sucesso (simulação)",
        "transaction_id": transaction_id,
        "status": "executado"
    }

@api_router.get("/pix/bank-info")
async def get_bank_info():
    """Get Banco do Brasil integration info"""
    return {
        "bank": "Banco do Brasil",
        "integration_available": BB_PIX_AVAILABLE,
        "environment": BB_ENVIRONMENT if BB_PIX_AVAILABLE else None,
        "integration_status": "ativo" if BB_PIX_AVAILABLE else "não_configurado",
        "features": [
            "PIX Cobrança (cobv)",
            "PIX Pagamento",
            "Consulta de Status",
            "Geração de QR Code",
            "PIX Copia e Cola"
        ] if BB_PIX_AVAILABLE else [],
        "api_docs": "https://developers.bb.com.br",
        "note": "Integração com Banco do Brasil para PIX" if BB_PIX_AVAILABLE else "Configure as credenciais BB_APP_KEY, BB_CLIENT_ID e BB_CLIENT_SECRET no ambiente"
    }

@api_router.get("/pix/check-status/{pix_id}")
async def check_pix_status(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Check PIX payment status from Banco do Brasil"""
    campaign_id = current_user.get("campaign_id")
    
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    
    txid = payment.get("transaction_id")
    
    # If we have a real txid, check with BB
    if txid and bb_pix_client and BB_PIX_AVAILABLE:
        try:
            bb_status = await bb_pix_client.check_pix_status(txid)
            
            if bb_status.get("success"):
                # Update local record
                new_status = payment.get("status")
                bb_pix_status = bb_status.get("status", "")
                
                if bb_pix_status == "CONCLUIDA":
                    new_status = "executado"
                elif bb_pix_status == "REMOVIDA_PELO_USUARIO_RECEBEDOR":
                    new_status = "cancelado"
                elif bb_pix_status in ["ATIVA", "CRIADA"]:
                    new_status = "agendado"
                
                # Check if payment was received
                pix_received = bb_status.get("pix", [])
                if pix_received:
                    new_status = "executado"
                    # Update expense if linked
                    if payment.get("expense_id"):
                        await db.expenses.update_one(
                            {"id": payment.get("expense_id")},
                            {"$set": {"payment_status": "pago", "pix_transaction_id": txid}}
                        )
                
                await db.pix_payments.update_one(
                    {"id": pix_id},
                    {"$set": {
                        "status": new_status,
                        "bb_status": bb_pix_status,
                        "last_checked": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                return {
                    "pix_id": pix_id,
                    "txid": txid,
                    "local_status": new_status,
                    "bb_status": bb_pix_status,
                    "pix_received": pix_received,
                    "bb_response": bb_status
                }
            else:
                return {
                    "pix_id": pix_id,
                    "txid": txid,
                    "local_status": payment.get("status"),
                    "error": bb_status.get("error"),
                    "note": "Não foi possível consultar o status no Banco do Brasil"
                }
        except Exception as e:
            logging.error(f"Erro ao verificar status PIX: {e}")
            return {
                "pix_id": pix_id,
                "local_status": payment.get("status"),
                "error": str(e)
            }
    
    return {
        "pix_id": pix_id,
        "local_status": payment.get("status"),
        "integration_mode": payment.get("integration_mode", "simulado"),
        "note": "Pagamento em modo simulado - sem consulta real ao BB"
    }

@api_router.post("/pix/execute/{pix_id}")
async def execute_pix_payment(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Execute a scheduled PIX payment"""
    campaign_id = current_user.get("campaign_id")
    
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    
    if payment.get("status") == "executado":
        raise HTTPException(status_code=400, detail="PIX já foi executado")
    
    txid = payment.get("transaction_id")
    
    # If we have real integration, the PIX is already created on BB
    # We just need to wait for the recipient to pay
    if txid and BB_PIX_AVAILABLE:
        # Check current status
        if bb_pix_client:
            bb_status = await bb_pix_client.check_pix_status(txid)
            
            return {
                "message": "PIX já está ativo no Banco do Brasil",
                "txid": txid,
                "bb_status": bb_status.get("status") if bb_status.get("success") else "unknown",
                "pix_copia_cola": payment.get("pix_copia_cola"),
                "note": "O destinatário pode pagar usando o código PIX Copia e Cola ou QR Code"
            }
    
    # Simulate execution for non-integrated payments
    transaction_id = f"E{uuid.uuid4().hex[:20].upper()}"
    
    await db.pix_payments.update_one(
        {"id": pix_id},
        {
            "$set": {
                "status": "executado",
                "transaction_id": transaction_id,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # Update expense status if linked
    if payment.get("expense_id"):
        await db.expenses.update_one(
            {"id": payment.get("expense_id")},
            {"$set": {"payment_status": "pago", "pix_transaction_id": transaction_id}}
        )
    
    return {
        "message": "PIX executado com sucesso",
        "transaction_id": transaction_id,
        "status": "executado",
        "integration_mode": "simulado"
    }

# ============== TSE SPENDING LIMITS ==============
# Limites de gastos eleitorais do TSE - Portaria nº 593/2024
# Valores base para municípios de diferentes portes (eleições 2024)

TSE_SPENDING_LIMITS = {
    # Faixas de eleitorado com limites base (valores em R$)
    # Fonte: TSE Portaria 593/2024, atualizado pelo IPCA
    "prefeito": {
        "micro": {"min_eleitores": 0, "max_eleitores": 10000, "primeiro_turno": 159850.76, "segundo_turno": 63940.30},
        "pequeno": {"min_eleitores": 10001, "max_eleitores": 50000, "primeiro_turno": 500000.00, "segundo_turno": 200000.00},
        "medio": {"min_eleitores": 50001, "max_eleitores": 200000, "primeiro_turno": 2000000.00, "segundo_turno": 800000.00},
        "grande": {"min_eleitores": 200001, "max_eleitores": 1000000, "primeiro_turno": 10000000.00, "segundo_turno": 4000000.00},
        "metropole": {"min_eleitores": 1000001, "max_eleitores": float('inf'), "primeiro_turno": 67200000.00, "segundo_turno": 26880000.00}
    },
    "vereador": {
        "micro": {"min_eleitores": 0, "max_eleitores": 10000, "limite": 15985.08},
        "pequeno": {"min_eleitores": 10001, "max_eleitores": 50000, "limite": 50000.00},
        "medio": {"min_eleitores": 50001, "max_eleitores": 200000, "limite": 200000.00},
        "grande": {"min_eleitores": 200001, "max_eleitores": 1000000, "limite": 1000000.00},
        "metropole": {"min_eleitores": 1000001, "max_eleitores": float('inf'), "limite": 4770000.00}
    }
}

# Dados de alguns municípios conhecidos (para demonstração)
MUNICIPIOS_TSE = {
    "5200050": {"nome": "Anhanguera", "uf": "GO", "eleitores": 800, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "5101102": {"nome": "Araguainha", "uf": "MT", "eleitores": 950, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "3505302": {"nome": "Borá", "uf": "SP", "eleitores": 850, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "3550308": {"nome": "São Paulo", "uf": "SP", "eleitores": 9500000, "prefeito_1t": 67200000.00, "prefeito_2t": 26880000.00, "vereador": 4770000.00},
    "2611606": {"nome": "Recife", "uf": "PE", "eleitores": 1200000, "prefeito_1t": 9776138.29, "prefeito_2t": 3910455.32, "vereador": 1313263.10},
    "4106902": {"nome": "Curitiba", "uf": "PR", "eleitores": 1400000, "prefeito_1t": 14161044.67, "vereador": 689037.15},
    "2408102": {"nome": "Mossoró", "uf": "RN", "eleitores": 220000, "prefeito_1t": 3500000.00, "vereador": 350000.00},
    "2400505": {"nome": "Assú", "uf": "RN", "eleitores": 45000, "prefeito_1t": 450000.00, "vereador": 45000.00},
}

def calculate_spending_limit(cargo: str, eleitores: int, segundo_turno: bool = False) -> float:
    """Calculate TSE spending limit based on position and number of voters"""
    if cargo.lower() == "prefeito":
        limits = TSE_SPENDING_LIMITS["prefeito"]
        for faixa, dados in limits.items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                return dados["segundo_turno"] if segundo_turno else dados["primeiro_turno"]
    elif cargo.lower() == "vereador":
        limits = TSE_SPENDING_LIMITS["vereador"]
        for faixa, dados in limits.items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                return dados["limite"]
    return 0.0

@api_router.get("/tse/spending-limits")
async def get_spending_limits(
    cargo: str = Query(..., description="Cargo: prefeito ou vereador"),
    eleitores: int = Query(..., description="Número de eleitores do município"),
    segundo_turno: bool = Query(False, description="Se é segundo turno")
):
    """Calculate TSE spending limit for a position"""
    limit = calculate_spending_limit(cargo, eleitores, segundo_turno)
    
    # Find which bracket applies
    faixa = "desconhecida"
    if cargo.lower() == "prefeito":
        for f, dados in TSE_SPENDING_LIMITS["prefeito"].items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                faixa = f
                break
    elif cargo.lower() == "vereador":
        for f, dados in TSE_SPENDING_LIMITS["vereador"].items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                faixa = f
                break
    
    return {
        "cargo": cargo,
        "eleitores": eleitores,
        "segundo_turno": segundo_turno,
        "limite_gastos": limit,
        "limite_formatado": format_currency(limit),
        "faixa_municipio": faixa,
        "fonte": "TSE Portaria 593/2024",
        "nota": "Limite baseado nas eleições 2024, atualizado pelo IPCA"
    }

@api_router.get("/tse/municipio/{codigo_ibge}")
async def get_municipio_limits(codigo_ibge: str):
    """Get spending limits for a specific municipality by IBGE code"""
    municipio = MUNICIPIOS_TSE.get(codigo_ibge)
    if not municipio:
        raise HTTPException(status_code=404, detail="Município não encontrado na base")
    
    return {
        "codigo_ibge": codigo_ibge,
        "municipio": municipio["nome"],
        "uf": municipio["uf"],
        "eleitores": municipio["eleitores"],
        "limites": {
            "prefeito_primeiro_turno": municipio.get("prefeito_1t", 0),
            "prefeito_segundo_turno": municipio.get("prefeito_2t", municipio.get("prefeito_1t", 0) * 0.4),
            "vereador": municipio.get("vereador", 0)
        },
        "fonte": "TSE Portaria 593/2024"
    }

@api_router.get("/tse/campaign-status")
async def get_campaign_spending_status(current_user: dict = Depends(get_current_user)):
    """Get current campaign spending status vs TSE limits"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    # Calculate total expenses
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    total_spent = sum(e.get("amount", 0) for e in expenses)
    
    # Get the position and estimate voters (default for small city)
    position = campaign.get("position", "vereador").lower()
    eleitores = campaign.get("eleitores", 50000)  # Default estimate
    
    # Calculate limit
    limit = calculate_spending_limit(position, eleitores)
    
    # Check status
    percentage_used = (total_spent / limit * 100) if limit > 0 else 0
    remaining = limit - total_spent
    
    status = "ok"
    if percentage_used >= 100:
        status = "excedido"
    elif percentage_used >= 90:
        status = "critico"
    elif percentage_used >= 75:
        status = "atencao"
    
    alerts = []
    if status == "excedido":
        alerts.append({
            "type": "error",
            "message": f"ATENÇÃO: Limite de gastos excedido em {format_currency(abs(remaining))}!",
            "detail": "O candidato pode ser multado em 100% do valor excedente e enquadrado por abuso de poder econômico."
        })
    elif status == "critico":
        alerts.append({
            "type": "warning",
            "message": f"CRÍTICO: {percentage_used:.1f}% do limite já utilizado!",
            "detail": f"Restam apenas {format_currency(remaining)} para gastar."
        })
    elif status == "atencao":
        alerts.append({
            "type": "info",
            "message": f"ATENÇÃO: {percentage_used:.1f}% do limite já utilizado.",
            "detail": f"Restam {format_currency(remaining)} disponíveis."
        })
    
    return {
        "campaign": {
            "name": campaign.get("candidate_name"),
            "position": position,
            "city": campaign.get("city"),
            "state": campaign.get("state")
        },
        "spending": {
            "total_gasto": total_spent,
            "total_gasto_formatado": format_currency(total_spent),
            "limite_tse": limit,
            "limite_formatado": format_currency(limit),
            "saldo_disponivel": remaining,
            "saldo_formatado": format_currency(remaining),
            "percentual_utilizado": round(percentage_used, 2)
        },
        "status": status,
        "alerts": alerts,
        "penalidades": {
            "multa": "100% do valor excedente",
            "crime": "Abuso de poder econômico",
            "consequencias": ["Cassação do registro/diploma", "Inelegibilidade por 8 anos"]
        }
    }

# ============== ADMIN CONTADOR (ATIVA CONTABILIDADE) ==============
ADMIN_CONTADOR_EMAIL = "diretoria@ativacontabilidade.cnt.br"

class AdminInviteCreate(BaseModel):
    email: EmailStr
    name: str
    type: ProfessionalType = ProfessionalType.CONTADOR
    crc: Optional[str] = None
    crc_state: Optional[str] = None
    oab: Optional[str] = None
    oab_state: Optional[str] = None

class ContadorLogin(BaseModel):
    email: EmailStr
    password: str

@api_router.post("/admin/contador/login")
async def admin_contador_login(credentials: ContadorLogin):
    """Login for contador/advogado portal"""
    # Check if it's the admin account
    is_admin = credentials.email.lower() == ADMIN_CONTADOR_EMAIL.lower()
    
    # Find professional in database
    professional = await db.professionals.find_one({"email": credentials.email.lower()})
    
    if not professional:
        if is_admin:
            # Create admin account on first login attempt
            admin_doc = {
                "id": str(uuid.uuid4()),
                "email": ADMIN_CONTADOR_EMAIL,
                "name": "Diretoria Ativa Contabilidade",
                "type": "contador",
                "is_admin": True,
                "is_active": True,
                "has_system_access": True,
                "password_hash": hash_password("ativa2024"),  # Default password
                "campaigns": [],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.professionals.insert_one(admin_doc)
            professional = admin_doc
        else:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    # Verify password
    if not professional.get("password_hash"):
        raise HTTPException(status_code=401, detail="Conta não possui senha configurada. Entre em contato com o administrador.")
    
    if not verify_password(credentials.password, professional["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    # Create token
    token = create_token(
        professional["id"], 
        professional["email"], 
        "admin_contador" if professional.get("is_admin") else "contador"
    )
    
    professional.pop("password_hash", None)
    professional.pop("_id", None)
    
    return {
        "token": token,
        "professional": professional,
        "is_admin": professional.get("is_admin", False)
    }

@api_router.post("/admin/contador/invite")
async def admin_invite_professional(
    data: AdminInviteCreate,
    current_user: dict = Depends(get_current_user_or_contador)
):
    """Admin contador invites new professional (only admin can do this)"""
    # Verify if current user is admin
    professional = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not professional or not professional.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas o administrador pode enviar convites")
    
    # Check if professional already exists
    existing = await db.professionals.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um profissional com este email")
    
    # Generate temporary password
    temp_password = str(uuid.uuid4())[:8]
    
    # Create professional
    prof_id = str(uuid.uuid4())
    prof_doc = {
        "id": prof_id,
        "email": data.email.lower(),
        "name": data.name,
        "type": data.type.value,
        "crc": data.crc,
        "crc_state": data.crc_state,
        "oab": data.oab,
        "oab_state": data.oab_state,
        "is_active": True,
        "is_admin": False,
        "has_system_access": True,
        "password_hash": hash_password(temp_password),
        "campaigns": [],
        "invited_by": current_user.get("id"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.professionals.insert_one(prof_doc)
    
    # Send invitation email if Resend is configured
    email_sent = False
    if RESEND_AVAILABLE and RESEND_API_KEY:
        try:
            resend.emails.send({
                "from": SENDER_EMAIL,
                "to": [data.email],
                "subject": "Convite - Portal Eleitora 360",
                "html": f"""
                <h2>Bem-vindo ao Eleitora 360!</h2>
                <p>Olá {data.name},</p>
                <p>Você foi convidado(a) para fazer parte do Portal de Contadores do Eleitora 360.</p>
                <p><strong>Suas credenciais de acesso:</strong></p>
                <ul>
                    <li>Email: {data.email}</li>
                    <li>Senha temporária: <code>{temp_password}</code></li>
                </ul>
                <p>Acesse: <a href="{APP_URL}/contador/login">{APP_URL}/contador/login</a></p>
                <p>Por favor, altere sua senha no primeiro acesso.</p>
                <br>
                <p>Atenciosamente,<br>Equipe Ativa Contabilidade</p>
                """
            })
            email_sent = True
        except Exception as e:
            logging.error(f"Failed to send invitation email: {e}")
    
    prof_doc.pop("password_hash", None)
    prof_doc.pop("_id", None)
    
    return {
        "message": "Profissional convidado com sucesso",
        "professional": prof_doc,
        "temp_password": temp_password if not email_sent else None,
        "email_sent": email_sent,
        "note": "Senha temporária enviada por email" if email_sent else "Email não enviado. Informe a senha temporária manualmente."
    }

@api_router.get("/admin/contador/professionals")
async def admin_list_professionals(current_user: dict = Depends(get_current_user_or_contador)):
    """Admin lists all professionals"""
    professional = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not professional or not professional.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    
    professionals = await db.professionals.find(
        {},
        {"_id": 0, "password_hash": 0}
    ).to_list(1000)
    
    return {"professionals": professionals}

@api_router.get("/admin/contador/all-campaigns")
async def admin_list_all_campaigns(current_user: dict = Depends(get_current_user_or_contador)):
    """Admin lists all campaigns in the system"""
    professional = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not professional or not professional.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    
    campaigns = await db.campaigns.find({}, {"_id": 0}).to_list(1000)
    
    # Add spending info for each campaign
    for campaign in campaigns:
        expenses = await db.expenses.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(10000)
        revenues = await db.revenues.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(10000)
        
        total_expenses = sum(e.get("amount", 0) for e in expenses)
        total_revenues = sum(r.get("amount", 0) for r in revenues)
        
        campaign["financeiro"] = {
            "total_receitas": total_revenues,
            "total_despesas": total_expenses,
            "saldo": total_revenues - total_expenses
        }
    
    return {"campaigns": campaigns}

@api_router.post("/admin/contador/assign-campaign")
async def admin_assign_campaign_to_professional(
    professional_id: str = Query(...),
    campaign_id: str = Query(...),
    current_user: dict = Depends(get_current_user_or_contador)
):
    """Admin assigns a campaign to a professional"""
    admin = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    
    # Verify professional exists
    professional = await db.professionals.find_one({"id": professional_id})
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    # Verify campaign exists
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    # Add campaign to professional's list
    await db.professionals.update_one(
        {"id": professional_id},
        {"$addToSet": {"campaigns": campaign_id}}
    )
    
    return {
        "message": f"Campanha atribuída a {professional['name']}",
        "professional": professional["name"],
        "campaign": campaign["candidate_name"]
    }

@api_router.post("/contador/change-password")
async def contador_change_password(
    current_password: str,
    new_password: str,
    current_user: dict = Depends(get_current_user_or_contador)
):
    """Contador changes their password"""
    professional = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    # Verify current password
    if not verify_password(current_password, professional.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    
    # Update password
    await db.professionals.update_one(
        {"id": current_user.get("id")},
        {"$set": {"password_hash": hash_password(new_password)}}
    )
    
    return {"message": "Senha alterada com sucesso"}

@api_router.get("/contador/my-campaigns")
async def contador_get_my_campaigns(current_user: dict = Depends(get_current_user_or_contador)):
    """Contador gets their assigned campaigns"""
    professional = await db.professionals.find_one({"id": current_user.get("id")}, {"_id": 0})
    
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    campaign_ids = professional.get("campaigns", [])
    campaigns = await db.campaigns.find(
        {"id": {"$in": campaign_ids}},
        {"_id": 0}
    ).to_list(100)
    
    # Add financial summary for each campaign
    for campaign in campaigns:
        expenses = await db.expenses.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(10000)
        revenues = await db.revenues.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(10000)
        
        total_expenses = sum(e.get("amount", 0) for e in expenses)
        total_revenues = sum(r.get("amount", 0) for r in revenues)
        pending_expenses = sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente")
        
        campaign["resumo_financeiro"] = {
            "total_receitas": total_revenues,
            "total_despesas": total_expenses,
            "despesas_pendentes": pending_expenses,
            "saldo": total_revenues - total_expenses
        }
    
    return {
        "professional": {
            "id": professional["id"],
            "name": professional["name"],
            "email": professional["email"],
            "type": professional["type"],
            "is_admin": professional.get("is_admin", False)
        },
        "campaigns": campaigns
    }

@api_router.get("/contador/campaign/{campaign_id}/details")
async def contador_get_campaign_details(campaign_id: str, current_user: dict = Depends(get_current_user_or_contador)):
    """Contador gets detailed info of a specific campaign they have access to"""
    professional = await db.professionals.find_one({"id": current_user.get("id")})
    
    if not professional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    
    # Check access
    is_admin = professional.get("is_admin", False)
    has_access = campaign_id in professional.get("campaigns", [])
    
    if not is_admin and not has_access:
        raise HTTPException(status_code=403, detail="Você não tem acesso a esta campanha")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    # Get all financial data
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Calculate TSE limit status
    position = campaign.get("position", "vereador").lower()
    eleitores = campaign.get("eleitores", 50000)
    limit = calculate_spending_limit(position, eleitores)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    
    return {
        "campaign": campaign,
        "financeiro": {
            "receitas": revenues,
            "despesas": expenses,
            "contratos": contracts,
            "totais": {
                "total_receitas": sum(r.get("amount", 0) for r in revenues),
                "total_despesas": total_expenses,
                "despesas_pendentes": sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pendente"),
                "despesas_pagas": sum(e.get("amount", 0) for e in expenses if e.get("payment_status") == "pago"),
                "contratos_ativos": len([c for c in contracts if c.get("status") == "ativo"])
            }
        },
        "limite_tse": {
            "limite": limit,
            "limite_formatado": format_currency(limit),
            "gasto": total_expenses,
            "gasto_formatado": format_currency(total_expenses),
            "disponivel": limit - total_expenses,
            "disponivel_formatado": format_currency(limit - total_expenses),
            "percentual_usado": round((total_expenses / limit * 100) if limit > 0 else 0, 2)
        }
    }

# ============== ATIVA CONTABILIDADE INTEGRATION ==============
@api_router.get("/ativa-contabilidade/info")
async def get_ativa_info():
    """Get Ativa Contabilidade partner info"""
    return {
        "partner": "Ativa Contabilidade",
        "website": "https://ativacontabilidade.cnt.br",
        "description": "Contabilidade digital completa para sua empresa",
        "services": [
            "Área Contábil",
            "Obrigações Trabalhistas",
            "Assessoria Empresarial",
            "Departamento Fiscal",
            "Prestação de Contas Eleitorais"
        ],
        "coverage": [
            "Assú", "Pendências", "Paraú", "Afonso Bezerra", 
            "Ipanguaçu", "São Rafael", "Serra do Mel", "Upanema",
            "Carnaubais", "Triunfo Potiguar", "Itajá", "Mossoró",
            "São Paulo", "Todo o Rio Grande do Norte"
        ],
        "contact": {
            "website": "https://ativacontabilidade.cnt.br",
            "action": "falar com o especialista",
            "admin_email": ADMIN_CONTADOR_EMAIL
        },
        "integration_status": "partner",
        "logo_url": "https://ativacontabilidade.cnt.br/assets/imgs/h1.png"
    }

# ============== HEALTH CHECK ==============
@api_router.get("/")
async def root():
    return {"message": "Eleitora 360 API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Bank statement and validation endpoints defined below

# ============== BANK STATEMENT ENDPOINTS ==============

@api_router.post("/bank-statements/upload")
async def upload_bank_statement(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and parse OFX bank statement file"""
    if not OFX_AVAILABLE:
        raise HTTPException(status_code=500, detail="Parser OFX não disponível")
    
    # Validate file extension
    if not file.filename.lower().endswith(('.ofx', '.qfx')):
        raise HTTPException(status_code=400, detail="Formato de arquivo inválido. Use arquivos .ofx ou .qfx")
    
    try:
        content = await file.read()
        ofx = OfxParser.parse(BytesIO(content))
        
        # Get campaign
        campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        
        # Process account info
        account = ofx.account
        statement_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Parse transactions
        transactions = []
        total_credits = 0
        total_debits = 0
        
        for txn in account.statement.transactions:
            txn_type = BankTransactionType.CREDIT if txn.amount > 0 else BankTransactionType.DEBIT
            amount = abs(float(txn.amount))
            
            if txn_type == BankTransactionType.CREDIT:
                total_credits += amount
            else:
                total_debits += amount
            
            transaction = {
                "id": str(uuid.uuid4()),
                "statement_id": statement_id,
                "transaction_id": txn.id or str(uuid.uuid4()),
                "date": txn.date.strftime("%Y-%m-%d") if txn.date else now[:10],
                "amount": amount,
                "type": txn_type.value,
                "description": txn.memo or txn.payee or "Transação",
                "memo": txn.memo,
                "payee": txn.payee,
                "check_number": txn.checknum,
                "reconciliation_status": ReconciliationStatus.PENDING.value,
                "reconciled_with_id": None,
                "reconciled_with_type": None,
                "reconciled_at": None,
                "match_confidence": None,
                "campaign_id": campaign["id"],
                "created_at": now
            }
            transactions.append(transaction)
        
        # Create statement record
        statement = {
            "id": statement_id,
            "bank_name": account.institution.organization if hasattr(account, 'institution') and account.institution else "Banco",
            "account_number": account.account_id or "N/A",
            "account_type": account.account_type if hasattr(account, 'account_type') else None,
            "start_date": account.statement.start_date.strftime("%Y-%m-%d") if account.statement.start_date else now[:10],
            "end_date": account.statement.end_date.strftime("%Y-%m-%d") if account.statement.end_date else now[:10],
            "currency": account.statement.currency if hasattr(account.statement, 'currency') else "BRL",
            "total_credits": total_credits,
            "total_debits": total_debits,
            "transaction_count": len(transactions),
            "reconciled_count": 0,
            "pending_count": len(transactions),
            "campaign_id": campaign["id"],
            "created_at": now
        }
        
        # Save to database
        await db.bank_statements.insert_one(statement)
        if transactions:
            await db.bank_transactions.insert_many(transactions)
        
        return {
            "statement": statement,
            "transactions": transactions,
            "message": f"Extrato importado com sucesso: {len(transactions)} transações"
        }
        
    except Exception as e:
        logging.error(f"Erro ao processar arquivo OFX: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao processar arquivo: {str(e)}")

@api_router.get("/bank-statements")
async def list_bank_statements(current_user: dict = Depends(get_current_user)):
    """List all bank statements for current campaign"""
    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        return []
    
    statements = await db.bank_statements.find(
        {"campaign_id": campaign["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return statements

@api_router.get("/bank-statements/{statement_id}")
async def get_bank_statement(statement_id: str, current_user: dict = Depends(get_current_user)):
    """Get bank statement with transactions"""
    statement = await db.bank_statements.find_one({"id": statement_id}, {"_id": 0})
    if not statement:
        raise HTTPException(status_code=404, detail="Extrato não encontrado")
    
    transactions = await db.bank_transactions.find(
        {"statement_id": statement_id},
        {"_id": 0}
    ).sort("date", -1).to_list(1000)
    
    return {
        "statement": statement,
        "transactions": transactions
    }

@api_router.get("/bank-statements/{statement_id}/transactions")
async def get_statement_transactions(
    statement_id: str,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get transactions for a bank statement with optional status filter"""
    query = {"statement_id": statement_id}
    if status:
        query["reconciliation_status"] = status
    
    transactions = await db.bank_transactions.find(query, {"_id": 0}).sort("date", -1).to_list(1000)
    return transactions

@api_router.post("/bank-statements/{statement_id}/reconcile")
async def auto_reconcile_statement(statement_id: str, current_user: dict = Depends(get_current_user)):
    """Automatically reconcile bank transactions with revenues and expenses"""
    
    # Get statement
    statement = await db.bank_statements.find_one({"id": statement_id}, {"_id": 0})
    if not statement:
        raise HTTPException(status_code=404, detail="Extrato não encontrado")
    
    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    # Get pending transactions
    pending_txns = await db.bank_transactions.find(
        {"statement_id": statement_id, "reconciliation_status": ReconciliationStatus.PENDING.value},
        {"_id": 0}
    ).to_list(1000)
    
    # Get revenues and expenses for matching
    revenues = await db.revenues.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(1000)
    
    reconciled_count = 0
    results = []
    
    for txn in pending_txns:
        best_match = None
        best_confidence = 0
        match_type = None
        
        if txn["type"] == BankTransactionType.CREDIT.value:
            # Match with revenues
            for rev in revenues:
                confidence = calculate_match_confidence(txn, rev)
                if confidence > best_confidence and confidence >= 70:
                    best_confidence = confidence
                    best_match = rev
                    match_type = "revenue"
        else:
            # Match with expenses
            for exp in expenses:
                confidence = calculate_match_confidence(txn, exp)
                if confidence > best_confidence and confidence >= 70:
                    best_confidence = confidence
                    best_match = exp
                    match_type = "expense"
        
        if best_match:
            # Update transaction as reconciled
            now = datetime.now(timezone.utc).isoformat()
            await db.bank_transactions.update_one(
                {"id": txn["id"]},
                {"$set": {
                    "reconciliation_status": ReconciliationStatus.RECONCILED.value,
                    "reconciled_with_id": best_match["id"],
                    "reconciled_with_type": match_type,
                    "reconciled_at": now,
                    "match_confidence": best_confidence
                }}
            )
            reconciled_count += 1
            results.append({
                "transaction_id": txn["id"],
                "matched_with": best_match["id"],
                "matched_type": match_type,
                "confidence": best_confidence,
                "status": "reconciled"
            })
        else:
            results.append({
                "transaction_id": txn["id"],
                "status": "no_match",
                "confidence": 0
            })
    
    # Update statement counts
    all_txns = await db.bank_transactions.find({"statement_id": statement_id}, {"_id": 0}).to_list(1000)
    reconciled_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.RECONCILED.value])
    pending_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.PENDING.value])
    
    await db.bank_statements.update_one(
        {"id": statement_id},
        {"$set": {"reconciled_count": reconciled_total, "pending_count": pending_total}}
    )
    
    return {
        "message": f"Conciliação automática concluída: {reconciled_count} transações conciliadas",
        "reconciled_count": reconciled_count,
        "pending_count": pending_total,
        "results": results
    }

def calculate_match_confidence(transaction: dict, record: dict) -> float:
    """Calculate confidence score for matching a bank transaction with a revenue/expense"""
    confidence = 0
    
    # Amount match (40% weight)
    txn_amount = transaction["amount"]
    rec_amount = record["amount"]
    if abs(txn_amount - rec_amount) < 0.01:
        confidence += 40
    elif abs(txn_amount - rec_amount) / max(txn_amount, rec_amount) < 0.05:
        confidence += 30
    elif abs(txn_amount - rec_amount) / max(txn_amount, rec_amount) < 0.10:
        confidence += 15
    
    # Date match (30% weight)
    txn_date = transaction["date"]
    rec_date = record["date"]
    if txn_date == rec_date:
        confidence += 30
    else:
        try:
            txn_dt = datetime.strptime(txn_date, "%Y-%m-%d")
            rec_dt = datetime.strptime(rec_date, "%Y-%m-%d")
            diff_days = abs((txn_dt - rec_dt).days)
            if diff_days <= 1:
                confidence += 25
            elif diff_days <= 3:
                confidence += 15
            elif diff_days <= 7:
                confidence += 5
        except:
            pass
    
    # Description match (30% weight) - fuzzy matching
    txn_desc = (transaction.get("description") or "").lower()
    txn_payee = (transaction.get("payee") or "").lower()
    rec_desc = (record.get("description") or "").lower()
    rec_name = (record.get("donor_name") or record.get("supplier_name") or "").lower()
    
    # Check for common words
    txn_words = set(txn_desc.split() + txn_payee.split())
    rec_words = set(rec_desc.split() + rec_name.split())
    common_words = txn_words & rec_words
    
    if len(common_words) >= 3:
        confidence += 30
    elif len(common_words) >= 2:
        confidence += 20
    elif len(common_words) >= 1:
        confidence += 10
    
    # Check for CPF/CNPJ match
    rec_doc = record.get("donor_cpf_cnpj") or record.get("supplier_cpf_cnpj") or ""
    if rec_doc and rec_doc in txn_desc:
        confidence += 20
    
    return min(confidence, 100)

@api_router.post("/bank-transactions/{transaction_id}/reconcile-manual")
async def manual_reconcile_transaction(
    transaction_id: str,
    record_id: str = Query(...),
    record_type: str = Query(...),  # "revenue" or "expense"
    current_user: dict = Depends(get_current_user)
):
    """Manually reconcile a bank transaction with a revenue or expense"""
    
    # Validate record type
    if record_type not in ["revenue", "expense"]:
        raise HTTPException(status_code=400, detail="Tipo de registro inválido. Use 'revenue' ou 'expense'")
    
    # Get transaction
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    # Get record
    collection = db.revenues if record_type == "revenue" else db.expenses
    record = await collection.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail=f"{'Receita' if record_type == 'revenue' else 'Despesa'} não encontrada")
    
    # Update transaction
    now = datetime.now(timezone.utc).isoformat()
    await db.bank_transactions.update_one(
        {"id": transaction_id},
        {"$set": {
            "reconciliation_status": ReconciliationStatus.MANUAL.value,
            "reconciled_with_id": record_id,
            "reconciled_with_type": record_type,
            "reconciled_at": now,
            "match_confidence": 100
        }}
    )
    
    # Update statement counts
    statement = await db.bank_statements.find_one({"id": transaction["statement_id"]}, {"_id": 0})
    if statement:
        all_txns = await db.bank_transactions.find({"statement_id": statement["id"]}, {"_id": 0}).to_list(1000)
        reconciled_total = len([t for t in all_txns if t.get("reconciliation_status") in [ReconciliationStatus.RECONCILED.value, ReconciliationStatus.MANUAL.value]])
        pending_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.PENDING.value])
        
        await db.bank_statements.update_one(
            {"id": statement["id"]},
            {"$set": {"reconciled_count": reconciled_total, "pending_count": pending_total}}
        )
    
    return {"message": "Transação conciliada manualmente", "status": "success"}

@api_router.post("/bank-transactions/{transaction_id}/ignore")
async def ignore_transaction(transaction_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a bank transaction as ignored"""
    
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    await db.bank_transactions.update_one(
        {"id": transaction_id},
        {"$set": {"reconciliation_status": ReconciliationStatus.IGNORED.value}}
    )
    
    # Update statement counts
    statement = await db.bank_statements.find_one({"id": transaction["statement_id"]}, {"_id": 0})
    if statement:
        all_txns = await db.bank_transactions.find({"statement_id": statement["id"]}, {"_id": 0}).to_list(1000)
        pending_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.PENDING.value])
        
        await db.bank_statements.update_one(
            {"id": statement["id"]},
            {"$set": {"pending_count": pending_total}}
        )
    
    return {"message": "Transação ignorada", "status": "success"}

@api_router.post("/bank-transactions/{transaction_id}/create-record")
async def create_record_from_transaction(
    transaction_id: str,
    category: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Create a revenue or expense from a bank transaction"""
    
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    
    if transaction["type"] == BankTransactionType.CREDIT.value:
        # Create revenue
        revenue = {
            "id": record_id,
            "description": transaction["description"] or transaction["payee"] or "Receita importada",
            "amount": transaction["amount"],
            "category": category or "outros",
            "donor_name": transaction["payee"],
            "donor_cpf_cnpj": None,
            "date": transaction["date"],
            "receipt_number": None,
            "notes": f"Importado do extrato bancário. ID original: {transaction['transaction_id']}",
            "campaign_id": campaign["id"],
            "created_at": now,
            "attachment_id": None,
            "tipo_receita": "doacao_financeira",
            "tipo_doador": "pessoa_fisica",
            "forma_recebimento": "transferencia",
            "recibo_eleitoral": None,
            "donor_titulo_eleitor": None
        }
        await db.revenues.insert_one(revenue)
        record_type = "revenue"
    else:
        # Create expense
        expense = {
            "id": record_id,
            "description": transaction["description"] or transaction["payee"] or "Despesa importada",
            "amount": transaction["amount"],
            "category": category or "outros",
            "supplier_name": transaction["payee"],
            "supplier_cpf_cnpj": None,
            "date": transaction["date"],
            "invoice_number": None,
            "notes": f"Importado do extrato bancário. ID original: {transaction['transaction_id']}",
            "campaign_id": campaign["id"],
            "created_at": now,
            "attachment_id": None,
            "payment_status": "pago",
            "contract_id": None,
            "tipo_pagamento": "transferencia",
            "numero_parcela": None,
            "total_parcelas": None,
            "numero_documento_fiscal": None,
            "data_pagamento": transaction["date"]
        }
        await db.expenses.insert_one(expense)
        record_type = "expense"
    
    # Update transaction as reconciled
    await db.bank_transactions.update_one(
        {"id": transaction_id},
        {"$set": {
            "reconciliation_status": ReconciliationStatus.RECONCILED.value,
            "reconciled_with_id": record_id,
            "reconciled_with_type": record_type,
            "reconciled_at": now,
            "match_confidence": 100
        }}
    )
    
    return {
        "message": f"{'Receita' if record_type == 'revenue' else 'Despesa'} criada com sucesso",
        "record_id": record_id,
        "record_type": record_type
    }

@api_router.delete("/bank-statements/{statement_id}")
async def delete_bank_statement(statement_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a bank statement and all its transactions"""
    
    statement = await db.bank_statements.find_one({"id": statement_id}, {"_id": 0})
    if not statement:
        raise HTTPException(status_code=404, detail="Extrato não encontrado")
    
    # Delete transactions
    await db.bank_transactions.delete_many({"statement_id": statement_id})
    
    # Delete statement
    await db.bank_statements.delete_one({"id": statement_id})
    
    return {"message": "Extrato e transações excluídos com sucesso"}

# ============== CPF/CNPJ VALIDATION ENDPOINT ==============

@api_router.get("/validate/document")
async def validate_document(cpf_cnpj: str = Query(...)):
    """Validate and format CPF or CNPJ"""
    # Remove formatting
    doc = re.sub(r'[^0-9]', '', cpf_cnpj)
    
    if len(doc) == 11:
        # CPF
        is_valid = validate_cpf(doc)
        formatted = format_cpf(doc) if is_valid else doc
        return {
            "type": "cpf",
            "valid": is_valid,
            "formatted": formatted,
            "raw": doc
        }
    elif len(doc) == 14:
        # CNPJ
        is_valid = validate_cnpj(doc)
        formatted = format_cnpj(doc) if is_valid else doc
        return {
            "type": "cnpj",
            "valid": is_valid,
            "formatted": formatted,
            "raw": doc
        }
    else:
        return {
            "type": "unknown",
            "valid": False,
            "formatted": cpf_cnpj,
            "raw": doc,
            "error": "Documento deve ter 11 dígitos (CPF) ou 14 dígitos (CNPJ)"
        }

# Include router - AFTER all route definitions
app.include_router(api_router)

cors_origins = [
    origin.strip()
    for origin in os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
    if origin.strip()
]
if not cors_origins:
    cors_origins = ['http://localhost:3000']

# Browsers reject wildcard origins when credentials are enabled.
cors_allow_credentials = os.environ.get('CORS_ALLOW_CREDENTIALS', 'false').lower() == 'true'
if '*' in cors_origins:
    cors_allow_credentials = False

cors_origin_regex = os.environ.get(
    'CORS_ORIGIN_REGEX',
    r'https://.*\.vercel\.app'
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=cors_allow_credentials,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
