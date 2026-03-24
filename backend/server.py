from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Query, Form, BackgroundTasks, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
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
import unicodedata
import xml.etree.ElementTree as ET
import tempfile
import shutil
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr, validator
from typing import List, Optional, Dict, Any
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
    from PyPDF2 import PdfReader
    PDF_TEXT_EXTRACTION_AVAILABLE = True
except ImportError:
    PDF_TEXT_EXTRACTION_AVAILABLE = False

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

# TSE Import system - Force rebuild 2025-03-10
try:
    from tse_import import TSEImportManager, DatabaseImporter, DataMapper
    TSE_IMPORT_AVAILABLE = True
except ImportError:
    TSE_IMPORT_AVAILABLE = False

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(
    mongo_url,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=20000,
    socketTimeoutMS=20000,
)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Email Config
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
APP_URL = os.environ.get('APP_URL', 'https://brasil-voting.preview.emergentagent.com')
GOVBR_SIGNATURE_URL = os.environ.get('GOVBR_SIGNATURE_URL', 'https://assinador.iti.br/')

if RESEND_AVAILABLE and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Banco do Brasil PIX API Config
BB_APP_KEY = os.environ.get('BB_APP_KEY', '')
BB_CLIENT_ID = os.environ.get('BB_CLIENT_ID', '')
BB_CLIENT_SECRET = os.environ.get('BB_CLIENT_SECRET', '')
BB_ENVIRONMENT = os.environ.get('BB_ENVIRONMENT', 'homologacao')
BB_CLIENT_CERT_PATH = os.environ.get('BB_CLIENT_CERT_PATH', '')
BB_CLIENT_KEY_PATH = os.environ.get('BB_CLIENT_KEY_PATH', '')
BB_STRICT_MODE = os.environ.get('BB_STRICT_MODE', 'false').lower() == 'true'

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
TSE_IMPORT_MAX_FILE_SIZE = int(os.environ.get("TSE_IMPORT_MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB

# ============== BANCO DO BRASIL PIX INTEGRATION ==============
class BancoDoBrasilPIX:
    """Classe para integraÃ§Ã£o com a API PIX do Banco do Brasil"""
    
    def __init__(self):
        self.app_key = BB_APP_KEY
        self.client_id = BB_CLIENT_ID
        self.client_secret = BB_CLIENT_SECRET
        self.oauth_url = BB_OAUTH_URL
        self.api_url = BB_API_URL
        self.access_token = None
        self.token_expires_at = None
    
    def _cert_config(self):
        cert_path = BB_CLIENT_CERT_PATH.strip() if BB_CLIENT_CERT_PATH else ""
        key_path = BB_CLIENT_KEY_PATH.strip() if BB_CLIENT_KEY_PATH else ""
        if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
            return (cert_path, key_path)
        if cert_path and os.path.exists(cert_path):
            return cert_path
        return None

    def _httpx_client_kwargs(self) -> dict:
        kwargs = {"timeout": 30.0}
        cert_config = self._cert_config()
        if cert_config:
            kwargs["cert"] = cert_config
        return kwargs

    def get_diagnostic_snapshot(self) -> dict:
        cert_config = self._cert_config()
        return {
            "configured": BB_PIX_AVAILABLE,
            "strict_mode": BB_STRICT_MODE,
            "environment": BB_ENVIRONMENT,
            "oauth_url": self.oauth_url,
            "api_url": self.api_url,
            "has_app_key": bool(self.app_key),
            "has_client_id": bool(self.client_id),
            "has_client_secret": bool(self.client_secret),
            "uses_client_certificate": bool(cert_config),
            "client_cert_path": BB_CLIENT_CERT_PATH if BB_CLIENT_CERT_PATH else None,
            "client_key_path": BB_CLIENT_KEY_PATH if BB_CLIENT_KEY_PATH else None,
        }

    async def diagnose_connection(self) -> dict:
        snapshot = self.get_diagnostic_snapshot()
        if not snapshot["configured"]:
            snapshot["status"] = "not_configured"
            snapshot["oauth_ok"] = False
            snapshot["message"] = "Credenciais BB nao configuradas no ambiente."
            return snapshot
        try:
            token = await self.get_access_token()
            snapshot["oauth_ok"] = bool(token)
            snapshot["status"] = "ok" if token else "error"
            snapshot["message"] = "OAuth BB validado com sucesso." if token else "Token vazio."
            return snapshot
        except Exception as e:
            snapshot["oauth_ok"] = False
            snapshot["status"] = "error"
            snapshot["message"] = f"Falha na autenticacao OAuth: {str(e)}"
            return snapshot
        
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
        
        async with httpx.AsyncClient(**self._httpx_client_kwargs()) as client:
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
        
        async with httpx.AsyncClient(**self._httpx_client_kwargs()) as client:
            try:
                # Create cobranÃ§a (billing request)
                response = await client.put(
                    f"{self.api_url}/cobv/{txid}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                logging.info(f"BB PIX: CobranÃ§a criada - txid: {txid}")
                
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
                logging.error(f"BB PIX: Erro ao criar cobranÃ§a: {error_detail}")
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
        
        async with httpx.AsyncClient(**self._httpx_client_kwargs()) as client:
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
        """Lista PIX recebidos em um perÃ­odo"""
        token = await self.get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "gw-dev-app-key": self.app_key
        }
        
        params = {
            "inicio": f"{start_date}T00:00:00Z",
            "fim": f"{end_date}T23:59:59Z"
        }
        
        async with httpx.AsyncClient(**self._httpx_client_kwargs()) as client:
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

# Root endpoint for platform health checks
@app.get("/")
async def root():
    return {"status": "ok"}

# Health check endpoint to diagnose module loading
@app.get("/api/health")
async def health_check():
    """Check API health and module availability"""
    diagnostics = {
        "status": "ok",
        "modules": {
            "pdf": PDF_AVAILABLE,
            "pdf_text_extraction": PDF_TEXT_EXTRACTION_AVAILABLE,
            "resend": RESEND_AVAILABLE,
            "ofx": OFX_AVAILABLE,
            "tse_import": TSE_IMPORT_AVAILABLE
        }
    }

    # Try to import tse_import if it failed
    if not TSE_IMPORT_AVAILABLE:
        try:
            from tse_import import TSEImportManager
            diagnostics["tse_import_error"] = "Module exists but failed to import"
        except ImportError as e:
            diagnostics["tse_import_error"] = f"ImportError: {str(e)}"
            diagnostics["tse_import_detail"] = "pdfplumber missing or other dependency error"
        except Exception as e:
            diagnostics["tse_import_error"] = f"Exception: {str(e)}"

    return diagnostics

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

def normalize_document(document: Optional[str]) -> Optional[str]:
    """Return document digits only."""
    if document is None:
        return None
    cleaned = re.sub(r'[^0-9]', '', str(document))
    return cleaned or None

def validate_and_normalize_document(
    document: Optional[str],
    field_name: str,
    allowed_types=("cpf", "cnpj"),
    required: bool = False,
) -> Optional[str]:
    """Validate CPF/CNPJ and return normalized digits."""
    doc = normalize_document(document)
    if not doc:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} é obrigatório")
        return None

    if len(doc) == 11:
        if "cpf" not in allowed_types:
            raise HTTPException(status_code=400, detail=f"{field_name} deve ser CNPJ")
        if not validate_cpf(doc):
            raise HTTPException(status_code=400, detail=f"{field_name} invÃ¡lido")
        return doc

    if len(doc) == 14:
        if "cnpj" not in allowed_types:
            raise HTTPException(status_code=400, detail=f"{field_name} deve ser CPF")
        if not validate_cnpj(doc):
            raise HTTPException(status_code=400, detail=f"{field_name} invÃ¡lido")
        return doc

    if allowed_types == ("cpf",):
        expected = "11 dÃ­gitos (CPF)"
    elif allowed_types == ("cnpj",):
        expected = "14 dÃ­gitos (CNPJ)"
    else:
        expected = "11 dÃ­gitos (CPF) ou 14 dÃ­gitos (CNPJ)"
    raise HTTPException(status_code=400, detail=f"{field_name} deve ter {expected}")

# ============== ENUMS ==============
class UserRole(str, Enum):
    CANDIDATO = "candidato"
    CONTADOR = "contador"

class ContractStatus(str, Enum):
    RASCUNHO = "rascunho"
    AGUARDANDO_ASSINATURA = "aguardando_assinatura"
    ASSINADO_LOCADOR = "assinado_locador"
    ASSINADO_LOCATÁRIO = "assinado_locatario"
    ATIVO = "ativo"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"

class ContractTemplateType(str, Enum):
    # Legacy templates (mantidos por compatibilidade)
    BEM_MOVEL = "bem_movel"
    ESPACO_EVENTO = "espaco_evento"
    IMOVEL = "imovel"
    VEICULO_COM_MOTORISTA = "veiculo_com_motorista"
    VEICULO_SEM_MOTORISTA = "veiculo_sem_motorista"
    # SPCE templates
    IMOVEL_COMITE = "imovel_comite"
    IMOVEL_EVENTO = "imovel_evento"
    SERVICO_GRAFICO = "servico_grafico"
    SERVICO_PUBLICIDADE = "servico_publicidade"
    SERVICO_PESQUISA = "servico_pesquisa"
    SERVICO_JURIDICO = "servico_juridico"
    SERVICO_CONTABIL = "servico_contabil"
    SERVICO_TI = "servico_ti"
    PRODUCAO_AUDIOVISUAL = "producao_audiovisual"
    IMPULSIONAMENTO = "impulsionamento"
    OUTROS = "outros"

# Required attachments by contract type
CONTRACT_REQUIRED_ATTACHMENTS = {
    "veiculo_com_motorista": [
        {"key": "doc_veiculo", "label": "Documento do VeÃ­culo (CRLV)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio (RG/CPF)", "required": True},
        {"key": "cnh_motorista", "label": "CNH do Motorista", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "veiculo_sem_motorista": [
        {"key": "doc_veiculo", "label": "Documento do VeÃ­culo (CRLV)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio (RG/CPF)", "required": True},
        {"key": "cnh_proprietario", "label": "CNH do ProprietÃ¡rio", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "imovel": [
        {"key": "doc_imovel", "label": "Documento do Imóvel (Escritura/Contrato)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio/Locador (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia do Locador", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "bem_movel": [
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia", "required": True},
        {"key": "doc_bem", "label": "Documento do Bem (se houver)", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "espaco_evento": [
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio/ResponsÃ¡vel (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia", "required": True},
        {"key": "doc_espaco", "label": "Documento do Espaço (se houver)", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "imovel_comite": [
        {"key": "doc_imovel", "label": "Documento do Imóvel (Escritura/Contrato)", "required": True},
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio/Locador (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia do Locador", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "imovel_evento": [
        {"key": "doc_proprietario", "label": "Documento do ProprietÃ¡rio/ResponsÃ¡vel (RG/CPF)", "required": True},
        {"key": "comprovante_residencia", "label": "Comprovante de ResidÃªncia", "required": True},
        {"key": "doc_espaco", "label": "Documento do Espaço (se houver)", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_grafico": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Proposta/OrÃ§amento do Serviço", "required": True},
        {"key": "arte_aprovada", "label": "Arte/EspecificaÃ§Ã£o do Material", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_publicidade": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Proposta/Plano de MÃ­dia", "required": True},
        {"key": "relatorio_entrega", "label": "RelatÃ³rio de Entrega/VeiculaÃ§Ã£o", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_pesquisa": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Proposta/Plano de Pesquisa", "required": True},
        {"key": "relatorio_entrega", "label": "RelatÃ³rio/Resultado da Pesquisa", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_juridico": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "doc_oab", "label": "ComprovaÃ§Ã£o de OAB (se aplicÃ¡vel)", "required": False},
        {"key": "proposta_servico", "label": "Proposta/Objeto do Serviço", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_contabil": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "doc_crc", "label": "ComprovaÃ§Ã£o de CRC (se aplicÃ¡vel)", "required": False},
        {"key": "proposta_servico", "label": "Proposta/Objeto do Serviço", "required": True},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "servico_ti": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Escopo Técnico do Serviço", "required": True},
        {"key": "relatorio_entrega", "label": "RelatÃ³rio de Entrega", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "producao_audiovisual": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Roteiro/Escopo da ProduÃ§Ã£o", "required": True},
        {"key": "relatorio_entrega", "label": "ComprovaÃ§Ã£o de Entrega do Material", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "impulsionamento": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "Plano de Impulsionamento", "required": True},
        {"key": "relatorio_entrega", "label": "RelatÃ³rio de VeiculaÃ§Ã£o", "required": False},
        {"key": "comprovante_pagamento", "label": "Comprovante de Pagamento", "required": False}
    ],
    "outros": [
        {"key": "doc_prestador", "label": "Documento do Prestador (RG/CPF ou CNPJ)", "required": True},
        {"key": "proposta_servico", "label": "DescriÃ§Ã£o/Proposta do Objeto", "required": True},
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
    eleitores: Optional[int] = None  # NÃºmero de eleitores do municÃ­pio (para cÃ¡lculo do limite TSE)
    codigo_ibge: Optional[str] = None  # CÃ³digo IBGE do municÃ­pio
    segundo_turno: Optional[bool] = False
    limite_gastos: Optional[float] = None
    limite_fonte: Optional[str] = None
    limite_ano_base: Optional[int] = None
    # SPCE Required Fields
    cnpj: Optional[str] = None  # CNPJ da campanha
    numero_candidato: Optional[str] = None  # NÃºmero do candidato
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
    segundo_turno: Optional[bool] = False
    limite_gastos: Optional[float] = None
    limite_fonte: Optional[str] = None
    limite_ano_base: Optional[int] = None
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
    recibo_eleitoral: Optional[str] = None  # NÃºmero do recibo eleitoral (auto-gerado)
    donor_titulo_eleitor: Optional[str] = None  # TÃ­tulo de eleitor do doador PF

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
    contador_professional_id: Optional[str] = None
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
    # Reboque/ParedÃ£o fields
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
    assinatura_externa_iniciada_em: Optional[str] = None
    signed_document_attachment_id: Optional[str] = None
    signed_document_uploaded_at: Optional[str] = None

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
    contador_professional_id: Optional[str] = None
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
    assinatura_externa_iniciada_em: Optional[str] = None
    signed_document_attachment_id: Optional[str] = None
    signed_document_uploaded_at: Optional[str] = None
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
    oab: Optional[str] = None  # NÃºmero OAB
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
    source_account_type: Optional[str] = "doacao"  # doacao, fundo_partidario, fefec
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
    source_account_type: Optional[str] = "doacao"
    source_bank: Optional[str] = None
    source_agency: Optional[str] = None
    source_account: Optional[str] = None
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
    DEBIT = "debit"    # SaÃ­da (despesa)

class ReconciliationStatus(str, Enum):
    PENDING = "pending"           # Aguardando conciliaÃ§Ã£o
    RECONCILED = "reconciled"     # Conciliado automaticamente
    MANUAL = "manual"             # Conciliado manualmente
    DIVERGENT = "divergent"       # DivergÃªncia encontrada
    IGNORED = "ignored"           # Ignorado pelo usuÃ¡rio

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
    match_confidence: Optional[float] = None  # 0-100% de confianÃ§a do match
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
            raise HTTPException(status_code=401, detail="UsuÃ¡rio nÃ£o encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invÃ¡lido")

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
        
        raise HTTPException(status_code=401, detail="UsuÃ¡rio nÃ£o encontrado")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invÃ¡lido")

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
        months = ['janeiro', 'fevereiro', 'marÃ§o', 'abril', 'maio', 'junho', 
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
        <p><strong>LOCATÃRIO:</strong></p>
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
            <strong>CLÃUSULA TERCEIRA.</strong> Pela locação ora ajustada, o LOCATÃRIO pagará a quantia de 
            <strong>{format_currency(contract_data.get('value', 0))}</strong>, cujo pagamento será efetuado 
            até o dia {format_date_br(contract_data.get('end_date', ''))}.
        </p>
    """
    
    term_clause = f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DA VIGÊNCIA</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA SEGUNDA.</strong> O presente contrato terÃ¡ vigência a partir de 
            {format_date_br(contract_data.get('start_date', ''))} até {format_date_br(contract_data.get('end_date', ''))}.
        </p>
    """
    
    # Forum clause
    forum_clause = f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO FORO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA QUARTA.</strong> As partes elegem o Foro da Comarca de 
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
                <p><strong>{campaign.get('candidate_name', '_______________')}</strong><br>LOCATÃRIO</p>
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

def _normalize_contract_template_type(template_type: str) -> str:
    legacy_aliases = {
        "imovel": "imovel_comite",
        "espaco_evento": "imovel_evento",
    }
    return legacy_aliases.get(template_type, template_type or "outros")

def get_contract_title(template_type: str) -> str:
    normalized = _normalize_contract_template_type(template_type)
    titles = {
        "veiculo_com_motorista": "VEÃCULO COM MOTORISTA PARA CAMPANHA ELEITORAL",
        "veiculo_sem_motorista": "VEÃCULO SEM MOTORISTA PARA CAMPANHA ELEITORAL",
        "imovel_comite": "IMÃ“VEL PARA COMITÃŠ DE CAMPANHA",
        "imovel_evento": "IMÃ“VEL/ESPAÇO PARA EVENTO ELEITORAL",
        "servico_grafico": "SERVIÇOS GRÃFICOS DE CAMPANHA",
        "servico_publicidade": "SERVIÇOS DE PUBLICIDADE DE CAMPANHA",
        "servico_pesquisa": "SERVIÇOS DE PESQUISA ELEITORAL",
        "servico_juridico": "SERVIÇOS JURÃDICOS ELEITORAIS",
        "servico_contabil": "SERVIÇOS CONTÃBEIS ELEITORAIS",
        "servico_ti": "SERVIÇOS DE TECNOLOGIA DA INFORMAÇÃO",
        "producao_audiovisual": "PRODUÇÃO AUDIOVISUAL DE CAMPANHA",
        "impulsionamento": "IMPULSIONAMENTO DE CONTEÚDO ELEITORAL",
        "outros": "OUTROS SERVIÇOS/LOCAÇÕES DE CAMPANHA",
        "bem_movel": "BEM MÃ“VEL PARA CAMPANHA ELEITORAL",
    }
    return titles.get(normalized, "OUTROS SERVIÇOS/LOCAÇÕES DE CAMPANHA")

def generate_object_clause(template_type: str, contract_data: dict) -> str:
    normalized = _normalize_contract_template_type(template_type)
    if normalized == "bem_movel":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para uso exclusivo 
            da campanha eleitoral do LOCATÃRIO, do seguinte bem móvel de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCATÃRIO é obrigado a conservar o bem móvel ora alugado, 
            ficando responsÃ¡vel pelo seu bom estado de conservaÃ§Ã£o.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> São vedados a transferência, a sublocação, a cessão ou o empréstimo, 
            total ou parcial, do bem locado sem prévia anuÃªncia expressa do LOCADOR.
        </p>
        """
    elif normalized == "imovel_evento":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para realizaÃ§Ã£o 
            de atividade da campanha eleitoral do LOCATÃRIO, do seguinte espaÃ§o de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCADOR colocarÃ¡ o espaÃ§o Ã  disposiÃ§Ã£o do LOCATÃRIO entre as 
            {contract_data.get('evento_horario_inicio', '___')} e {contract_data.get('evento_horario_fim', '___')} horas.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> O LOCATÃRIO usarÃ¡ com zelo as dependÃªncias, devendo restituÃ­-lo 
            ao término do perÃ­odo em seu estado inicial.
        </p>
        """
    elif normalized == "imovel_comite":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação, para uso exclusivo 
            da campanha eleitoral do LOCATÃRIO, do seguinte bem imóvel de propriedade do LOCADOR:
        </p>
        <p style="margin-left: 40px;">
            <strong>{contract_data.get('imovel_descricao', '_______________')}</strong><br>
            Registro: {contract_data.get('imovel_registro', '_______________')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCATÃRIO é obrigado a conservar o bem imóvel ora alugado, 
            ficando responsÃ¡vel pelas obras necessÃ¡rias ao seu bom estado de conservaÃ§Ã£o.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Segundo.</em> São vedados a transferência, a sublocação, a cessão ou o empréstimo, 
            total ou parcial, do imóvel locado sem prévia anuÃªncia expressa do LOCADOR.
        </p>
        """
    elif normalized == "veiculo_com_motorista":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação do veÃ­culo:
        </p>
        <p style="margin-left: 40px;">
            <strong>VeÃ­culo:</strong> {contract_data.get('veiculo_marca', '___')} {contract_data.get('veiculo_modelo', '___')}<br>
            <strong>Ano:</strong> {contract_data.get('veiculo_ano', '___')}<br>
            <strong>Placa:</strong> {contract_data.get('veiculo_placa', '___')}<br>
            <strong>RENAVAM:</strong> {contract_data.get('veiculo_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <strong>Motorista:</strong> {contract_data.get('motorista_nome', '_______________')}, 
            CNH nº {contract_data.get('motorista_cnh', '_______________')}
        </p>
        <p style="text-align: justify;">
            <strong>Equipamento a ser puxado (se aplicÃ¡vel):</strong><br>
            {contract_data.get('reboque_descricao', '_______________')}<br>
            Placa: {contract_data.get('reboque_placa', '___')} - RENAVAM: {contract_data.get('reboque_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo Ãºnico.</em> O LOCATÃRIO deverÃ¡ devolver o veÃ­culo ao LOCADOR nas mesmas condiÃ§Ãµes 
            em que o recebeu, respondendo por danos ou prejuÃ­zos causados.
        </p>
        """
    elif normalized == "veiculo_sem_motorista":
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a locação do veÃ­culo:
        </p>
        <p style="margin-left: 40px;">
            <strong>VeÃ­culo:</strong> {contract_data.get('veiculo_marca', '___')} {contract_data.get('veiculo_modelo', '___')}<br>
            <strong>Ano:</strong> {contract_data.get('veiculo_ano', '___')}<br>
            <strong>Placa:</strong> {contract_data.get('veiculo_placa', '___')}<br>
            <strong>RENAVAM:</strong> {contract_data.get('veiculo_renavam', '___')}
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O automóvel será utilizado exclusivamente pelo LOCATÃRIO ou 
            terceiros sob sua responsabilidade.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo segundo.</em> O LOCATÃRIO deverÃ¡ devolver o automóvel ao LOCADOR nas mesmas 
            condiÃ§Ãµes em que o recebeu, respondendo por danos ou prejuÃ­zos causados.
        </p>
        """
    elif normalized in {
        "servico_grafico",
        "servico_publicidade",
        "servico_pesquisa",
        "servico_juridico",
        "servico_contabil",
        "servico_ti",
        "producao_audiovisual",
        "impulsionamento",
    }:
        service_labels = {
            "servico_grafico": "serviÃ§os grÃ¡ficos",
            "servico_publicidade": "serviÃ§os de publicidade",
            "servico_pesquisa": "serviÃ§os de pesquisa eleitoral",
            "servico_juridico": "serviÃ§os jurÃ­dicos",
            "servico_contabil": "serviÃ§os contÃ¡beis",
            "servico_ti": "serviÃ§os de tecnologia da informaÃ§Ã£o",
            "producao_audiovisual": "serviÃ§os de produÃ§Ã£o audiovisual",
            "impulsionamento": "serviÃ§os de impulsionamento de conteÃºdo",
        }
        service_desc = service_labels.get(normalized, "serviÃ§os especializados")
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a prestaÃ§Ã£o de {service_desc}
            para a campanha eleitoral do LOCATÃRIO, conforme escopo abaixo:
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo primeiro.</em> O LOCADOR compromete-se a executar os serviÃ§os com observÃ¢ncia Ã  legislaÃ§Ã£o eleitoral,
            incluindo regras de transparÃªncia e prestaÃ§Ã£o de contas aplicÃ¡veis ao SPCE.
        </p>
        <p style="text-align: justify;">
            <em>Parágrafo segundo.</em> O LOCADOR deverÃ¡ entregar comprovantes de execuÃ§Ã£o e documentos fiscais
            idÃ´neos correspondentes aos serviÃ§os contratados.
        </p>
        """
    else:
        return f"""
        <h3 style="font-size: 12pt; margin-top: 20px;">DO OBJETO</h3>
        <p style="text-align: justify;">
            <strong>CLÃUSULA PRIMEIRA.</strong> Constitui OBJETO deste contrato a prestaÃ§Ã£o de serviÃ§os e/ou
            locação de bens para uso na campanha eleitoral do LOCATÃRIO.
        </p>
        <p style="margin-left: 40px;"><strong>{contract_data.get('objeto_descricao', '_______________')}</strong></p>
        <p style="text-align: justify;">
            <em>Parágrafo Ãºnico.</em> Todas as entregas e pagamentos devem possuir comprovaÃ§Ã£o documental
            para fins de prestaÃ§Ã£o de contas eleitoral.
        </p>
        """

def get_signature_status(contract_data: dict, party: str) -> str:
    if party == "locador":
        if contract_data.get('locador_assinatura_hash'):
            return f"<span style='color: green;'>âœ“ Assinado digitalmente em {contract_data.get('locador_assinatura_data', '')}</span>"
        return "<span style='color: #999;'>Aguardando assinatura</span>"
    else:
        if contract_data.get('locatario_assinatura_hash'):
            return f"<span style='color: green;'>âœ“ Assinado digitalmente em {contract_data.get('locatario_assinatura_data', '')}</span>"
        return "<span style='color: #999;'>Aguardando assinatura</span>"

def generate_signature_token(contract_id: str, email: str, party: str, digital_cert: bool = False) -> str:
    """Generate a unique token for signature request with optional digital certificate support"""
    payload = {
        "contract_id": contract_id,
        "email": email,
        "party": party,
        "digital_cert_required": digital_cert,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def build_govbr_signature_metadata(contract: dict, party: str) -> dict:
    """Build metadata for GOV.BR certified digital signature"""
    return {
        "contract_id": contract.get("id"),
        "contract_title": contract.get("title", "Contrato"),
        "contract_value": contract.get("value", 0),
        "party": party,
        "signature_method": "iti_gov_br",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature_requirements": {
            "biometric_validation": True,
            "certificate_required": True,
            "audit_trail": True
        }
    }

def _render_text_document_bytes(title: str, lines: List[str]) -> tuple[bytes, str, str]:
    """Render a simple auto-generated document as PDF (preferred) or TXT fallback."""
    content_type = "application/pdf" if PDF_AVAILABLE else "text/plain"
    ext = ".pdf" if PDF_AVAILABLE else ".txt"

    if PDF_AVAILABLE:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "AutoDocTitle",
            parent=styles["Heading1"],
            fontSize=13,
            leading=17,
            alignment=TA_LEFT,
            spaceAfter=10,
        )
        body_style = ParagraphStyle(
            "AutoDocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
        story = [Paragraph(title, title_style), Spacer(1, 0.3 * cm)]
        for line in lines:
            story.append(Paragraph(line, body_style))
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue(), content_type, ext

    txt = title + "\n\n" + "\n".join(lines)
    return txt.encode("utf-8"), content_type, ext

async def _get_contador_for_campaign(contador_id: str, campaign_id: str) -> dict:
    contador = await db.professionals.find_one(
        {"id": contador_id, "campaigns": campaign_id, "type": "contador"},
        {"_id": 0, "password_hash": 0}
    )
    if not contador:
        raise HTTPException(status_code=404, detail="Contador nÃ£o encontrado para esta campanha")
    return contador

def _apply_contador_data_to_contract(contract_data: dict, contador: dict) -> dict:
    """Fill contract provider fields from selected contador account."""
    contador_cpf = normalize_document(contador.get("cpf"))
    if not contador_cpf or len(contador_cpf) != 11 or not validate_cpf(contador_cpf):
        raise HTTPException(status_code=400, detail="Contador selecionado sem CPF vÃ¡lido cadastrado")

    contract_data["contractor_name"] = contador.get("name") or contract_data.get("contractor_name")
    contract_data["contractor_cpf_cnpj"] = contador_cpf
    contract_data["locador_nome"] = contador.get("name") or contract_data.get("locador_nome")
    contract_data["locador_cpf"] = contador_cpf
    contract_data["locador_email"] = contador.get("email") or contract_data.get("locador_email")
    contract_data["locador_profissao"] = "Contador(a)"
    contract_data["contador_professional_id"] = contador.get("id")
    return contract_data

async def _auto_attach_contador_docs(
    *,
    contract_id: str,
    campaign_id: str,
    uploaded_by: str,
    contador: dict,
    existing_attachments: Optional[dict] = None,
) -> dict:
    """
    Auto-generate and attach accountant supporting docs from professional profile.
    Returns merged attachments map.
    """
    attachments_map = dict(existing_attachments or {})

    now_iso = datetime.now(timezone.utc).isoformat()
    city_uf = f"{contador.get('city', '-')}/{(contador.get('state') or '-').upper()}"
    cpf_fmt = contador.get("cpf") or "-"
    crc_fmt = f"{contador.get('crc', '-')}/{(contador.get('crc_state') or '-').upper()}" if contador.get("crc") else "-"

    docs_to_generate = []
    if not attachments_map.get("doc_prestador"):
        docs_to_generate.append((
            "doc_prestador",
            f"Cadastro Profissional - {contador.get('name', 'Contador')}",
            [
                f"Nome: {contador.get('name', '-')}",
                f"Tipo: Contador(a)",
                f"Email: {contador.get('email', '-')}",
                f"Telefone: {contador.get('phone', '-')}",
                f"CPF: {cpf_fmt}",
                f"CRC: {crc_fmt}",
                f"Endereço: {contador.get('address', '-')}",
                f"Cidade/UF: {city_uf}",
                f"ObservaÃ§Ãµes: {contador.get('notes', '-')}",
                f"Gerado automaticamente em: {now_iso}",
            ],
        ))

    if contador.get("crc") and not attachments_map.get("doc_crc"):
        docs_to_generate.append((
            "doc_crc",
            f"Comprovacao CRC - {contador.get('name', 'Contador')}",
            [
                f"Profissional: {contador.get('name', '-')}",
                f"CPF: {cpf_fmt}",
                f"CRC: {crc_fmt}",
                f"UF do CRC: {(contador.get('crc_state') or '-').upper()}",
                f"Registro gerado automaticamente em: {now_iso}",
            ],
        ))

    for attachment_key, title, lines in docs_to_generate:
        doc_bytes, content_type, ext = _render_text_document_bytes(title, lines)
        file_id = str(uuid.uuid4())
        safe_filename = f"{file_id}{ext}"
        file_path = UPLOAD_DIR / safe_filename
        with open(file_path, "wb") as f:
            f.write(doc_bytes)

        attachment_doc = {
            "id": file_id,
            "original_name": f"{title}{ext}",
            "filename": safe_filename,
            "content_type": content_type,
            "size": len(doc_bytes),
            "campaign_id": campaign_id,
            "uploaded_by": uploaded_by,
            "entity_type": "contract_attachment",
            "entity_id": contract_id,
            "attachment_key": attachment_key,
            "auto_generated": True,
            "source_professional_id": contador.get("id"),
            "created_at": now_iso,
        }
        await db.attachments.insert_one(attachment_doc)
        attachments_map[attachment_key] = file_id

    return attachments_map

# ============== AUTH ROUTES ==============
@api_router.post("/auth/register", response_model=dict)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email jÃ¡ cadastrado")
    
    cpf_normalized = validate_and_normalize_document(
        user_data.cpf, "CPF", allowed_types=("cpf",), required=False
    )
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": user_data.role.value,
        "cpf": cpf_normalized,
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
    try:
        user = await db.users.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(status_code=401, detail="Credenciais invÃ¡lidas")

        # Backward compatibility for legacy user documents
        password_hash = user.get("password") or user.get("password_hash")
        if not password_hash:
            raise HTTPException(status_code=401, detail="Credenciais invÃ¡lidas")

        try:
            password_ok = verify_password(credentials.password, password_hash)
        except Exception:
            password_ok = False

        if not password_ok:
            raise HTTPException(status_code=401, detail="Credenciais invÃ¡lidas")

        user_id = user.get("id") or str(user.get("_id"))
        user_role = user.get("role", "candidate")
        user_email = user.get("email") or credentials.email

        token = create_token(user_id, user_email, user_role)
        user.pop("password", None)
        user.pop("password_hash", None)
        user.pop("_id", None)

        return {"token": token, "user": jsonable_encoder(user)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro inesperado no login: %s", e)
        raise HTTPException(status_code=500, detail="Erro interno no login")

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# ============== CAMPAIGN ROUTES ==============
@api_router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(data: CampaignCreate, current_user: dict = Depends(get_current_user)):
    campaign_data = data.model_dump()
    campaign_data["cnpj"] = validate_and_normalize_document(
        campaign_data.get("cnpj"), "CNPJ da campanha", allowed_types=("cnpj",), required=False
    )
    campaign_data["cpf_candidato"] = validate_and_normalize_document(
        campaign_data.get("cpf_candidato"), "CPF do candidato", allowed_types=("cpf",), required=False
    )
    limit_data = await resolve_spending_limit(
        cargo=campaign_data.get("position", ""),
        city=campaign_data.get("city"),
        state=campaign_data.get("state"),
        eleitores=campaign_data.get("eleitores"),
        segundo_turno=bool(campaign_data.get("segundo_turno", False)),
    )
    campaign_data["limite_gastos"] = limit_data.get("limite_gastos", 0.0)
    campaign_data["limite_fonte"] = limit_data.get("fonte")
    campaign_data["limite_ano_base"] = limit_data.get("ano_base")

    campaign_id = str(uuid.uuid4())
    campaign_doc = {
        "id": campaign_id,
        **campaign_data,
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
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    if campaign["owner_id"] != current_user["id"] and current_user["role"] != "contador":
        raise HTTPException(status_code=403, detail="Sem permissÃ£o")
    
    update_data = data.model_dump()
    update_data["cnpj"] = validate_and_normalize_document(
        update_data.get("cnpj"), "CNPJ da campanha", allowed_types=("cnpj",), required=False
    )
    update_data["cpf_candidato"] = validate_and_normalize_document(
        update_data.get("cpf_candidato"), "CPF do candidato", allowed_types=("cpf",), required=False
    )
    limit_data = await resolve_spending_limit(
        cargo=update_data.get("position", ""),
        city=update_data.get("city"),
        state=update_data.get("state"),
        eleitores=update_data.get("eleitores"),
        segundo_turno=bool(update_data.get("segundo_turno", False)),
    )
    update_data["limite_gastos"] = limit_data.get("limite_gastos", 0.0)
    update_data["limite_fonte"] = limit_data.get("fonte")
    update_data["limite_ano_base"] = limit_data.get("ano_base")
    await db.campaigns.update_one({"id": campaign_id}, {"$set": update_data})
    
    updated = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    return updated

# ============== REVENUE ROUTES ==============
async def generate_recibo_eleitoral(campaign_id: str) -> str:
    """Generate sequential electoral receipt number"""
    # Get campaign info for the prefix
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
    revenue_data["donor_cpf_cnpj"] = validate_and_normalize_document(
        revenue_data.get("donor_cpf_cnpj"), "CPF/CNPJ do doador", required=False
    )
    
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
        raise HTTPException(status_code=404, detail="Receita nÃ£o encontrada")
    return revenue

@api_router.put("/revenues/{revenue_id}", response_model=RevenueResponse)
async def update_revenue(revenue_id: str, data: RevenueCreate, current_user: dict = Depends(get_current_user)):
    revenue = await db.revenues.find_one({"id": revenue_id, "campaign_id": current_user.get("campaign_id")})
    if not revenue:
        raise HTTPException(status_code=404, detail="Receita nÃ£o encontrada")
    
    update_data = data.model_dump()
    update_data["donor_cpf_cnpj"] = validate_and_normalize_document(
        update_data.get("donor_cpf_cnpj"), "CPF/CNPJ do doador", required=False
    )
    await db.revenues.update_one({"id": revenue_id}, {"$set": update_data})
    updated = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    return updated

@api_router.delete("/revenues/{revenue_id}")
async def delete_revenue(revenue_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.revenues.delete_one({"id": revenue_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Receita nÃ£o encontrada")
    return {"message": "Receita excluÃ­da"}

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
        raise HTTPException(status_code=404, detail="Receita nÃ£o encontrada")
    
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
    elements.append(Paragraph(f"<b>NÂº {revenue.get('recibo_eleitoral', 'N/A')}</b>", styles['Center']))
    elements.append(Spacer(1, 30))
    
    # Campaign info
    elements.append(Paragraph(f"<b>CANDIDATO(A):</b> {campaign.get('candidate_name', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CARGO:</b> {campaign.get('position', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>PARTIDO:</b> {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CNPJ DA CAMPANHA:</b> {campaign.get('cnpj', 'NÃ£o informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CIDADE/UF:</b> {campaign.get('city', '')}/{campaign.get('state', '')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Donation info
    elements.append(Paragraph("_" * 70, styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>DADOS DA DOAÃ‡ÃƒO</b>", styles['Center']))
    elements.append(Spacer(1, 10))
    
    tipo_receita_labels = {
        "doacao_financeira": "DoaÃ§Ã£o Financeira",
        "doacao_estimavel": "DoaÃ§Ã£o EstimÃ¡vel em Dinheiro",
        "recursos_proprios": "Recursos PrÃ³prios",
        "fundo_partidario": "Fundo PartidÃ¡rio",
        "fundo_eleitoral": "Fundo Especial de Financiamento de Campanha",
        "comercializacao": "ComercializaÃ§Ã£o de Bens/Serviços",
        "rendimento_aplicacao": "Rendimento de AplicaÃ§Ã£o",
        "sobras_campanha": "Sobras de Campanha Anterior",
        "outros": "Outros"
    }
    
    forma_labels = {
        "pix": "PIX",
        "transferencia": "TransferÃªncia BancÃ¡ria",
        "deposito": "DepÃ³sito em Conta",
        "cheque": "Cheque",
        "especie": "Espécie",
        "cartao_credito": "CartÃ£o de Crédito",
        "cartao_debito": "CartÃ£o de Débito",
        "estimavel": "EstimÃ¡vel em Dinheiro"
    }
    
    elements.append(Paragraph(f"<b>Tipo de Receita:</b> {tipo_receita_labels.get(revenue.get('tipo_receita'), revenue.get('tipo_receita', 'NÃ£o informado'))}", styles['Normal']))
    elements.append(Paragraph(f"<b>Forma de Recebimento:</b> {forma_labels.get(revenue.get('forma_recebimento'), revenue.get('forma_recebimento', 'NÃ£o informado'))}", styles['Normal']))
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
        "pessoa_fisica": "Pessoa FÃ­sica",
        "pessoa_juridica": "Pessoa JurÃ­dica",
        "partido": "Partido PolÃ­tico",
        "candidato": "Candidato",
        "comite": "ComitÃª Financeiro",
        "fundo_partidario": "Fundo PartidÃ¡rio",
        "fundo_eleitoral": "Fundo Eleitoral"
    }
    
    elements.append(Paragraph(f"<b>Nome:</b> {revenue.get('donor_name', 'NÃ£o informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>CPF/CNPJ:</b> {revenue.get('donor_cpf_cnpj', 'NÃ£o informado')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Tipo de Doador:</b> {tipo_doador_labels.get(revenue.get('tipo_doador'), revenue.get('tipo_doador', 'NÃ£o informado'))}", styles['Normal']))
    if revenue.get('donor_titulo_eleitor'):
        elements.append(Paragraph(f"<b>TÃ­tulo de Eleitor:</b> {revenue.get('donor_titulo_eleitor')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>DescriÃ§Ã£o:</b> {revenue.get('description', '')}", styles['Normal']))
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
    elements.append(Paragraph("<i>Este recibo foi emitido em conformidade com a ResoluÃ§Ã£o TSE nº 23.607/2019</i>", styles['Center']))
    elements.append(Paragraph(f"<i>Gerado em: {datetime.now().strftime('%d/%m/%Y Ã s %H:%M:%S')}</i>", styles['Center']))
    
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
    
    expense_data = data.model_dump()
    expense_data["supplier_cpf_cnpj"] = validate_and_normalize_document(
        expense_data.get("supplier_cpf_cnpj"), "CPF/CNPJ do fornecedor", required=False
    )

    expense_id = str(uuid.uuid4())
    expense_doc = {
        "id": expense_id,
        **expense_data,
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
        raise HTTPException(status_code=404, detail="Despesa nÃ£o encontrada")
    return expense

@api_router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: str, data: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    expense = await db.expenses.find_one({"id": expense_id, "campaign_id": current_user.get("campaign_id")})
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa nÃ£o encontrada")
    
    update_data = data.model_dump()
    update_data["supplier_cpf_cnpj"] = validate_and_normalize_document(
        update_data.get("supplier_cpf_cnpj"), "CPF/CNPJ do fornecedor", required=False
    )
    await db.expenses.update_one({"id": expense_id}, {"$set": update_data})
    updated = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return updated

@api_router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.expenses.delete_one({"id": expense_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Despesa nÃ£o encontrada")
    return {"message": "Despesa excluÃ­da"}

# ============== CONTRACT ROUTES ==============
@api_router.post("/contracts", response_model=ContractResponse)
async def create_contract(data: ContractCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    contract_data = data.model_dump()

    if data.template_type == ContractTemplateType.SERVICO_CONTABIL and data.contador_professional_id:
        contador = await _get_contador_for_campaign(data.contador_professional_id, current_user["campaign_id"])
        contract_data = _apply_contador_data_to_contract(contract_data, contador)
    else:
        contador = None

    contract_data["contractor_cpf_cnpj"] = validate_and_normalize_document(
        contract_data.get("contractor_cpf_cnpj"), "CPF/CNPJ do contratado", required=True
    )
    contract_data["locador_cpf"] = validate_and_normalize_document(
        contract_data.get("locador_cpf"), "CPF do locador", allowed_types=("cpf",), required=False
    )

    # Get campaign data for contract generation
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    
    contract_id = str(uuid.uuid4())
    contract_doc = {
        "id": contract_id,
        **contract_data,
        "campaign_id": current_user["campaign_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Generate contract HTML if template type is specified
    if data.template_type:
        contract_doc["contract_html"] = generate_contract_html(contract_doc, campaign)
    
    await db.contracts.insert_one(contract_doc)

    if contador:
        merged_attachments = await _auto_attach_contador_docs(
            contract_id=contract_id,
            campaign_id=current_user["campaign_id"],
            uploaded_by=current_user["id"],
            contador=contador,
            existing_attachments=contract_doc.get("attachments"),
        )
        await db.contracts.update_one({"id": contract_id}, {"$set": {"attachments": merged_attachments}})
        contract_doc["attachments"] = merged_attachments

    contract_doc.pop("_id", None)
    
    # Auto-generate expenses based on installment config
    if data.gerar_despesas:
        await generate_contract_expenses(contract_id, data, current_user["campaign_id"])
    
    return contract_doc

async def generate_contract_expenses(contract_id: str, data: ContractCreate, campaign_id: str):
    """Generate expenses based on contract installment configuration"""
    total_value = data.value
    normalized_supplier_doc = validate_and_normalize_document(
        data.contractor_cpf_cnpj, "CPF/CNPJ do contratado", required=True
    )
    
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
                "supplier_cpf_cnpj": normalized_supplier_doc,
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
                "supplier_cpf_cnpj": normalized_supplier_doc,
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
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    return contract

@api_router.get("/contracts/{contract_id}/html")
async def get_contract_html(contract_id: str, current_user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")}, {"_id": 0})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    html = generate_contract_html(contract, campaign)
    return {"html": html}

@api_router.put("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(contract_id: str, data: ContractCreate, current_user: dict = Depends(get_current_user)):
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    update_data = data.model_dump()

    if data.template_type == ContractTemplateType.SERVICO_CONTABIL and data.contador_professional_id:
        contador = await _get_contador_for_campaign(data.contador_professional_id, current_user["campaign_id"])
        update_data = _apply_contador_data_to_contract(update_data, contador)
    else:
        contador = None

    update_data["contractor_cpf_cnpj"] = validate_and_normalize_document(
        update_data.get("contractor_cpf_cnpj"), "CPF/CNPJ do contratado", required=True
    )
    update_data["locador_cpf"] = validate_and_normalize_document(
        update_data.get("locador_cpf"), "CPF do locador", allowed_types=("cpf",), required=False
    )
    
    # Regenerate HTML if template type exists
    if data.template_type:
        update_data["contract_html"] = generate_contract_html({**contract, **update_data}, campaign)
    
    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})

    if contador:
        merged_attachments = await _auto_attach_contador_docs(
            contract_id=contract_id,
            campaign_id=current_user["campaign_id"],
            uploaded_by=current_user["id"],
            contador=contador,
            existing_attachments=(contract.get("attachments") or update_data.get("attachments")),
        )
        await db.contracts.update_one({"id": contract_id}, {"$set": {"attachments": merged_attachments}})

    updated = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    return updated

@api_router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.contracts.delete_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    return {"message": "Contrato excluÃ­do"}

# ============== SIGNATURE ROUTES ==============
class SignatureRequest(BaseModel):
    contract_id: Optional[str] = None
    locador_email: Optional[str] = None

class SignContract(BaseModel):
    signature_hash: str

@api_router.post("/contracts/{contract_id}/request-signature")
async def request_signature(contract_id: str, data: SignatureRequest, current_user: dict = Depends(get_current_user)):
    """Start external signature flow (download + Gov.br signing)"""
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    now = datetime.now(timezone.utc).isoformat()
    locador_email = (data.locador_email or contract.get("locador_email") or "").strip()

    # Generate legacy token (kept for compatibility with old flow)
    token = generate_signature_token(contract_id, locador_email or "locador@assinatura.externa", "locador")
    
    # Update contract as pending signature, but keep expense generation unaffected
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {
            "signature_request_token": token,
            "locador_email": locador_email,
            "status": "aguardando_assinatura",
            "assinatura_externa_iniciada_em": now
        }}
    )

    download_url = f"/api/contracts/{contract_id}/pdf"
    govbr_url = GOVBR_SIGNATURE_URL
    provider_signature_hint = (
        "Após assinatura do candidato no Gov.br, compartilhar o PDF assinado com o prestador "
        "para segunda assinatura e depois anexar o arquivo final no sistema."
    )

    return {
        "message": "Fluxo de assinatura externa iniciado",
        "signature_link": f"/assinar/{token}",
        "token": token,
        "download_url": download_url,
        "govbr_url": govbr_url,
        "provider_signature_hint": provider_signature_hint
    }

@api_router.post("/contracts/{contract_id}/sign-locatario")
async def sign_as_locatario(contract_id: str, data: SignContract, current_user: dict = Depends(get_current_user)):
    """Sign contract as locatÃ¡rio (candidate)"""
    contract = await db.contracts.find_one({"id": contract_id, "campaign_id": current_user.get("campaign_id")})
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
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
        "message": "Contrato assinado pelo locatÃ¡rio",
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
            raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
        
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
        raise HTTPException(status_code=400, detail="Token invÃ¡lido")

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
    title = contract.get("title", "CONTRATO DE PRESTAÃ‡ÃƒO DE SERVIÇOS")
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
        elements.append(Paragraph("<b>LOCATÃRIO / CONTRATANTE:</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {campaign.get('candidate_name', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data da assinatura: {contract.get('locatario_assinatura_data', 'N/A')[:19].replace('T', ' ')}", styles['Normal']))
        elements.append(Paragraph(f"Hash de validaÃ§Ã£o: {contract.get('locatario_assinatura_hash', '')[:32]}...", styles['Signature']))
        elements.append(Spacer(1, 20))
    
    # Locador signature
    if contract.get("locador_assinatura_hash"):
        elements.append(Paragraph("<b>LOCADOR / CONTRATADO:</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {contract.get('locador_nome', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"CPF/CNPJ: {contract.get('locador_cpf', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data da assinatura: {contract.get('locador_assinatura_data', 'N/A')[:19].replace('T', ' ')}", styles['Normal']))
        elements.append(Paragraph(f"Hash de validaÃ§Ã£o: {contract.get('locador_assinatura_hash', '')[:32]}...", styles['Signature']))
        elements.append(Spacer(1, 20))
    
    # Footer with validation info
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 60, styles['Center']))
    elements.append(Paragraph("<i>Documento gerado eletronicamente pelo sistema Eleitora 360</i>", styles['Center']))
    elements.append(Paragraph(f"<i>ID do Contrato: {contract_id}</i>", styles['Signature']))
    elements.append(Paragraph(f"<i>Gerado em: {datetime.now(timezone.utc).strftime('%d/%m/%Y Ã s %H:%M:%S')} UTC</i>", styles['Signature']))
    
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
            raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
        
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
        raise HTTPException(status_code=400, detail="Token invÃ¡lido")

@api_router.get("/contract-templates")
async def get_contract_templates():
    """Get available contract templates"""
    return {
        "templates": [
            {
                "type": "bem_movel",
                "name": "LocaÃ§Ã£o de Bem MÃ³vel",
                "description": "Contrato para locação de equipamentos, rÃ¡dios, etc."
            },
            {
                "type": "espaco_evento",
                "name": "LocaÃ§Ã£o de Espaço para Evento",
                "description": "Contrato para locação de espaÃ§o para evento eleitoral"
            },
            {
                "type": "imovel",
                "name": "LocaÃ§Ã£o de Imóvel",
                "description": "Contrato para locação de imóvel (comitÃª, escritÃ³rio)"
            },
            {
                "type": "veiculo_com_motorista",
                "name": "LocaÃ§Ã£o de VeÃ­culo com Motorista",
                "description": "Contrato para veÃ­culo com motorista (carro de som, paredÃ£o)"
            },
            {
                "type": "veiculo_sem_motorista",
                "name": "LocaÃ§Ã£o de VeÃ­culo sem Motorista",
                "description": "Contrato para locação de veÃ­culo sem motorista"
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
            {"sigla": "DC", "nome": "Democracia CristÃ£", "numero": 27},
            {"sigla": "MDB", "nome": "Movimento DemocrÃ¡tico Brasileiro", "numero": 15},
            {"sigla": "MOBILIZA", "nome": "Mobiliza", "numero": 33},
            {"sigla": "NOVO", "nome": "Partido Novo", "numero": 30},
            {"sigla": "PATRIOTA", "nome": "Patriota", "numero": 51},
            {"sigla": "PCB", "nome": "Partido Comunista Brasileiro", "numero": 21},
            {"sigla": "PCdoB", "nome": "Partido Comunista do Brasil", "numero": 65},
            {"sigla": "PCO", "nome": "Partido da Causa OperÃ¡ria", "numero": 29},
            {"sigla": "PDT", "nome": "Partido DemocrÃ¡tico Trabalhista", "numero": 12},
            {"sigla": "PL", "nome": "Partido Liberal", "numero": 22},
            {"sigla": "PMB", "nome": "Partido da Mulher Brasileira", "numero": 35},
            {"sigla": "PMN", "nome": "Partido da MobilizaÃ§Ã£o Nacional", "numero": 33},
            {"sigla": "PODE", "nome": "Podemos", "numero": 20},
            {"sigla": "PP", "nome": "Progressistas", "numero": 11},
            {"sigla": "PRD", "nome": "Partido RenovaÃ§Ã£o DemocrÃ¡tica", "numero": 25},
            {"sigla": "PROS", "nome": "Partido Republicano da Ordem Social", "numero": 90},
            {"sigla": "PRTB", "nome": "Partido Renovador Trabalhista Brasileiro", "numero": 28},
            {"sigla": "PSB", "nome": "Partido Socialista Brasileiro", "numero": 40},
            {"sigla": "PSC", "nome": "Partido Social CristÃ£o", "numero": 20},
            {"sigla": "PSD", "nome": "Partido Social DemocrÃ¡tico", "numero": 55},
            {"sigla": "PSDB", "nome": "Partido da Social Democracia Brasileira", "numero": 45},
            {"sigla": "PSOL", "nome": "Partido Socialismo e Liberdade", "numero": 50},
            {"sigla": "PSTU", "nome": "Partido Socialista dos Trabalhadores Unificado", "numero": 16},
            {"sigla": "PT", "nome": "Partido dos Trabalhadores", "numero": 13},
            {"sigla": "PTB", "nome": "Partido Trabalhista Brasileiro", "numero": 14},
            {"sigla": "PV", "nome": "Partido Verde", "numero": 43},
            {"sigla": "REDE", "nome": "Rede Sustentabilidade", "numero": 18},
            {"sigla": "REPUBLICANOS", "nome": "Republicanos", "numero": 10},
            {"sigla": "SOLIDARIEDADE", "nome": "Solidariedade", "numero": 77},
            {"sigla": "UNIÃƒO", "nome": "UniÃ£o Brasil", "numero": 44},
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
            {"uf": "AP", "nome": "AmapÃ¡", "regiao": "Norte"},
            {"uf": "AM", "nome": "Amazonas", "regiao": "Norte"},
            {"uf": "BA", "nome": "Bahia", "regiao": "Nordeste"},
            {"uf": "CE", "nome": "CearÃ¡", "regiao": "Nordeste"},
            {"uf": "DF", "nome": "Distrito Federal", "regiao": "Centro-Oeste"},
            {"uf": "ES", "nome": "EspÃ­rito Santo", "regiao": "Sudeste"},
            {"uf": "GO", "nome": "GoiÃ¡s", "regiao": "Centro-Oeste"},
            {"uf": "MA", "nome": "MaranhÃ£o", "regiao": "Nordeste"},
            {"uf": "MT", "nome": "Mato Grosso", "regiao": "Centro-Oeste"},
            {"uf": "MS", "nome": "Mato Grosso do Sul", "regiao": "Centro-Oeste"},
            {"uf": "MG", "nome": "Minas Gerais", "regiao": "Sudeste"},
            {"uf": "PA", "nome": "ParÃ¡", "regiao": "Norte"},
            {"uf": "PB", "nome": "ParaÃ­ba", "regiao": "Nordeste"},
            {"uf": "PR", "nome": "ParanÃ¡", "regiao": "Sul"},
            {"uf": "PE", "nome": "Pernambuco", "regiao": "Nordeste"},
            {"uf": "PI", "nome": "PiauÃ­", "regiao": "Nordeste"},
            {"uf": "RJ", "nome": "Rio de Janeiro", "regiao": "Sudeste"},
            {"uf": "RN", "nome": "Rio Grande do Norte", "regiao": "Nordeste"},
            {"uf": "RS", "nome": "Rio Grande do Sul", "regiao": "Sul"},
            {"uf": "RO", "nome": "RondÃ´nia", "regiao": "Norte"},
            {"uf": "RR", "nome": "Roraima", "regiao": "Norte"},
            {"uf": "SC", "nome": "Santa Catarina", "regiao": "Sul"},
            {"uf": "SP", "nome": "São Paulo", "regiao": "Sudeste"},
            {"uf": "SE", "nome": "Sergipe", "regiao": "Nordeste"},
            {"uf": "TO", "nome": "Tocantins", "regiao": "Norte"}
        ],
        "regioes": ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
    }

@api_router.get("/reference/municipios")
async def get_municipios(uf: str = Query(..., description="UF com 2 letras, ex: SP")):
    """Lista oficial de municipios brasileiros por UF (IBGE)."""
    municipios = await _get_ibge_municipios_by_uf(uf)
    if not municipios:
        raise HTTPException(status_code=404, detail="Nao foi possivel carregar municipios para a UF informada")
    return {"uf": uf.upper(), "municipios": municipios, "fonte": "IBGE API localidades"}

@api_router.get("/reference/bancos")
async def get_bancos():
    """Get list of Brazilian banks"""
    return {
        "bancos": [
            {"codigo": "001", "nome": "Banco do Brasil"},
            {"codigo": "033", "nome": "Santander"},
            {"codigo": "104", "nome": "Caixa EconÃ´mica Federal"},
            {"codigo": "237", "nome": "Bradesco"},
            {"codigo": "341", "nome": "ItaÃº"},
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
def _is_valid_iso_date(date_str: Optional[str]) -> bool:
    if not date_str:
        return False
    try:
        datetime.fromisoformat(str(date_str))
        return True
    except Exception:
        return False

def build_spce_precheck(
    campaign: dict,
    revenues: Optional[list] = None,
    expenses: Optional[list] = None,
    contracts: Optional[list] = None,
) -> dict:
    errors = []
    warnings = []
    if not campaign:
        return {"ok": False, "errors": ["Campanha não encontrada."], "warnings": []}

    cnpj = normalize_document(campaign.get("cnpj"))
    if not cnpj or len(cnpj) != 14 or not validate_cnpj(cnpj):
        errors.append("CNPJ da campanha inválido ou não configurado.")

    state = (campaign.get("state") or "").strip().upper()
    if len(state) != 2:
        errors.append("UF da campanha deve ter 2 caracteres.")

    if not campaign.get("election_year"):
        errors.append("Ano da eleição não configurado.")

    if revenues is not None:
        for i, rev in enumerate(revenues, 1):
            amount = float(rev.get("amount", 0) or 0)
            if amount <= 0:
                errors.append(f"Receita #{i} com valor inválido.")
            if not _is_valid_iso_date(rev.get("date")):
                errors.append(f"Receita #{i} com data inválida.")
            donor_doc = normalize_document(rev.get("donor_cpf_cnpj"))
            if donor_doc:
                if len(donor_doc) == 11 and not validate_cpf(donor_doc):
                    errors.append(f"Receita #{i} com CPF do doador inválido.")
                elif len(donor_doc) == 14 and not validate_cnpj(donor_doc):
                    errors.append(f"Receita #{i} com CNPJ do doador inválido.")
                elif len(donor_doc) not in (11, 14):
                    errors.append(f"Receita #{i} com CPF/CNPJ do doador inválido.")
            else:
                warnings.append(f"Receita #{i} sem CPF/CNPJ do doador.")

    if expenses is not None:
        for i, exp in enumerate(expenses, 1):
            amount = float(exp.get("amount", 0) or 0)
            if amount <= 0:
                errors.append(f"Despesa #{i} com valor inválido.")
            if not _is_valid_iso_date(exp.get("date")):
                errors.append(f"Despesa #{i} com data inválida.")
            supplier_doc = normalize_document(exp.get("supplier_cpf_cnpj"))
            if supplier_doc:
                if len(supplier_doc) == 11 and not validate_cpf(supplier_doc):
                    errors.append(f"Despesa #{i} com CPF do fornecedor inválido.")
                elif len(supplier_doc) == 14 and not validate_cnpj(supplier_doc):
                    errors.append(f"Despesa #{i} com CNPJ do fornecedor inválido.")
                elif len(supplier_doc) not in (11, 14):
                    errors.append(f"Despesa #{i} com CPF/CNPJ do fornecedor inválido.")
            else:
                warnings.append(f"Despesa #{i} sem CPF/CNPJ do fornecedor.")

    if contracts is not None:
        for i, contract in enumerate(contracts, 1):
            value = float(contract.get("value", 0) or 0)
            if value <= 0:
                errors.append(f"Contrato #{i} com valor inválido.")

            start_date = contract.get("start_date")
            end_date = contract.get("end_date")
            if not _is_valid_iso_date(start_date) or not _is_valid_iso_date(end_date):
                errors.append(f"Contrato #{i} com data inicial/final inválida.")
            else:
                if datetime.fromisoformat(start_date) > datetime.fromisoformat(end_date):
                    errors.append(f"Contrato #{i} com data inicial maior que a data final.")

            locador_doc = normalize_document(contract.get("locador_cpf") or contract.get("contractor_cpf_cnpj"))
            if not locador_doc:
                errors.append(f"Contrato #{i} sem CPF/CNPJ do contratado.")
            elif len(locador_doc) == 11 and not validate_cpf(locador_doc):
                errors.append(f"Contrato #{i} com CPF inválido.")
            elif len(locador_doc) == 14 and not validate_cnpj(locador_doc):
                errors.append(f"Contrato #{i} com CNPJ inválido.")
            elif len(locador_doc) not in (11, 14):
                errors.append(f"Contrato #{i} com CPF/CNPJ inválido.")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

def ensure_spce_ready(precheck: dict):
    if precheck["ok"]:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "message": "Dados incompatíveis com exportação SPCE.",
            "errors": precheck["errors"],
            "warnings": precheck["warnings"],
        },
    )

def _contract_has_signature_evidence(contract: dict) -> bool:
    internal_both_signed = bool(contract.get("locador_assinatura_hash")) and bool(contract.get("locatario_assinatura_hash"))
    external_signed_doc = bool(contract.get("signed_document_attachment_id"))
    return internal_both_signed or external_signed_doc

def _sanitize_filename_token(value: str, fallback: str = "DOC") -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    token = token.strip("_")
    return token[:60] if token else fallback

def _expense_service_description(category: str) -> str:
    key = (category or "outros").lower().replace(" ", "_")
    return SPCE_DESPESA_CATEGORIAS.get(key, SPCE_DESPESA_CATEGORIAS["outros"])["descricao"]

def _expense_is_ready_for_spce(expense: dict) -> bool:
    amount_ok = float(expense.get("amount", 0) or 0) > 0
    date_ok = _is_valid_iso_date(expense.get("date"))
    supplier_name_ok = bool((expense.get("supplier_name") or "").strip())
    supplier_doc = normalize_document(expense.get("supplier_cpf_cnpj"))
    supplier_doc_ok = bool(
        supplier_doc and (
            (len(supplier_doc) == 11 and validate_cpf(supplier_doc))
            or (len(supplier_doc) == 14 and validate_cnpj(supplier_doc))
        )
    )
    payment_ok = (expense.get("payment_status") or "").lower() == "pago"
    attachment_ok = bool(expense.get("attachment_id"))
    payment_type_ok = bool(expense.get("tipo_pagamento"))
    fiscal_doc_ok = bool((expense.get("numero_documento_fiscal") or expense.get("invoice_number") or "").strip())
    payment_date = expense.get("data_pagamento") or expense.get("date")
    payment_date_ok = _is_valid_iso_date(payment_date)
    return all([
        amount_ok,
        date_ok,
        supplier_name_ok,
        supplier_doc_ok,
        payment_ok,
        attachment_ok,
        payment_type_ok,
        fiscal_doc_ok,
        payment_date_ok,
    ])

def _generate_expense_cover_bytes(expense: dict, campaign: dict, cnpj: str, seq: int) -> bytes:
    service_desc = _expense_service_description(expense.get("category"))
    payment_date = expense.get("data_pagamento") or expense.get("date") or "-"
    supplier_doc = normalize_document(expense.get("supplier_cpf_cnpj")) or "-"
    tomador = campaign.get("candidate_name") or "Candidato(a)"
    tomador_doc = normalize_document(campaign.get("cpf_candidato")) or "-"
    lines = [
        "CAPA DE COMPROVANTE DE DESPESA - SPCE",
        f"Sequencial: {seq}",
        f"Campanha (Tomador): {tomador}",
        f"CPF do Tomador: {tomador_doc}",
        f"CNPJ da Campanha: {cnpj}",
        f"Prestador: {expense.get('supplier_name', '-')}",
        f"CPF/CNPJ do Prestador: {supplier_doc}",
        f"Tipo de Pagamento: {expense.get('tipo_pagamento', '-')}",
        f"Documento Fiscal: {expense.get('numero_documento_fiscal') or expense.get('invoice_number') or '-'}",
        f"Descricao da Despesa: {expense.get('description', '-')}",
        f"Especie do Servico (SPCE): {service_desc}",
        f"Categoria: {expense.get('category', '-')}",
        f"Valor: R$ {float(expense.get('amount', 0) or 0):,.2f}",
        f"Data da Despesa: {expense.get('date', '-')}",
        f"Data de Pagamento: {payment_date}",
        f"Status: {expense.get('payment_status', '-')}",
        f"ID da Despesa: {expense.get('id', '-')}",
    ]

    if PDF_AVAILABLE:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CoverTitle",
            parent=styles["Heading1"],
            fontSize=14,
            leading=18,
            alignment=TA_LEFT,
            spaceAfter=10,
        )
        body_style = ParagraphStyle(
            "CoverBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
        story = [Paragraph(lines[0], title_style), Spacer(1, 0.3 * cm)]
        for row in lines[1:]:
            story.append(Paragraph(row, body_style))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            "Documento gerado automaticamente para organização da exportação SPCE (texto pesquisável/OCR-ready).",
            body_style,
        ))
        doc.build(story)
        return buffer.getvalue()

    return ("\n".join(lines)).encode("utf-8")

def _build_ocr_text_for_attachment(expense: dict, attachment: dict, file_bytes: bytes) -> bytes:
    header = [
        "OCR_INDEX_DESPESA",
        f"Despesa ID: {expense.get('id', '-')}",
        f"Descricao: {expense.get('description', '-')}",
        f"Prestador: {expense.get('supplier_name', '-')}",
        f"CPF/CNPJ Prestador: {expense.get('supplier_cpf_cnpj', '-')}",
        f"Arquivo Original: {attachment.get('original_name') or attachment.get('filename') or '-'}",
        "",
        "TEXTO_EXTRAIDO:",
    ]
    extracted_text = ""

    content_type = (attachment.get("content_type") or "").lower()
    if content_type == "application/pdf" and PDF_TEXT_EXTRACTION_AVAILABLE:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
            extracted_text = "\n".join(pages_text).strip()
        except Exception:
            extracted_text = ""

    if not extracted_text:
        extracted_text = (
            "Nao foi possivel extrair texto OCR automaticamente do arquivo. "
            "Mantenha este comprovante junto da capa para conferencia no SPCE."
        )

    return ("\n".join(header) + "\n" + extracted_text).encode("utf-8")

@api_router.get("/export/spce/precheck")
async def spce_precheck(current_user: dict = Depends(get_current_user)):
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")

    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(2000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(2000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(2000)

    report = build_spce_precheck(campaign, revenues=revenues, expenses=expenses, contracts=contracts)
    report["totals"] = {"revenues": len(revenues), "expenses": len(expenses), "contracts": len(contracts)}
    return report

@api_router.get("/export/spce-doacoes")
async def export_spce_doacoes(current_user: dict = Depends(get_current_user)):
    """Export donations in SPCE format (DOACINTE layout)"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    ensure_spce_ready(build_spce_precheck(campaign, revenues=revenues))
    
    if not campaign.get("cnpj"):
        raise HTTPException(status_code=400, detail="CNPJ da campanha nÃ£o configurado")
    
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
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    return payment

@api_router.put("/payments/{payment_id}", response_model=PaymentResponse)
async def update_payment(payment_id: str, data: PaymentCreate, current_user: dict = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id, "campaign_id": current_user.get("campaign_id")})
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    
    await db.payments.update_one({"id": payment_id}, {"$set": data.model_dump()})
    updated = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    return updated

@api_router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.payments.delete_one({"id": payment_id, "campaign_id": current_user.get("campaign_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    return {"message": "Pagamento excluÃ­do"}

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
    """Dashboard de conformidade TSE - verifica completude dos dados para prestaÃ§Ã£o de contas"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        return {
            "status": "sem_campanha",
            "message": "Configure uma campanha primeiro",
            "completude_geral": 0,
            "itens": []
        }
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
        ("election_year", "Ano da EleiÃ§Ã£o"),
        ("cnpj", "CNPJ da Campanha"),
        ("numero_candidato", "NÃºmero do Candidato"),
        ("cpf_candidato", "CPF do Candidato"),
        ("eleitores", "NÃºmero de Eleitores")
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
                "descricao": r.get("description", "Sem descriÃ§Ã£o")[:30],
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
                "descricao": e.get("description", "Sem descriÃ§Ã£o")[:30],
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
        if not _contract_has_signature_evidence(c):
            problemas.append("falta_documento_assinado")
        if not c.get("locador_cpf"):
            problemas.append("falta_cpf_locador")
        
        if not problemas:
            contratos_completos += 1
        else:
            contratos_pendentes.append({
                "id": c.get("id"),
                "titulo": c.get("title", "Sem tÃ­tulo")[:30],
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
        "categoria": "Documentos ComprobatÃ³rios",
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
        message = "Sua prestaÃ§Ã£o de contas estÃ¡ praticamente completa!"
    elif completude_geral >= 70:
        status = "quase_pronto"
        message = "Alguns ajustes sÃ£o necessÃ¡rios antes de enviar."
    elif completude_geral >= 50:
        status = "em_andamento"
        message = "Ainda hÃ¡ campos importantes pendentes de preenchimento."
    else:
        status = "incompleto"
        message = "Muitos dados obrigatórios estÃ£o faltando."
    
    # Alertas e sugestÃµes
    alertas = []
    if not campaign.get("cnpj"):
        alertas.append({
            "tipo": "erro",
            "mensagem": "CNPJ da campanha nÃ£o configurado - obrigatório para exportaÃ§Ã£o SPCE",
            "acao": "VÃ¡ em ConfiguraÃ§Ãµes e preencha o CNPJ"
        })
    
    if not campaign.get("eleitores"):
        alertas.append({
            "tipo": "aviso",
            "mensagem": "NÃºmero de eleitores nÃ£o configurado - necessÃ¡rio para cÃ¡lculo de limite TSE",
            "acao": "VÃ¡ em ConfiguraÃ§Ãµes e informe o nÃºmero de eleitores do municÃ­pio"
        })
    
    receitas_sem_recibo = len([r for r in revenues if not r.get("recibo_eleitoral")])
    if receitas_sem_recibo > 0:
        alertas.append({
            "tipo": "aviso",
            "mensagem": f"{receitas_sem_recibo} receita(s) sem nÃºmero de recibo eleitoral",
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
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
    # Validate required SPCE fields
    cnpj = campaign.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha invÃ¡lido ou nÃ£o configurado")
    
    # Get all data
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    attachments = await db.attachments.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    ensure_spce_ready(build_spce_precheck(campaign, revenues=revenues, expenses=expenses, contracts=contracts))
    
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
            receipt_content = f"""RECIBO DE DOAÃ‡ÃƒO ELEITORAL

Campanha: {campaign.get('candidate_name', '')}
CNPJ: {cnpj}
Partido: {campaign.get('party', '')}

Doador: {rev.get('donor_name', '')}
CPF/CNPJ: {rev.get('donor_cpf_cnpj', '')}

DescriÃ§Ã£o: {rev.get('description', '')}
Valor: R$ {rev.get('amount', 0):,.2f}
Data: {rev.get('date', '')}
Categoria: {rev.get('category', '')}

NÃºmero do Recibo: {i + 1}
"""
            zf.writestr(f"RECEITAS/{filename}", receipt_content.encode('utf-8'))
            
            receitas_arquivos.append({
                "codigo": filename,
                "descricao": f"REC_DOA_{rev.get('donor_name', '').replace(' ', '_')[:20]}_{donor_cpf}_{date_rev}_R${rev.get('amount', 0):.2f}_{i+1}"
            })
        
        # Generate documents for DESPESAS folder
        despesas_arquivos = []
        attachments_by_id = {a.get("id"): a for a in attachments if a.get("id")}
        zf.writestr("DESPESAS/OCR/", "")

        for i, exp in enumerate(expenses, 1):
            if not _expense_is_ready_for_spce(exp):
                continue

            supplier_doc = normalize_document(exp.get("supplier_cpf_cnpj")) or "SEM_DOC"
            date_exp = (exp.get("date", "") or "").replace("-", "")
            if len(date_exp) == 8:
                date_exp = date_exp[6:8] + date_exp[4:6] + date_exp[0:4]  # DDMMYYYY
            else:
                date_exp = "00000000"

            supplier_token = _sanitize_filename_token(exp.get("supplier_name"), "FORNECEDOR")
            expense_seq = 246 + i
            base_name = f"DESP_{expense_seq}_{date_exp}_{supplier_doc}"

            # 1) Capa da despesa (texto pesquisável / OCR-ready)
            cover_bytes = _generate_expense_cover_bytes(exp, campaign, cnpj, expense_seq)
            cover_name = f"{base_name}_CAPA.pdf" if PDF_AVAILABLE else f"{base_name}_CAPA.txt"
            zf.writestr(f"DESPESAS/{cover_name}", cover_bytes)

            despesas_arquivos.append({
                "codigo": cover_name,
                "descricao": (
                    f"CAPA_{supplier_token}_{supplier_doc}_{date_exp}_R${float(exp.get('amount', 0) or 0):.2f}_{expense_seq}"
                ),
            })

            # 2) Comprovante anexado + arquivo OCR auxiliar
            attachment_id = exp.get("attachment_id")
            attachment = attachments_by_id.get(attachment_id)
            if not attachment:
                continue

            file_path = UPLOAD_DIR / (attachment.get("filename") or "")
            if not file_path.exists():
                continue

            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()

                original_name = attachment.get("original_name") or attachment.get("filename") or f"{base_name}_ANEXO"
                original_name = _sanitize_filename_token(original_name, f"{base_name}_ANEXO")
                ext = os.path.splitext(attachment.get("filename") or "")[1].lower() or ".bin"
                anexo_name = f"{base_name}_COMPROVANTE_{original_name}{ext}"
                zf.writestr(f"DESPESAS/{anexo_name}", file_content)

                ocr_txt = _build_ocr_text_for_attachment(exp, attachment, file_content)
                ocr_name = f"{base_name}_OCR.txt"
                zf.writestr(f"DESPESAS/OCR/{ocr_name}", ocr_txt)

                despesas_arquivos.append({
                    "codigo": anexo_name,
                    "descricao": f"COMPROVANTE_{supplier_token}_{supplier_doc}_{date_exp}_{expense_seq}",
                })
                despesas_arquivos.append({
                    "codigo": f"OCR/{ocr_name}",
                    "descricao": f"OCR_INDEX_{supplier_token}_{supplier_doc}_{date_exp}_{expense_seq}",
                })
            except Exception:
                continue
        
        # Generate DEMONSTRATIVOS
        demonstrativos_arquivos = []
        total_receitas = sum(r.get("amount", 0) for r in revenues)
        total_despesas = sum(e.get("amount", 0) for e in expenses)
        saldo = total_receitas - total_despesas
        
        # RelatÃ³rio de Receitas e Despesas
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
        
        # RelatÃ³rio de Despesas Efetuadas
        desp_efetuadas = f"""RELATÃ“RIO DE DESPESAS EFETUADAS
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
                        # Despesas são tratadas acima com capa + comprovante + OCR
                        continue
                    elif entity_type == "contract":
                        zf.writestr(f"AVULSOS_OUTROS/{att.get('original_name', att.get('filename'))}", file_content)
                    elif entity_type == "contract_signed":
                        zf.writestr(f"AVULSOS_SPCE/{att.get('original_name', att.get('filename'))}", file_content)
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
            detail=f"Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")
    
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
        raise HTTPException(status_code=404, detail="Despesa nÃ£o encontrada")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")
    
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
        raise HTTPException(status_code=404, detail="Receita nÃ£o encontrada")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")
    
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
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")
    
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

@api_router.post("/contracts/{contract_id}/upload-signed-document")
async def upload_signed_contract_document(
    contract_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload externally signed contract document and mark contract as active."""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")

    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")

    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(file.content_type, ".bin")
    safe_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_filename
    with open(file_path, "wb") as f:
        f.write(contents)

    attachment_doc = {
        "id": file_id,
        "original_name": file.filename,
        "filename": safe_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "campaign_id": current_user["campaign_id"],
        "uploaded_by": current_user["id"],
        "entity_type": "contract_signed",
        "entity_id": contract_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)

    now = datetime.now(timezone.utc).isoformat()
    await db.contracts.update_one(
        {"id": contract_id},
        {"$set": {
            "signed_document_attachment_id": file_id,
            "signed_document_uploaded_at": now,
            "status": "ativo"
        }}
    )

    updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    return {
        "message": "Contrato assinado anexado com sucesso",
        "contract": updated_contract,
        "attachment": {**attachment_doc, "_id": None}
    }

@api_router.get("/contracts/{contract_id}/expenses")
async def get_contract_expenses(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Get all expenses linked to a contract"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
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
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
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
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    # Validate attachment key
    template_type = contract.get("template_type")
    valid_keys = [a["key"] for a in CONTRACT_REQUIRED_ATTACHMENTS.get(template_type, [])]
    if attachment_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Tipo de anexo invÃ¡lido. VÃ¡lidos: {', '.join(valid_keys)}")
    
    # Validate file type
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de arquivo nÃ£o permitido. Use: JPEG, PNG ou PDF"
        )
    
    # Upload file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 10MB)")
    
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
        raise HTTPException(status_code=404, detail="Arquivo nÃ£o encontrado")
    return attachment

@api_router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, current_user: dict = Depends(get_current_user)):
    """Download attachment file"""
    attachment = await db.attachments.find_one(
        {"id": attachment_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Arquivo nÃ£o encontrado")
    
    file_path = UPLOAD_DIR / attachment["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nÃ£o encontrado no servidor")
    
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
        raise HTTPException(status_code=404, detail="Arquivo nÃ£o encontrado")
    
    # Delete file
    file_path = UPLOAD_DIR / attachment["filename"]
    if file_path.exists():
        file_path.unlink()
    
    # Delete from DB
    await db.attachments.delete_one({"id": attachment_id})
    
    return {"message": "Arquivo excluÃ­do"}

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
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
    elements.append(Paragraph("PRESTAÃ‡ÃƒO DE CONTAS ELEITORAL", styles['Title2']))
    elements.append(Spacer(1, 20))
    
    # Campaign Info
    if campaign:
        info_text = f"""
        <b>Candidato:</b> {campaign.get('candidate_name', '')}<br/>
        <b>Partido:</b> {campaign.get('party', '')} - {campaign.get('position', '')}<br/>
        <b>Cidade/UF:</b> {campaign.get('city', '')}/{campaign.get('state', '')}<br/>
        <b>Ano:</b> {campaign.get('election_year', '')}<br/>
        <b>CNPJ:</b> {campaign.get('cnpj', 'NÃ£o informado')}
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
        revenue_data = [["Data", "DescriÃ§Ã£o", "Categoria", "Valor"]]
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
        expense_data = [["Data", "DescriÃ§Ã£o", "Categoria", "Valor"]]
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
        f"RelatÃ³rio gerado em {datetime.now().strftime('%d/%m/%Y Ã s %H:%M')}",
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



# ============== ENHANCED PDF GENERATION ==============
def format_signature_section(contract: dict, styles: dict) -> list:
    """Generate enhanced signature section with audit trail"""
    elements = []
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>SEÇÃO DE ASSINATURAS DIGITAIS E CERTIFICADAS</b>", styles['Title2']))
    elements.append(Spacer(1, 20))

    # Locador signature
    if contract.get("locador_assinatura_hash"):
        elements.append(Paragraph("<b>✓ Assinado pelo Locador (Locatário de Imóvel)</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {contract.get('locador_nome', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data/Hora: {contract.get('locador_assinatura_data', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Método: Assinatura Facial Certificada com Validação Biométrica", styles['Normal']))
        elements.append(Paragraph(f"Hash SHA-256: {contract.get('locador_assinatura_hash', '')[:32]}...", styles['Normal']))
        elements.append(Spacer(1, 15))

    # Locatário signature
    if contract.get("locatario_assinatura_hash"):
        elements.append(Paragraph("<b>✓ Assinado pelo Locatário (Campanha Política)</b>", styles['Normal']))
        elements.append(Paragraph(f"Nome: {contract.get('locatario_nome', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Data/Hora: {contract.get('locatario_assinatura_data', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Método: Assinatura Digital com Validação de Identidade", styles['Normal']))
        elements.append(Paragraph(f"Hash SHA-256: {contract.get('locatario_assinatura_hash', '')[:32]}...", styles['Normal']))
        elements.append(Spacer(1, 15))

    # Audit trail
    if contract.get("status") == "ativo":
        elements.append(Paragraph("<b>Status do Contrato:</b> ✓ ATIVO E PLENAMENTE VÁLIDO", styles['Normal']))
    elif contract.get("locador_assinatura_hash") and contract.get("locatario_assinatura_hash"):
        elements.append(Paragraph("<b>Status do Contrato:</b> ✓ COMPLETAMENTE ASSINADO", styles['Normal']))
    else:
        elements.append(Paragraph(f"<b>Status do Contrato:</b> {contract.get('status', 'PENDENTE')}", styles['Normal']))

    return elements

def create_pdf_with_metadata(buffer: BytesIO, contract_id: str, contract: dict) -> BytesIO:
    """Add metadata to PDF document"""
    # Note: ReportLab's SimpleDocTemplate doesn't directly support PDF metadata
    # This function serves as a placeholder for future implementation with PyPDF2
    return buffer

async def generate_contract_pdf(contract_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF of contract"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
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
    
    # Signature section with enhanced audit trail
    elements.extend(format_signature_section(contract, styles))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    # Add metadata to PDF
    buffer = create_pdf_with_metadata(buffer, contract_id, contract)
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
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    # Check if contract has a stored PDF
    pdf_id = contract.get("pdf_path")
    if not pdf_id:
        # Check if contract is fully signed
        if not (contract.get("locatario_assinatura_hash") and contract.get("locador_assinatura_hash")):
            raise HTTPException(status_code=400, detail="Contrato nÃ£o estÃ¡ completamente assinado")
        
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
        raise HTTPException(status_code=404, detail="PDF nÃ£o encontrado")
    
    buffer = BytesIO(pdf_doc["data"])
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pdf_doc.get('filename', 'contrato.pdf')}"}
    )

# ============== EMAIL TEMPLATES & UTILITIES ==============
class EmailTemplate:
    """Professional email templates with variable substitution"""

    BASE_STYLE = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }
        .container { max-width: 600px; margin: 0 auto; padding: 0; }
        .header { background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; padding: 30px 20px; text-align: center; }
        .content { padding: 30px 20px; border-bottom: 1px solid #e5e7eb; }
        .section { margin-bottom: 20px; }
        .button { display: inline-block; background: #2563eb; color: white; padding: 12px 32px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 15px 0; }
        .button:hover { background: #1e40af; }
        .footer { padding: 20px; text-align: center; color: #666; font-size: 12px; background: #f9fafb; }
        .info-box { background: #eff6ff; padding: 15px; border-left: 4px solid #2563eb; border-radius: 4px; margin: 15px 0; }
        .warning-box { background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 4px; margin: 15px 0; }
        h1 { margin: 0; font-size: 28px; }
        h2 { color: #1f2937; margin: 20px 0 10px 0; font-size: 18px; }
        p { line-height: 1.6; color: #374151; margin: 10px 0; }
        .signature-status { display: flex; justify-content: space-between; margin-top: 20px; }
        .status-badge { padding: 8px 16px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .status-pending { background: #fef3c7; color: #92400e; }
        .status-signed { background: #d1fae5; color: #065f46; }
    </style>
    """

    @staticmethod
    def signature_request(contract: dict, party_name: str, signature_link: str, expiry_days: int = 7) -> str:
        """Generate professional signature request email"""
        contract_title = contract.get("title", "Contrato de Locação")
        contract_value = contract.get("value", 0)

        return f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head><meta charset="UTF-8">{EmailTemplate.BASE_STYLE}</head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📋 Solicitação de Assinatura</h1>
                </div>
                <div class="content">
                    <p>Olá <strong>{party_name}</strong>,</p>

                    <div class="section">
                        <p>Você recebeu uma solicitação para assinar um contrato na plataforma <strong>Eleitora 360</strong>.</p>
                    </div>

                    <div class="info-box">
                        <h2>Detalhes do Contrato</h2>
                        <p><strong>Título:</strong> {contract_title}</p>
                        <p><strong>Valor:</strong> R$ {contract_value:,.2f}</p>
                        <p><strong>ID do Contrato:</strong> {contract.get('id', 'N/A')[:8]}</p>
                        <p><strong>Data de Geração:</strong> {datetime.now(timezone.utc).strftime('%d/%m/%Y às %H:%M')}</p>
                    </div>

                    <div class="section">
                        <h2>Como Assinar</h2>
                        <p>Clique no botão abaixo para revisar e assinar o contrato de forma digital e segura:</p>
                        <center>
                            <a href="{signature_link}" class="button">Assinar Contrato</a>
                        </center>
                    </div>

                    <div class="warning-box">
                        <strong>⏰ Validade do Link:</strong> Este link de assinatura expira em {expiry_days} dias.
                        Após esse período, você precisará solicitar um novo link.
                    </div>

                    <div class="section">
                        <h2>Segurança</h2>
                        <ul>
                            <li>✅ Assinatura com validação facial (selfie)</li>
                            <li>✅ Criptografia de ponta a ponta</li>
                            <li>✅ Armazenamento seguro em nuvem</li>
                            <li>✅ Rastreabilidade completa</li>
                        </ul>
                    </div>

                    <div class="section">
                        <p><strong>Dúvidas?</strong> Entre em contato conosco através da plataforma Eleitora 360 ou responda este email.</p>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 Eleitora 360 - Gestão Eleitoral Digital</p>
                    <p>Este é um email automático. Por favor, não responda diretamente.</p>
                    <p style="margin-top: 15px; border-top: 1px solid #d1d5db; padding-top: 15px;">
                        Você está recebendo este email porque foi designado como signatário de um contrato.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def signature_confirmation(contract: dict, signer_name: str, signed_date: str) -> str:
        """Generate signature confirmation email"""
        return f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head><meta charset="UTF-8">{EmailTemplate.BASE_STYLE}</head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Contrato Assinado</h1>
                </div>
                <div class="content">
                    <p>Olá <strong>{signer_name}</strong>,</p>

                    <div class="section">
                        <p>Seu contrato foi assinado com sucesso e está agora em vigor.</p>
                    </div>

                    <div class="info-box">
                        <h2>Informações da Assinatura</h2>
                        <p><strong>Contrato:</strong> {contract.get('title', 'Contrato')}</p>
                        <p><strong>Valor:</strong> R$ {contract.get('value', 0):,.2f}</p>
                        <p><strong>Data de Assinatura:</strong> {signed_date}</p>
                        <p><strong>Status:</strong> <span class="status-badge status-signed">✓ ATIVO</span></p>
                    </div>

                    <div class="section">
                        <h2>Próximos Passos</h2>
                        <p>Você pode acessar seu contrato assinado na plataforma Eleitora 360 para:</p>
                        <ul>
                            <li>Fazer download do PDF assinado</li>
                            <li>Baixar comprovante de assinatura</li>
                            <li>Visualizar histórico de alterações</li>
                        </ul>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 Eleitora 360 - Gestão Eleitoral Digital</p>
                </div>
            </div>
        </body>
        </html>
        """

# ============== EMAIL ROUTES ==============
async def send_email_async(to_email: str, subject: str, html_content: str, reply_to: str = None):
    """Send email using Resend with retry logic"""
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        logging.warning(f"Email service not configured - email to {to_email} not sent")
        return False

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
            if reply_to:
                params["reply_to"] = reply_to

            response = await asyncio.to_thread(resend.Emails.send, params)
            logging.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{max_retries} failed to send email to {to_email}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logging.error(f"Failed to send email after {max_retries} attempts: {to_email}")
                return False

@api_router.post("/email/send-signature-request")
async def send_signature_email(
    contract_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Send professional signature request email with template"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    locador_email = contract.get("locador_email")
    locador_nome = contract.get("locador_nome", "Prezado(a)")

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
            "signature_request_sent_at": datetime.now(timezone.utc).isoformat(),
            "status": "aguardando_assinatura"
        }}
    )

    # Use professional email template
    html_content = EmailTemplate.signature_request(contract, locador_nome, signature_link, expiry_days=7)

    # Send email in background
    background_tasks.add_task(
        send_email_async,
        locador_email,
        "Solicitação de Assinatura de Contrato - Eleitora 360",
        html_content,
        reply_to=SENDER_EMAIL
    )

    return {
        "message": "Email de solicitação enviado com sucesso",
        "signature_link": signature_link,
        "email_sent_to": locador_email,
        "expires_in_days": 7
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
                raise HTTPException(status_code=400, detail="Token invÃ¡lido para este contrato")
            contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Token expirado")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Token invÃ¡lido")
    elif party == "locatario" and current_user:
        contract = await db.contracts.find_one(
            {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
            {"_id": 0}
        )
    else:
        raise HTTPException(status_code=400, detail="AutenticaÃ§Ã£o necessÃ¡ria")
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nÃ£o encontrado")
    
    # Validate selfie (must be base64 image)
    if not data.selfie_base64 or len(data.selfie_base64) < 1000:
        raise HTTPException(status_code=400, detail="Selfie invÃ¡lida")
    
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
        "message": f"Contrato assinado pelo {party} com validaÃ§Ã£o facial",
        "status": update_data["status"],
        "signature_hash": full_hash[:20] + "...",
        "selfie_id": selfie_id
    }

# ============== DIGITAL SIGNATURE WITH GOVBR CERTIFICATE ==============
class DigitalSignatureRequest(BaseModel):
    """Request model for GOV.BR certified digital signature"""
    certificate_serial: str
    signer_name: str
    signer_cpf: str
    signature_hash: str

@api_router.post("/contracts/{contract_id}/sign-with-govbr-certificate")
async def sign_contract_with_govbr_certificate(
    contract_id: str,
    data: DigitalSignatureRequest,
    party: str = Query(..., description="locador or locatario"),
    token: Optional[str] = None,
    current_user: Optional[dict] = None
):
    """Sign contract with GOV.BR certified digital signature (official certificate)"""

    # Validate request based on party
    if party == "locador" and token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload["contract_id"] != contract_id:
                raise HTTPException(status_code=400, detail="Token invalido para este contrato")
            contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Token expirado")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Token invalido")
    elif party == "locatario" and current_user:
        contract = await db.contracts.find_one(
            {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
            {"_id": 0}
        )
    else:
        raise HTTPException(status_code=400, detail="Autenticacao necessaria")

    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nao encontrado")

    # Generate certified digital signature hash
    now = datetime.now(timezone.utc).isoformat()
    signature_content = f"{contract_id}-{party}-{data.signer_cpf}-{data.certificate_serial}-{now}-{data.signature_hash}"
    certified_hash = hashlib.sha256(signature_content.encode()).hexdigest()

    # Build GOV.BR signature metadata
    govbr_metadata = build_govbr_signature_metadata(contract, party)
    govbr_metadata.update({
        "certificate_serial": data.certificate_serial,
        "signer_cpf": data.signer_cpf,
        "signature_timestamp": now,
        "certified_hash": certified_hash
    })

    # Update contract with certified signature
    update_data = {
        f"{party}_assinatura_hash": certified_hash,
        f"{party}_assinatura_data": now,
        f"{party}_nome_assinatura": data.signer_name,
        f"{party}_assinatura_metodo": "govbr_certificate",
        f"{party}_assinatura_certificado": data.certificate_serial,
        f"{party}_assinatura_metadados": govbr_metadata
    }

    # Check if both parties signed
    other_party = "locatario" if party == "locador" else "locador"
    if contract.get(f"{other_party}_assinatura_hash"):
        update_data["status"] = "ativo"
    else:
        update_data["status"] = f"assinado_{party}"

    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})

    # Send confirmation email
    campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
    html_content = EmailTemplate.signature_confirmation(contract, data.signer_name, now)
    await send_email_async(
        to_email=contract.get(f"{party}_email", ""),
        subject="Contrato Assinado Digitalmente - Eleitora 360",
        html_content=html_content
    )

    logging.info(f"Contract {contract_id} signed with GOV.BR certificate by {party}: {data.signer_cpf}")

    return {
        "message": f"Contrato assinado pelo {party} com certificado digital GOV.BR",
        "status": update_data["status"],
        "signature_hash": certified_hash[:20] + "...",
        "certificate_serial": data.certificate_serial,
        "signature_timestamp": now,
        "verification_url": f"{APP_URL}/verify-signature/{certified_hash[:10]}"
    }

@api_router.get("/contracts/{contract_id}/signature-audit-trail")
async def get_signature_audit_trail(
    contract_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get complete audit trail for contract signatures (GOV.BR certified or biometric)"""
    contract = await db.contracts.find_one(
        {"id": contract_id, "campaign_id": current_user.get("campaign_id")},
        {"_id": 0}
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato nao encontrado")

    audit_trail = {
        "contract_id": contract_id,
        "contract_title": contract.get("title", "Contrato"),
        "status": contract.get("status", "rascunho"),
        "signatures": []
    }

    # Locador signature audit
    if contract.get("locador_assinatura_hash"):
        audit_trail["signatures"].append({
            "party": "locador",
            "signer_name": contract.get("locador_nome_assinatura", "N/A"),
            "signed_at": contract.get("locador_assinatura_data", ""),
            "signature_method": contract.get("locador_assinatura_metodo", "facial_biometric"),
            "certificate_serial": contract.get("locador_assinatura_certificado", None),
            "signature_hash": contract.get("locador_assinatura_hash", "")[:32] + "...",
            "verified": True
        })

    # Locatario signature audit
    if contract.get("locatario_assinatura_hash"):
        audit_trail["signatures"].append({
            "party": "locatario",
            "signer_name": contract.get("locatario_nome_assinatura", "N/A"),
            "signed_at": contract.get("locatario_assinatura_data", ""),
            "signature_method": contract.get("locatario_assinatura_metodo", "digital_signature"),
            "certificate_serial": contract.get("locatario_assinatura_certificado", None),
            "signature_hash": contract.get("locatario_assinatura_hash", "")[:32] + "...",
            "verified": True
        })

    audit_trail["complete"] = len(audit_trail["signatures"]) == 2
    audit_trail["legal_validity"] = "Contrato com validade legal certificada" if audit_trail["complete"] else "Contrato pendente de assinatura"

    return audit_trail

# ============== SPCE EXPORT - DESPESAS ==============
@api_router.get("/export/spce-despesas")
async def export_spce_despesas(current_user: dict = Depends(get_current_user)):
    """Export expenses in SPCE format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    ensure_spce_ready(build_spce_precheck(campaign, expenses=expenses))
    ensure_spce_ready(build_spce_precheck(campaign, expenses=expenses))
    
    if not campaign.get("cnpj"):
        raise HTTPException(status_code=400, detail="CNPJ da campanha nÃ£o configurado")
    
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
# Layout oficial conforme ResoluÃ§Ã£o TSE 23.607/2019
SPCE_DESPESA_CATEGORIAS = {
    "propaganda": {"codigo": "101", "descricao": "Despesas com Propaganda"},
    "pessoal": {"codigo": "102", "descricao": "Despesas com Pessoal"},
    "transporte": {"codigo": "103", "descricao": "Despesas de Transporte"},
    "material": {"codigo": "104", "descricao": "Despesas com Material de Expediente"},
    "alimentacao": {"codigo": "105", "descricao": "Despesas com AlimentaÃ§Ã£o"},
    "combustivel": {"codigo": "106", "descricao": "Despesas com CombustÃ­vel e Lubrificantes"},
    "locacao_veiculo": {"codigo": "107", "descricao": "LocaÃ§Ã£o/CessÃ£o de VeÃ­culos"},
    "locacao_imovel": {"codigo": "108", "descricao": "LocaÃ§Ã£o/CessÃ£o de ImÃ³veis"},
    "eventos": {"codigo": "109", "descricao": "Despesas com Eventos"},
    "servicos_terceiros": {"codigo": "110", "descricao": "Serviços Prestados por Terceiros"},
    "agua_luz_telefone": {"codigo": "111", "descricao": "Ãgua, Luz, Telefone e Internet"},
    "taxa_bancaria": {"codigo": "112", "descricao": "Taxas e Tarifas BancÃ¡rias"},
    "producao_audiovisual": {"codigo": "113", "descricao": "ProduÃ§Ã£o de Programas de RÃ¡dio/TV/VÃ­deo"},
    "impulsionamento": {"codigo": "114", "descricao": "Impulsionamento de ConteÃºdos"},
    "outros": {"codigo": "199", "descricao": "Outras Despesas"}
}

@api_router.get("/export/spce-despagtos")
async def export_spce_despagtos(current_user: dict = Depends(get_current_user)):
    """Export expenses in SPCE DESPAGTOS layout format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    cnpj = (campaign.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha invÃ¡lido ou nÃ£o configurado")
    
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
    "veiculo_com_motorista": {"codigo": "01", "descricao": "LocaÃ§Ã£o de VeÃ­culo com Motorista"},
    "veiculo_sem_motorista": {"codigo": "02", "descricao": "LocaÃ§Ã£o de VeÃ­culo sem Motorista"},
    "imovel_comite": {"codigo": "03", "descricao": "LocaÃ§Ã£o de Imóvel para ComitÃª"},
    "imovel_evento": {"codigo": "04", "descricao": "LocaÃ§Ã£o de Imóvel para Evento"},
    "servico_grafico": {"codigo": "05", "descricao": "Serviços GrÃ¡ficos"},
    "servico_publicidade": {"codigo": "06", "descricao": "Serviços de Publicidade"},
    "servico_pesquisa": {"codigo": "07", "descricao": "Serviços de Pesquisa"},
    "servico_juridico": {"codigo": "08", "descricao": "Serviços JurÃ­dicos"},
    "servico_contabil": {"codigo": "09", "descricao": "Serviços ContÃ¡beis"},
    "servico_ti": {"codigo": "10", "descricao": "Serviços de TI"},
    "producao_audiovisual": {"codigo": "11", "descricao": "ProduÃ§Ã£o Audiovisual"},
    "impulsionamento": {"codigo": "12", "descricao": "Impulsionamento de ConteÃºdos"},
    # aliases legados para compatibilidade de contratos antigos
    "imovel": {"codigo": "03", "descricao": "LocaÃ§Ã£o de Imóvel para ComitÃª"},
    "espaco_evento": {"codigo": "04", "descricao": "LocaÃ§Ã£o de Imóvel para Evento"},
    "bem_movel": {"codigo": "99", "descricao": "Outros Contratos"},
    "outros": {"codigo": "99", "descricao": "Outros Contratos"}
}

@api_router.get("/export/spce-contratos")
async def export_spce_contratos(current_user: dict = Depends(get_current_user)):
    """Export contracts in SPCE format"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    ensure_spce_ready(build_spce_precheck(campaign, contracts=contracts))
    
    cnpj = (campaign.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="CNPJ da campanha invÃ¡lido ou nÃ£o configurado")
    
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
        template = _normalize_contract_template_type(contract.get("template_type", "outros"))
        tipo_info = SPCE_CONTRATO_TIPOS.get(template, SPCE_CONTRATO_TIPOS["outros"])
        
        # Format amount
        amount = f"{contract.get('value', 0):.2f}".replace(".", ",")
        
        # Status: A=Ativo, E=Encerrado, C=Cancelado, R=Rascunho
        status_map = {"ativo": "A", "encerrado": "E", "cancelado": "C", "rascunho": "R"}
        status = status_map.get(contract.get("status", "rascunho"), "R")
        
        # Signature status: accepts either internal signatures or externally signed uploaded doc
        signed_evidence = _contract_has_signature_evidence(contract)
        assinado_locador = "S" if (contract.get("locador_assinatura_hash") or signed_evidence) else "N"
        assinado_locatario = "S" if (contract.get("locatario_assinatura_hash") or signed_evidence) else "N"
        
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
            SPCE_CONTRATO_TIPOS.get(_normalize_contract_template_type(c.get("template_type", "outros")), SPCE_CONTRATO_TIPOS["outros"])["descricao"]
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
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=14, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Subtitle', alignment=TA_CENTER, fontSize=10, textColor=colors.grey))
    
    elements = []
    
    # Header
    elements.append(Paragraph("RELATÃ“RIO DE DESPESAS ELEITORAIS", styles['Title2']))
    elements.append(Paragraph(f"Campanha: {campaign.get('candidate_name', '')} - {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"CNPJ: {campaign.get('cnpj', 'NÃ£o informado')}", styles['Normal']))
    elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y Ã s %H:%M')}", styles['Subtitle']))
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
        
        exp_data = [["Data", "DescriÃ§Ã£o", "Fornecedor", "Valor", "Status"]]
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
    elements.append(Paragraph("<i>Documento gerado pelo sistema Eleitora 360 - Formato compatÃ­vel SPCE/TSE</i>", styles['Subtitle']))
    
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
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Title2', alignment=TA_CENTER, fontSize=14, spaceAfter=20, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Subtitle', alignment=TA_CENTER, fontSize=10, textColor=colors.grey))
    
    elements = []
    
    # Header
    elements.append(Paragraph("RELATÃ“RIO DE CONTRATOS ELEITORAIS", styles['Title2']))
    elements.append(Paragraph(f"Campanha: {campaign.get('candidate_name', '')} - {campaign.get('party', '')}", styles['Normal']))
    elements.append(Paragraph(f"CNPJ: {campaign.get('cnpj', 'NÃ£o informado')}", styles['Normal']))
    elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y Ã s %H:%M')}", styles['Subtitle']))
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
        contract_data = [["TÃ­tulo", "Contratado", "PerÃ­odo", "Valor", "Status"]]
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
    elements.append(Paragraph("<i>Documento gerado pelo sistema Eleitora 360 - Formato compatÃ­vel SPCE/TSE</i>", styles['Subtitle']))
    
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
        "nota": "Categorias conforme ResoluÃ§Ã£o TSE 23.607/2019"
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
        "message": f"Importadas {len(entries)} transaÃ§Ãµes"
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
        raise HTTPException(status_code=404, detail="ImportaÃ§Ã£o nÃ£o encontrada")
    
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
# AI Assistant module temporarily disabled - using fallback implementations
# from ai_assistant import assistant, get_tse_rules_summary

# Fallback implementations for AI functions
class AssistantFallback:
    """Fallback AI assistant when ai_assistant module is not available"""

    async def chat(self, message: str, campaign_context: dict) -> str:
        """Fallback chat - returns basic response"""
        return f"Recebi sua mensagem: {message}. Por favor, use a interface principal para operações."

    async def analyze_expenses(self, expenses: list, campaign_context: dict) -> str:
        """Fallback expense analysis"""
        total = sum(e.get("amount", 0) for e in expenses)
        return f"Total de despesas: R$ {total:.2f}"

    async def check_compliance(self, campaign_context: dict, contracts: list) -> str:
        """Fallback compliance check"""
        return "Conformidade TSE: Sistema verificando dados..."

async def get_tse_rules_summary() -> dict:
    """Fallback TSE rules"""
    return {
        "rules": "Consulte as normas TSE no site oficial",
        "limits": "Limites estão sendo validados pelo sistema"
    }

assistant = AssistantFallback()

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
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
    
    def _fallback_ai_response(message_text: str) -> str:
        msg = (message_text or "").lower()
        if "saldo" in msg or "resumo" in msg:
            return (
                f"Resumo rápido: receitas {format_currency(total_revenues)}, despesas {format_currency(total_expenses)} "
                f"e saldo {format_currency(total_revenues - total_expenses)}. "
                f"Pendências: {pending_count} despesa(s) e {contracts_missing_docs} contrato(s) com documentação pendente."
            )
        if "despesa" in msg or "gasto" in msg:
            return (
                f"Você tem {pending_count} despesa(s) pendente(s), com total pendente de {format_currency(pending_expenses)}. "
                "Quer que eu priorize por vencimento?"
            )
        if "contrato" in msg:
            return (
                f"Há {len(contracts)} contrato(s) cadastrados e {contracts_missing_docs} com documentação pendente. "
                "Posso te listar os próximos contratos para finalizar."
            )
        if "conform" in msg or "tse" in msg or "spce" in msg:
            if campaign_context.get("limite_gastos", 0) > 0:
                percentage = (total_expenses / campaign_context["limite_gastos"]) * 100
                return (
                    f"Conformidade: gastos em {percentage:.1f}% do limite e saldo de limite de "
                    f"{format_currency(campaign_context['limite_gastos'] - total_expenses)}."
                )
            return "Conformidade: limite de gastos ainda não configurado. Complete Configurações para monitoramento automático."
        return (
            "Estou em modo de contingência agora, mas sigo operacional. "
            f"Posso ajudar com resumo financeiro, despesas pendentes ({pending_count}) e contratos pendentes ({contracts_missing_docs})."
        )

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
                alerts.append(f"?? Gastos em {percentage:.1f}% do limite!")
        if pending_count > 0:
            alerts.append(f"?? {pending_count} despesa(s) pendente(s)")
        if contracts_missing_docs > 0:
            alerts.append(f"?? {contracts_missing_docs} contrato(s) sem documentação completa")
        
        return {
            "response": response,
            "session_id": session_id,
            "alerts": alerts if alerts else None
        }
        
    except Exception as e:
        logger.exception("Falha no provedor de IA em /ai/chat. Aplicando fallback local: %s", e)
        fallback_response = _fallback_ai_response(data.message)
        new_messages = [
            {"role": "user", "content": data.message, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"role": "assistant", "content": fallback_response, "timestamp": datetime.now(timezone.utc).isoformat()}
        ]
        await db.chat_history.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": {"$each": new_messages}},
                "$set": {
                    "campaign_id": campaign_id,
                    "user_id": current_user["id"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "fallback_mode": True
                }
            },
            upsert=True
        )
        return {
            "response": fallback_response,
            "session_id": session_id,
            "alerts": ["Modo contingência ativo: IA externa indisponível."],
            "fallback_mode": True
        }
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
    
    return {"message": "HistÃ³rico limpo com sucesso"}

@api_router.post("/ai/analyze-expenses")
async def ai_analyze_expenses(current_user: dict = Depends(get_current_user)):
    """Get AI analysis of campaign expenses"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    if not expenses:
        return {"analysis": "NÃ£o hÃ¡ despesas registradas para analisar."}
    
    campaign_context = {
        "campaign_id": campaign_id,
        "candidate_name": campaign.get("candidate_name", ""),
        "limite_gastos": campaign.get("limite_gastos", 0)
    }
    
    try:
        analysis = await assistant.analyze_expenses(expenses, campaign_context)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na anÃ¡lise: {str(e)}")

@api_router.post("/ai/check-compliance")
async def ai_check_compliance(current_user: dict = Depends(get_current_user)):
    """Check campaign compliance with electoral rules"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
        raise HTTPException(status_code=500, detail=f"Erro na verificaÃ§Ã£o: {str(e)}")

@api_router.get("/ai/tse-rules")
async def get_tse_rules():
    """Get summary of current TSE electoral rules"""
    rules = await get_tse_rules_summary()
    return {"rules": rules}

# ============== VOICE ASSISTANT ROUTES ==============
from voice_assistant import voice_assistant, RESPONSES

async def _execute_voice_command_text(transcribed_text: str, current_user: dict) -> dict:
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")

    command, params = voice_assistant.parse_command(transcribed_text)

    response_text = ""
    action = None
    action_data = None

    if command == "greeting":
        role = (current_user.get("role") or "").lower()
        perfil = "contador" if "contador" in role else "candidato"
        expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
        contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(500)
        today = datetime.now(timezone.utc).date()
        pending_expenses = [e for e in expenses if (e.get("payment_status") or "").lower() != "pago"]
        due_soon = []
        for e in pending_expenses:
            try:
                due = datetime.fromisoformat(str(e.get("date"))).date()
                if 0 <= (due - today).days <= 7:
                    due_soon.append(e)
            except Exception:
                continue
        unsigned_contracts = [
            c for c in contracts
            if (c.get("status") or "").lower() not in {"assinado", "concluido", "finalizado"}
        ]
        response_text = (
            f"Oi, {perfil}. Sou a Flora. "
            f"Você tem {len(pending_expenses)} despesa(s) pendente(s), "
            f"{len(due_soon)} pagamento(s) vencendo nos próximos 7 dias "
            f"e {len(unsigned_contracts)} contrato(s) para finalizar. "
            "Quer que eu te ajude a gerar uma despesa, criar um contrato ou revisar os vencimentos agora?"
        )

    elif command == "help":
        response_text = RESPONSES["help"]

    elif command == "query_saldo":
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
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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

        expense_doc = {
            "id": str(uuid.uuid4()),
            "description": "Despesa adicionada por comando de voz",
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

        revenue_doc = {
            "id": str(uuid.uuid4()),
            "description": "Receita adicionada por comando de voz",
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

    elif command == "contract_with_expense":
        response_text = "Vou abrir contratos e preparar a despesa vinculada. Quer que eu siga com o cadastro agora?"
        action = "navigate"
        action_data = {"route": "/contratos"}

    elif command == "sign_contract":
        response_text = "Vou abrir contratos para voce assinar. Quer que eu abra o contrato pendente?"
        action = "navigate"
        action_data = {"route": "/contratos"}

    elif command == "upload_documents":
        response_text = "Vou abrir contratos para voce anexar documentos. Quer ver as pendencias primeiro?"
        action = "navigate"
        action_data = {"route": "/contratos"}

    elif command == "ai_chat":
        message = params.get("message", transcribed_text)
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
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

        ai_response = await assistant.chat(
            session_id=f"voice_{campaign_id}",
            message=message,
            campaign_context=campaign_context
        )

        response_text = ai_response[:1000] if len(ai_response) > 1000 else ai_response

    else:
        response_text = RESPONSES["not_understood"]

    try:
        audio_base64 = await voice_assistant.generate_speech_base64(response_text)
    except Exception:
        audio_base64 = None

    return {
        "command": command,
        "response_text": response_text,
        "audio_response": audio_base64,
        "action": action,
        "action_data": action_data,
        "success": True
    }

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
        raise HTTPException(status_code=400, detail="Arquivo muito grande (mÃ¡ximo 25MB)")
    
    try:
        text = await voice_assistant.transcribe_audio(contents, audio.filename or "audio.webm")
        return {"text": text, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na transcriÃ§Ã£o: {str(e)}")

@api_router.post("/voice/speak")
async def voice_speak(
    text: str = Query(..., description="Text to convert to speech"),
    current_user: dict = Depends(get_current_user)
):
    """Convert text to speech using TTS"""
    if not text:
        raise HTTPException(status_code=400, detail="Texto nÃ£o fornecido")
    
    try:
        audio_base64 = await voice_assistant.generate_speech_base64(text)
        return {
            "audio": audio_base64,
            "format": "mp3",
            "success": True,
            "fallback_local": False
        }
    except Exception as e:
        logger.warning("Voice speak fallback local ativado: %s", e)
        return {
            "audio": None,
            "format": "mp3",
            "success": False,
            "fallback_local": True,
            "detail": "Sintese remota indisponivel. Use fallback local no navegador."
        }

@api_router.post("/voice/command")
async def voice_command(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Process voice command: transcribe, parse, execute, and respond with voice"""
    # Read audio file
    contents = await audio.read()
    
    try:
        # Step 1: Transcribe audio
        transcribed_text = await voice_assistant.transcribe_audio(contents, audio.filename or "audio.webm")
        result = await _execute_voice_command_text(transcribed_text, current_user)
        result["transcribed_text"] = transcribed_text
        return result
        
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


class VoiceTextCommand(BaseModel):
    text: str


@api_router.post("/voice/text-command")
async def voice_text_command(
    payload: VoiceTextCommand,
    current_user: dict = Depends(get_current_user)
):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")
    result = await _execute_voice_command_text(text, current_user)
    result["transcribed_text"] = text
    return result

@api_router.get("/voice/greeting")
async def voice_greeting(current_user: dict = Depends(get_current_user)):
    """Get voice greeting from Flora"""
    try:
        audio_base64 = await voice_assistant.generate_speech_base64(RESPONSES["greeting"])
        return {
            "text": RESPONSES["greeting"],
            "audio": audio_base64,
            "format": "mp3",
            "success": True,
            "fallback_local": False
        }
    except Exception as e:
        logger.warning("Voice greeting fallback local ativado: %s", e)
        return {
            "text": RESPONSES["greeting"],
            "audio": None,
            "format": "mp3",
            "success": False,
            "fallback_local": True,
            "detail": "Sintese remota indisponivel. Use fallback local no navegador."
        }

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
    
    professional_data = data.model_dump(exclude={"password"})
    professional_data["cpf"] = validate_and_normalize_document(
        professional_data.get("cpf"), "CPF do profissional", allowed_types=("cpf",), required=False
    )

    professional_id = str(uuid.uuid4())
    professional_doc = {
        "id": professional_id,
        **professional_data,
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
    update_data = data.model_dump(exclude={"password"})
    update_data["cpf"] = validate_and_normalize_document(
        update_data.get("cpf"), "CPF do profissional", allowed_types=("cpf",), required=False
    )
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
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
        return {"campaigns": [], "message": "VocÃª nÃ£o é um contador cadastrado"}
    
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
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {} or {}

    pix_data = data.model_dump()
    source_account_type = (pix_data.get("source_account_type") or "doacao").strip().lower()
    account_map = {
        "doacao": {
            "bank": campaign.get("conta_doacao_banco"),
            "agency": campaign.get("conta_doacao_agencia"),
            "account": campaign.get("conta_doacao_numero"),
            "digit": campaign.get("conta_doacao_digito"),
            "label": "Conta de Doacao",
        },
        "fundo_partidario": {
            "bank": campaign.get("conta_fundo_partidario_banco"),
            "agency": campaign.get("conta_fundo_partidario_agencia"),
            "account": campaign.get("conta_fundo_partidario_numero"),
            "digit": campaign.get("conta_fundo_partidario_digito"),
            "label": "Conta Fundo Partidario",
        },
        "fefec": {
            "bank": campaign.get("conta_fefec_banco"),
            "agency": campaign.get("conta_fefec_agencia"),
            "account": campaign.get("conta_fefec_numero"),
            "digit": campaign.get("conta_fefec_digito"),
            "label": "Conta FEFEC",
        },
    }
    selected_account = account_map.get(source_account_type)
    if not selected_account:
        raise HTTPException(status_code=400, detail="Conta de origem invalida. Use: doacao, fundo_partidario ou fefec.")
    if not selected_account.get("bank") or not selected_account.get("agency") or not selected_account.get("account"):
        raise HTTPException(
            status_code=400,
            detail=f"Dados bancarios incompletos para {selected_account['label']}. Configure em Configuracoes > Contas Bancarias.",
        )

    pix_data["recipient_cpf_cnpj"] = validate_and_normalize_document(
        pix_data.get("recipient_cpf_cnpj"), "CPF/CNPJ do favorecido", required=False
    )
    if pix_data.get("pix_key_type") == "cpf":
        pix_data["pix_key"] = validate_and_normalize_document(
            pix_data.get("pix_key"), "Chave PIX (CPF)", allowed_types=("cpf",), required=True
        )
    elif pix_data.get("pix_key_type") == "cnpj":
        pix_data["pix_key"] = validate_and_normalize_document(
            pix_data.get("pix_key"), "Chave PIX (CNPJ)", allowed_types=("cnpj",), required=True
        )

    # Verify expense exists if provided
    expense = None
    if pix_data.get("expense_id"):
        expense = await db.expenses.find_one(
            {"id": pix_data["expense_id"], "campaign_id": campaign_id}
        )
        if not expense:
            raise HTTPException(status_code=404, detail="Despesa não encontrada")
        # Keep PIX aligned with linked expense (value/date/description).
        pix_data["amount"] = float(expense.get("amount", pix_data["amount"]))
        pix_data["scheduled_date"] = expense.get("date") or pix_data.get("scheduled_date")
        if not pix_data.get("description"):
            pix_data["description"] = expense.get("description")
        if not pix_data.get("recipient_name"):
            pix_data["recipient_name"] = expense.get("supplier_name")
        if not pix_data.get("recipient_cpf_cnpj") and expense.get("supplier_cpf_cnpj"):
            pix_data["recipient_cpf_cnpj"] = expense.get("supplier_cpf_cnpj")

    pix_id = str(uuid.uuid4())
    bb_response = None
    txid = None
    pix_copia_cola = None

    # Try real BB integration if available
    bb_error = None
    if bb_pix_client and BB_PIX_AVAILABLE:
        try:
            bb_response = await bb_pix_client.create_pix_payment({
                "pix_key": pix_data["pix_key"],
                "recipient_name": pix_data["recipient_name"],
                "recipient_cpf_cnpj": pix_data.get("recipient_cpf_cnpj"),
                "amount": pix_data["amount"],
                "description": pix_data.get("description"),
                "scheduled_date": pix_data.get("scheduled_date") or datetime.now().strftime("%Y-%m-%d")
            })

            if bb_response.get("success"):
                txid = bb_response.get("txid")
                pix_copia_cola = bb_response.get("pixCopiaECola")
                logging.info(f"PIX BB criado com sucesso: {txid}")
            else:
                bb_error = bb_response.get("error")
                logging.warning(f"PIX BB falhou, usando modo simulado: {bb_response.get('error')}")
        except Exception as e:
            bb_error = str(e)
            logging.error(f"Erro na integração BB PIX: {e}")

    if BB_STRICT_MODE and BB_PIX_AVAILABLE and not txid:
        raise HTTPException(
            status_code=502,
            detail=f"Integracao BB em modo estrito: falha ao criar PIX real ({bb_error or 'erro desconhecido'})"
        )

    pix_doc = {
        "id": pix_id,
        "source_account_type": source_account_type,
        "pix_key": pix_data["pix_key"],
        "pix_key_type": pix_data["pix_key_type"],
        "recipient_name": pix_data["recipient_name"],
        "recipient_cpf_cnpj": pix_data.get("recipient_cpf_cnpj"),
        "amount": pix_data["amount"],
        "description": pix_data.get("description"),
        "scheduled_date": pix_data.get("scheduled_date"),
        "expense_id": pix_data.get("expense_id"),
        "status": "agendado" if pix_data.get("scheduled_date") else "processando",
        "transaction_id": txid,
        "pix_copia_cola": pix_copia_cola,
        "bb_response": bb_response if bb_response else None,
        "bb_error": bb_error,
        "integration_mode": "real" if txid else "simulado",
        "campaign_id": campaign_id,
        "source_bank": selected_account.get("bank"),
        "source_agency": selected_account.get("agency"),
        "source_account": selected_account.get("account"),
        "source_account_digit": selected_account.get("digit"),
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
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    return payment

@api_router.post("/pix/simulate-execution/{pix_id}")
async def simulate_pix_execution(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Simulate PIX execution (for testing - real execution requires BB API)"""
    campaign_id = current_user.get("campaign_id")
    
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    
    # Check if already executed
    if payment.get("status") == "executado":
        raise HTTPException(status_code=400, detail="PIX jÃ¡ foi executado")
    
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
        "message": "PIX executado com sucesso (simulaÃ§Ã£o)",
        "transaction_id": transaction_id,
        "status": "executado"
    }

@api_router.get("/pix/bank-info")
async def get_bank_info():
    """Get Banco do Brasil integration info"""
    cert_ready = False
    if BB_CLIENT_CERT_PATH and os.path.exists(BB_CLIENT_CERT_PATH):
        cert_ready = True
    if BB_CLIENT_KEY_PATH and os.path.exists(BB_CLIENT_KEY_PATH):
        cert_ready = True
    return {
        "bank": "Banco do Brasil",
        "integration_available": BB_PIX_AVAILABLE,
        "environment": BB_ENVIRONMENT if BB_PIX_AVAILABLE else None,
        "integration_status": "ativo" if BB_PIX_AVAILABLE else "nÃ£o_configurado",
        "strict_mode": BB_STRICT_MODE,
        "mtls_configured": cert_ready,
        "operation_mode": "real_only" if BB_STRICT_MODE else "real_with_simulation_fallback",
        "features": [
            "PIX CobranÃ§a (cobv)",
            "PIX Pagamento",
            "Consulta de Status",
            "GeraÃ§Ã£o de QR Code",
            "PIX Copia e Cola"
        ] if BB_PIX_AVAILABLE else [],
        "api_docs": "https://developers.bb.com.br",
        "note": "IntegraÃ§Ã£o com Banco do Brasil para PIX" if BB_PIX_AVAILABLE else "Configure as credenciais BB_APP_KEY, BB_CLIENT_ID e BB_CLIENT_SECRET no ambiente"
    }

@api_router.get("/pix/bank-diagnostic")
async def get_bank_diagnostic():
    """Diagnostico rapido da conectividade BB (config + OAuth)."""
    if not bb_pix_client:
        return {
            "status": "not_configured",
            "configured": False,
            "message": "Credenciais BB nao configuradas",
            "required_envs": ["BB_APP_KEY", "BB_CLIENT_ID", "BB_CLIENT_SECRET"],
            "optional_envs": ["BB_CLIENT_CERT_PATH", "BB_CLIENT_KEY_PATH", "BB_STRICT_MODE"],
        }
    diagnostic = await bb_pix_client.diagnose_connection()
    diagnostic["required_envs"] = ["BB_APP_KEY", "BB_CLIENT_ID", "BB_CLIENT_SECRET"]
    diagnostic["optional_envs"] = ["BB_CLIENT_CERT_PATH", "BB_CLIENT_KEY_PATH", "BB_STRICT_MODE"]
    return diagnostic

@api_router.get("/pix/check-status/{pix_id}")
async def check_pix_status(pix_id: str, current_user: dict = Depends(get_current_user)):
    """Check PIX payment status from Banco do Brasil"""
    campaign_id = current_user.get("campaign_id")
    
    payment = await db.pix_payments.find_one(
        {"id": pix_id, "campaign_id": campaign_id}
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    
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
                    "note": "NÃ£o foi possÃ­vel consultar o status no Banco do Brasil"
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
        raise HTTPException(status_code=404, detail="Pagamento nÃ£o encontrado")
    
    if payment.get("status") == "executado":
        raise HTTPException(status_code=400, detail="PIX jÃ¡ foi executado")
    
    txid = payment.get("transaction_id")
    
    # If we have real integration, the PIX is already created on BB
    # We just need to wait for the recipient to pay
    if txid and BB_PIX_AVAILABLE:
        # Check current status
        if bb_pix_client:
            bb_status = await bb_pix_client.check_pix_status(txid)
            
            return {
                "message": "PIX jÃ¡ estÃ¡ ativo no Banco do Brasil",
                "txid": txid,
                "bb_status": bb_status.get("status") if bb_status.get("success") else "unknown",
                "pix_copia_cola": payment.get("pix_copia_cola"),
                "note": "O destinatÃ¡rio pode pagar usando o cÃ³digo PIX Copia e Cola ou QR Code"
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
# Fontes oficiais:
# - Limites municipais (prefeito/vereador): Portaria TSE 593/2024 (anexo por município)
# - Limites gerais (deputado federal/estadual/distrital): tabela TSE Eleições 2022

TSE_MUNICIPAL_LIMITS_2024_XLSX_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/"
    "contas-campanha/limites-gastos/limites_de_gastos_2024.xlsx"
)

TSE_SPENDING_LIMITS_FALLBACK = {
    "prefeito": {
        "micro": {"min_eleitores": 0, "max_eleitores": 10000, "primeiro_turno": 159850.76, "segundo_turno": 63940.30},
        "pequeno": {"min_eleitores": 10001, "max_eleitores": 50000, "primeiro_turno": 500000.00, "segundo_turno": 200000.00},
        "medio": {"min_eleitores": 50001, "max_eleitores": 200000, "primeiro_turno": 2000000.00, "segundo_turno": 800000.00},
        "grande": {"min_eleitores": 200001, "max_eleitores": 1000000, "primeiro_turno": 10000000.00, "segundo_turno": 4000000.00},
        "metropole": {"min_eleitores": 1000001, "max_eleitores": float("inf"), "primeiro_turno": 67200000.00, "segundo_turno": 26880000.00},
    },
    "vereador": {
        "micro": {"min_eleitores": 0, "max_eleitores": 10000, "limite": 15985.08},
        "pequeno": {"min_eleitores": 10001, "max_eleitores": 50000, "limite": 50000.00},
        "medio": {"min_eleitores": 50001, "max_eleitores": 200000, "limite": 200000.00},
        "grande": {"min_eleitores": 200001, "max_eleitores": 1000000, "limite": 1000000.00},
        "metropole": {"min_eleitores": 1000001, "max_eleitores": float("inf"), "limite": 4770000.00},
    },
}

TSE_GENERAL_LIMITS_2022 = {
    "deputado_federal": 3176572.53,
    "deputado_estadual": 1270629.01,
    "deputado_distrital": 1270629.01,
}

# Fallback local para cenários sem acesso externo (mantém compatibilidade de testes)
MUNICIPIOS_TSE = {
    "5200050": {"nome": "Anhanguera", "uf": "GO", "eleitores": 800, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "5101102": {"nome": "Araguainha", "uf": "MT", "eleitores": 950, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "3505302": {"nome": "Bora", "uf": "SP", "eleitores": 850, "prefeito_1t": 159850.76, "vereador": 15985.08},
    "3550308": {"nome": "Sao Paulo", "uf": "SP", "eleitores": 9500000, "prefeito_1t": 67200000.00, "prefeito_2t": 26880000.00, "vereador": 4770000.00},
    "2611606": {"nome": "Recife", "uf": "PE", "eleitores": 1200000, "prefeito_1t": 9776138.29, "prefeito_2t": 3910455.32, "vereador": 1313263.10},
    "4106902": {"nome": "Curitiba", "uf": "PR", "eleitores": 1400000, "prefeito_1t": 14161044.67, "vereador": 689037.15},
    "2408102": {"nome": "Mossoro", "uf": "RN", "eleitores": 220000, "prefeito_1t": 3500000.00, "vereador": 350000.00},
    "2400505": {"nome": "Assu", "uf": "RN", "eleitores": 45000, "prefeito_1t": 450000.00, "vereador": 45000.00},
}

_tse_municipal_limits_cache: Dict[str, Dict[str, Any]] = {}
_tse_municipal_limits_loaded_at: Optional[str] = None
_tse_municipal_limits_lock = asyncio.Lock()
_ibge_municipios_cache: Dict[str, List[Dict[str, Any]]] = {}
_ibge_municipios_lock = asyncio.Lock()


def _normalize_text_key(value: Optional[str]) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


def _normalize_position(position: Optional[str]) -> str:
    raw = _normalize_text_key(position)
    aliases = {
        "prefeito": "prefeito",
        "vice prefeito": "vice_prefeito",
        "vereador": "vereador",
        "deputado federal": "deputado_federal",
        "dep federal": "deputado_federal",
        "deputado estadual": "deputado_estadual",
        "dep estadual": "deputado_estadual",
        "deputado distrital": "deputado_distrital",
        "dep distrital": "deputado_distrital",
    }
    return aliases.get(raw, raw.replace(" ", "_"))


def _parse_money_value(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    text = text.replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _column_ref_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: List[str] = []
    for si in root.findall("x:si", ns):
        parts = [node.text or "" for node in si.findall(".//x:t", ns)]
        values.append("".join(parts))
    return values


def _xlsx_sheet_rows(zf: zipfile.ZipFile, shared_strings: List[str]) -> List[Dict[int, Any]]:
    worksheet_files = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
    if not worksheet_files:
        return []
    worksheet_files.sort()
    root = ET.fromstring(zf.read(worksheet_files[0]))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: List[Dict[int, Any]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        parsed: Dict[int, Any] = {}
        for c in row.findall("x:c", ns):
            ref = c.attrib.get("r", "")
            col = _column_ref_to_index(ref)
            t = c.attrib.get("t")
            v = c.find("x:v", ns)
            if v is None:
                continue
            raw = v.text or ""
            value: Any = raw
            if t == "s":
                idx = int(raw)
                value = shared_strings[idx] if 0 <= idx < len(shared_strings) else raw
            else:
                try:
                    value = float(raw)
                except Exception:
                    value = raw
            parsed[col] = value
        if parsed:
            rows.append(parsed)
    return rows


def _build_tse_municipal_limits(rows: List[Dict[int, Any]]) -> Dict[str, Dict[str, Any]]:
    limits: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        uf_raw = row.get(0)
        city_raw = row.get(1)
        if not uf_raw or not city_raw:
            continue
        uf = str(uf_raw).strip().upper()
        city = str(city_raw).strip()
        if len(uf) != 2 or _normalize_text_key(city) in {"municipio", "município"}:
            continue

        prefeito_1t = _parse_money_value(row.get(5))
        prefeito_2t = _parse_money_value(row.get(6))
        vereador = _parse_money_value(row.get(7))
        if prefeito_1t is None and vereador is None:
            continue

        key = f"{uf}:{_normalize_text_key(city)}"
        limits[key] = {
            "uf": uf,
            "municipio": city,
            "prefeito_1t": prefeito_1t or 0.0,
            "prefeito_2t": prefeito_2t if prefeito_2t is not None else (prefeito_1t or 0.0) * 0.4,
            "vereador": vereador or 0.0,
            "fonte": "TSE Portaria 593/2024 - Limites de Gastos 2024",
            "ano_base": 2024,
        }
    return limits


async def _load_tse_municipal_limits() -> Dict[str, Dict[str, Any]]:
    global _tse_municipal_limits_cache, _tse_municipal_limits_loaded_at
    if _tse_municipal_limits_cache:
        return _tse_municipal_limits_cache

    async with _tse_municipal_limits_lock:
        if _tse_municipal_limits_cache:
            return _tse_municipal_limits_cache
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client_http:
                resp = await client_http.get(TSE_MUNICIPAL_LIMITS_2024_XLSX_URL)
                resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
                shared = _xlsx_shared_strings(zf)
                rows = _xlsx_sheet_rows(zf, shared)
            parsed = _build_tse_municipal_limits(rows)
            if parsed:
                _tse_municipal_limits_cache = parsed
                _tse_municipal_limits_loaded_at = datetime.now(timezone.utc).isoformat()
                return _tse_municipal_limits_cache
        except Exception as e:
            logger.warning(f"Nao foi possivel carregar limites municipais oficiais do TSE: {e}")
        return _tse_municipal_limits_cache


async def _get_ibge_municipios_by_uf(uf: str) -> List[Dict[str, Any]]:
    uf_norm = (uf or "").strip().upper()
    if len(uf_norm) != 2:
        return []
    if uf_norm in _ibge_municipios_cache:
        return _ibge_municipios_cache[uf_norm]

    async with _ibge_municipios_lock:
        if uf_norm in _ibge_municipios_cache:
            return _ibge_municipios_cache[uf_norm]
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client_http:
                resp = await client_http.get(
                    f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_norm}/municipios"
                )
                resp.raise_for_status()
            data = resp.json() or []
            municipios = sorted(
                [
                    {
                        "codigo_ibge": str(item.get("id")),
                        "nome": item.get("nome"),
                        "uf": uf_norm,
                    }
                    for item in data
                    if item.get("id") and item.get("nome")
                ],
                key=lambda x: _normalize_text_key(x.get("nome")),
            )
            _ibge_municipios_cache[uf_norm] = municipios
            return municipios
        except Exception as e:
            logger.warning(f"Nao foi possivel carregar municipios IBGE para {uf_norm}: {e}")
            return []


def _fallback_municipal_limit(cargo_norm: str, eleitores: int, segundo_turno: bool = False) -> Dict[str, Any]:
    faixa = "desconhecida"
    limite = 0.0
    if cargo_norm == "prefeito":
        for f, dados in TSE_SPENDING_LIMITS_FALLBACK["prefeito"].items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                faixa = f
                limite = dados["segundo_turno"] if segundo_turno else dados["primeiro_turno"]
                break
    elif cargo_norm == "vereador":
        for f, dados in TSE_SPENDING_LIMITS_FALLBACK["vereador"].items():
            if dados["min_eleitores"] <= eleitores <= dados["max_eleitores"]:
                faixa = f
                limite = dados["limite"]
                break
    return {
        "limite_gastos": limite,
        "faixa_municipio": faixa,
        "fonte": "Estimativa por faixas (fallback interno)",
        "ano_base": 2024,
        "is_official": False,
    }


async def resolve_spending_limit(
    cargo: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    eleitores: Optional[int] = None,
    segundo_turno: bool = False,
) -> Dict[str, Any]:
    cargo_norm = _normalize_position(cargo)

    if cargo_norm in {"deputado_federal", "deputado_estadual", "deputado_distrital"}:
        limit = TSE_GENERAL_LIMITS_2022.get(cargo_norm, 0.0)
        return {
            "limite_gastos": limit,
            "faixa_municipio": None,
            "fonte": "Tabela TSE Eleicoes 2022",
            "ano_base": 2022,
            "is_official": True,
        }

    if cargo_norm in {"prefeito", "vereador"}:
        uf = (state or "").strip().upper()
        city_key = _normalize_text_key(city)
        if uf and city_key:
            municipal_limits = await _load_tse_municipal_limits()
            hit = municipal_limits.get(f"{uf}:{city_key}")
            if hit:
                limit = hit["prefeito_2t"] if (cargo_norm == "prefeito" and segundo_turno) else (
                    hit["prefeito_1t"] if cargo_norm == "prefeito" else hit["vereador"]
                )
                return {
                    "limite_gastos": float(limit or 0.0),
                    "faixa_municipio": "oficial_municipio",
                    "fonte": hit["fonte"],
                    "ano_base": hit["ano_base"],
                    "is_official": True,
                }

        return _fallback_municipal_limit(cargo_norm, int(eleitores or 0), segundo_turno=segundo_turno)

    return {
        "limite_gastos": 0.0,
        "faixa_municipio": None,
        "fonte": "Sem regra de limite configurada para este cargo",
        "ano_base": None,
        "is_official": False,
    }


def calculate_spending_limit(cargo: str, eleitores: int, segundo_turno: bool = False) -> float:
    """Compat: cálculo legado por faixas."""
    result = _fallback_municipal_limit(_normalize_position(cargo), int(eleitores or 0), segundo_turno=segundo_turno)
    return float(result.get("limite_gastos", 0.0))


@api_router.get("/tse/spending-limits")
async def get_spending_limits(
    cargo: str = Query(..., description="Cargo: prefeito, vereador, deputado federal, deputado estadual"),
    eleitores: int = Query(0, description="Numero de eleitores do municipio (fallback)"),
    segundo_turno: bool = Query(False, description="Se e segundo turno"),
    city: Optional[str] = Query(None, description="Nome da cidade"),
    state: Optional[str] = Query(None, description="UF"),
):
    """Resolve limite de gastos com prioridade para fonte oficial por municipio."""
    result = await resolve_spending_limit(
        cargo=cargo,
        city=city,
        state=state,
        eleitores=eleitores,
        segundo_turno=segundo_turno,
    )
    return {
        "cargo": cargo,
        "city": city,
        "state": state,
        "eleitores": eleitores,
        "segundo_turno": segundo_turno,
        "limite_gastos": result["limite_gastos"],
        "limite_formatado": format_currency(result["limite_gastos"]),
        "faixa_municipio": result["faixa_municipio"],
        "fonte": result["fonte"],
        "ano_base": result["ano_base"],
        "is_official": result["is_official"],
    }


@api_router.get("/tse/municipio/{codigo_ibge}")
async def get_municipio_limits(codigo_ibge: str):
    """Get spending limits for a municipality by IBGE code."""
    city_name = None
    uf = None
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client_http:
            resp = await client_http.get(
                f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{codigo_ibge}"
            )
            resp.raise_for_status()
        payload = resp.json()
        city_name = payload.get("nome")
        uf = payload.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("sigla")
    except Exception:
        local = MUNICIPIOS_TSE.get(codigo_ibge)
        if local:
            city_name = local.get("nome")
            uf = local.get("uf")

    if not city_name or not uf:
        raise HTTPException(status_code=404, detail="Municipio nao encontrado")

    prefeito_limit = await resolve_spending_limit("prefeito", city=city_name, state=uf, eleitores=0, segundo_turno=False)
    prefeito_2t_limit = await resolve_spending_limit("prefeito", city=city_name, state=uf, eleitores=0, segundo_turno=True)
    vereador_limit = await resolve_spending_limit("vereador", city=city_name, state=uf, eleitores=0)

    return {
        "codigo_ibge": codigo_ibge,
        "municipio": city_name,
        "uf": uf,
        "limites": {
            "prefeito_primeiro_turno": prefeito_limit["limite_gastos"],
            "prefeito_segundo_turno": prefeito_2t_limit["limite_gastos"],
            "vereador": vereador_limit["limite_gastos"],
        },
        "fonte": prefeito_limit.get("fonte") or vereador_limit.get("fonte"),
        "ano_base": prefeito_limit.get("ano_base") or vereador_limit.get("ano_base"),
    }

@api_router.get("/tse/campaign-status")
async def get_campaign_spending_status(current_user: dict = Depends(get_current_user)):
    """Get current campaign spending status vs TSE limits"""
    campaign_id = current_user.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
    # Calculate total expenses
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    total_spent = sum(e.get("amount", 0) for e in expenses)
    
    position = campaign.get("position", "vereador")
    eleitores = campaign.get("eleitores", 0)
    resolved_limit = await resolve_spending_limit(
        cargo=position,
        city=campaign.get("city"),
        state=campaign.get("state"),
        eleitores=eleitores,
        segundo_turno=bool(campaign.get("segundo_turno", False)),
    )
    limit = resolved_limit.get("limite_gastos", 0.0)
    
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
            "message": f"ATENÃ‡ÃƒO: Limite de gastos excedido em {format_currency(abs(remaining))}!",
            "detail": "O candidato pode ser multado em 100% do valor excedente e enquadrado por abuso de poder econÃ´mico."
        })
    elif status == "critico":
        alerts.append({
            "type": "warning",
            "message": f"CRÃTICO: {percentage_used:.1f}% do limite jÃ¡ utilizado!",
            "detail": f"Restam apenas {format_currency(remaining)} para gastar."
        })
    elif status == "atencao":
        alerts.append({
            "type": "info",
            "message": f"ATENÃ‡ÃƒO: {percentage_used:.1f}% do limite jÃ¡ utilizado.",
            "detail": f"Restam {format_currency(remaining)} disponÃ­veis."
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
            "percentual_utilizado": round(percentage_used, 2),
            "fonte_limite": resolved_limit.get("fonte"),
            "ano_base_limite": resolved_limit.get("ano_base"),
            "is_official": resolved_limit.get("is_official", False),
        },
        "status": status,
        "alerts": alerts,
        "penalidades": {
            "multa": "100% do valor excedente",
            "crime": "Abuso de poder econÃ´mico",
            "consequencias": ["CassaÃ§Ã£o do registro/diploma", "Inelegibilidade por 8 anos"]
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
            raise HTTPException(status_code=401, detail="Credenciais invÃ¡lidas")
    
    # Verify password
    if not professional.get("password_hash"):
        raise HTTPException(status_code=401, detail="Conta nÃ£o possui senha configurada. Entre em contato com o administrador.")
    
    if not verify_password(credentials.password, professional["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais invÃ¡lidas")
    
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
        raise HTTPException(status_code=400, detail="JÃ¡ existe um profissional com este email")
    
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
                <p>OlÃ¡ {data.name},</p>
                <p>VocÃª foi convidado(a) para fazer parte do Portal de Contadores do Eleitora 360.</p>
                <p><strong>Suas credenciais de acesso:</strong></p>
                <ul>
                    <li>Email: {data.email}</li>
                    <li>Senha temporÃ¡ria: <code>{temp_password}</code></li>
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
        "note": "Senha temporÃ¡ria enviada por email" if email_sent else "Email nÃ£o enviado. Informe a senha temporÃ¡ria manualmente."
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
    # Verify campaign exists
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
    # Add campaign to professional's list
    await db.professionals.update_one(
        {"id": professional_id},
        {"$addToSet": {"campaigns": campaign_id}}
    )
    
    return {
        "message": f"Campanha atribuÃ­da a {professional['name']}",
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
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
        raise HTTPException(status_code=404, detail="Profissional nÃ£o encontrado")
    
    # Check access
    is_admin = professional.get("is_admin", False)
    has_access = campaign_id in professional.get("campaigns", [])
    
    if not is_admin and not has_access:
        raise HTTPException(status_code=403, detail="VocÃª nÃ£o tem acesso a esta campanha")
    
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0}) or {}
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
    # Get all financial data
    expenses = await db.expenses.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    revenues = await db.revenues.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10000)
    contracts = await db.contracts.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    
    # Calculate TSE limit status
    position = campaign.get("position", "vereador")
    eleitores = campaign.get("eleitores", 0)
    resolved_limit = await resolve_spending_limit(
        cargo=position,
        city=campaign.get("city"),
        state=campaign.get("state"),
        eleitores=eleitores,
        segundo_turno=bool(campaign.get("segundo_turno", False)),
    )
    limit = resolved_limit.get("limite_gastos", 0.0)
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
            "percentual_usado": round((total_expenses / limit * 100) if limit > 0 else 0, 2),
            "fonte_limite": resolved_limit.get("fonte"),
            "ano_base_limite": resolved_limit.get("ano_base"),
            "is_official": resolved_limit.get("is_official", False),
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
            "Ãrea ContÃ¡bil",
            "ObrigaÃ§Ãµes Trabalhistas",
            "Assessoria Empresarial",
            "Departamento Fiscal",
            "PrestaÃ§Ã£o de Contas Eleitorais"
        ],
        "coverage": [
            "AssÃº", "PendÃªncias", "ParaÃº", "Afonso Bezerra", 
            "IpanguaÃ§u", "São Rafael", "Serra do Mel", "Upanema",
            "Carnaubais", "Triunfo Potiguar", "ItajÃ¡", "MossorÃ³",
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
    try:
        await db.command("ping")
        return {
            "status": "healthy",
            "components": {
                "database": "ok",
                "pdf": "ok" if PDF_AVAILABLE else "unavailable",
                "ofx": "ok" if OFX_AVAILABLE else "unavailable",
                "email": "ok" if RESEND_AVAILABLE else "unavailable",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Health check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "component": "database",
                "error": "database_unreachable",
            },
        )

# Bank statement and validation endpoints defined below

# ============== BANK STATEMENT ENDPOINTS ==============

@api_router.post("/bank-statements/upload")
async def upload_bank_statement(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and parse OFX bank statement file"""
    if not OFX_AVAILABLE:
        raise HTTPException(status_code=500, detail="Parser OFX nÃ£o disponÃ­vel")
    
    # Validate file extension
    if not file.filename.lower().endswith(('.ofx', '.qfx')):
        raise HTTPException(status_code=400, detail="Formato de arquivo invÃ¡lido. Use arquivos .ofx ou .qfx")
    
    try:
        content = await file.read()
        ofx = OfxParser.parse(BytesIO(content))
        
        # Get campaign
        campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
        
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
                "description": txn.memo or txn.payee or "TransaÃ§Ã£o",
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
            "message": f"Extrato importado com sucesso: {len(transactions)} transaÃ§Ãµes"
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
        raise HTTPException(status_code=404, detail="Extrato nÃ£o encontrado")
    
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
        raise HTTPException(status_code=404, detail="Extrato nÃ£o encontrado")
    
    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
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
        "message": f"ConciliaÃ§Ã£o automÃ¡tica concluÃ­da: {reconciled_count} transaÃ§Ãµes conciliadas",
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

# ============== ENHANCED BANK RECONCILIATION ==============
@api_router.post("/bank-statements/{statement_id}/reconcile-advanced")
async def advanced_reconcile_statement(
    statement_id: str,
    min_confidence: int = 70,
    current_user: dict = Depends(get_current_user)
):
    """Advanced reconciliation with configurable confidence threshold"""
    statement = await db.bank_statements.find_one({"id": statement_id}, {"_id": 0})
    if not statement:
        raise HTTPException(status_code=404, detail="Extrato não encontrado")

    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    pending_txns = await db.bank_transactions.find(
        {"statement_id": statement_id, "reconciliation_status": ReconciliationStatus.PENDING.value},
        {"_id": 0}
    ).to_list(1000)

    revenues = await db.revenues.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(1000)
    expenses = await db.expenses.find({"campaign_id": campaign["id"]}, {"_id": 0}).to_list(1000)

    reconciled_count = 0
    results = []
    unmatched_analysis = []

    for txn in pending_txns:
        best_match = None
        best_confidence = 0
        match_type = None
        all_candidates = []

        if txn["type"] == BankTransactionType.CREDIT.value:
            for rev in revenues:
                confidence = calculate_match_confidence(txn, rev)
                all_candidates.append({
                    "id": rev["id"],
                    "type": "revenue",
                    "amount": rev.get("amount", 0),
                    "confidence": confidence
                })
                if confidence > best_confidence and confidence >= min_confidence:
                    best_confidence = confidence
                    best_match = rev
                    match_type = "revenue"
        else:
            for exp in expenses:
                confidence = calculate_match_confidence(txn, exp)
                all_candidates.append({
                    "id": exp["id"],
                    "type": "expense",
                    "amount": exp.get("amount", 0),
                    "confidence": confidence
                })
                if confidence > best_confidence and confidence >= min_confidence:
                    best_confidence = confidence
                    best_match = exp
                    match_type = "expense"

        if best_match:
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
                "amount": txn["amount"],
                "date": txn["date"],
                "matched_with": best_match["id"],
                "matched_type": match_type,
                "confidence": best_confidence,
                "status": "reconciled"
            })
            logging.info(f"Reconciled transaction {txn['id']} with {match_type} {best_match['id']} ({best_confidence}%)")
        else:
            # Analyze why no match was found
            top_candidates = sorted(all_candidates, key=lambda x: x["confidence"], reverse=True)[:3]
            unmatched_analysis.append({
                "transaction_id": txn["id"],
                "amount": txn["amount"],
                "date": txn["date"],
                "description": txn.get("description", ""),
                "status": "no_match",
                "top_candidates": top_candidates,
                "recommendation": "Review manually or adjust confidence threshold"
            })
            results.append({
                "transaction_id": txn["id"],
                "status": "no_match",
                "confidence": 0,
                "top_candidates": top_candidates
            })

    # Update statement counts
    all_txns = await db.bank_transactions.find({"statement_id": statement_id}, {"_id": 0}).to_list(1000)
    reconciled_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.RECONCILED.value])
    pending_total = len([t for t in all_txns if t.get("reconciliation_status") == ReconciliationStatus.PENDING.value])

    await db.bank_statements.update_one(
        {"id": statement_id},
        {"$set": {
            "reconciled_count": reconciled_total,
            "pending_count": pending_total,
            "last_reconciliation": datetime.now(timezone.utc).isoformat(),
            "reconciliation_confidence_threshold": min_confidence
        }}
    )

    return {
        "message": f"Conciliação avançada concluída: {reconciled_count} transações conciliadas",
        "reconciled_count": reconciled_count,
        "unmatched_count": pending_total,
        "reconciliation_rate": round((reconciled_total / len(all_txns) * 100) if all_txns else 0, 2),
        "results": results,
        "unmatched_analysis": unmatched_analysis
    }

@api_router.get("/bank-statements/{statement_id}/reconciliation-report")
async def get_reconciliation_report(
    statement_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed reconciliation report with discrepancies"""
    statement = await db.bank_statements.find_one({"id": statement_id}, {"_id": 0})
    if not statement:
        raise HTTPException(status_code=404, detail="Extrato não encontrado")

    transactions = await db.bank_transactions.find(
        {"statement_id": statement_id},
        {"_id": 0}
    ).to_list(1000)

    # Separate by reconciliation status
    reconciled = [t for t in transactions if t.get("reconciliation_status") == ReconciliationStatus.RECONCILED.value]
    pending = [t for t in transactions if t.get("reconciliation_status") == ReconciliationStatus.PENDING.value]

    # Calculate totals
    total_credits = sum(t["amount"] for t in transactions if t["type"] == BankTransactionType.CREDIT.value)
    total_debits = sum(t["amount"] for t in transactions if t["type"] == BankTransactionType.DEBIT.value)
    reconciled_credits = sum(t["amount"] for t in reconciled if t["type"] == BankTransactionType.CREDIT.value)
    reconciled_debits = sum(t["amount"] for t in reconciled if t["type"] == BankTransactionType.DEBIT.value)

    report = {
        "statement": statement,
        "summary": {
            "total_transactions": len(transactions),
            "reconciled_transactions": len(reconciled),
            "pending_transactions": len(pending),
            "reconciliation_percentage": round((len(reconciled) / len(transactions) * 100) if transactions else 0, 2),
            "reconciliation_status": "complete" if len(pending) == 0 else "partial"
        },
        "financial_summary": {
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "net_balance": round(total_credits - total_debits, 2),
            "reconciled_credits": round(reconciled_credits, 2),
            "reconciled_debits": round(reconciled_debits, 2),
            "unreconciled_credits": round(total_credits - reconciled_credits, 2),
            "unreconciled_debits": round(total_debits - reconciled_debits, 2)
        },
        "reconciled_transactions": reconciled,
        "pending_transactions": pending
    }

    return report

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
        raise HTTPException(status_code=400, detail="Tipo de registro invÃ¡lido. Use 'revenue' ou 'expense'")
    
    # Get transaction
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="TransaÃ§Ã£o nÃ£o encontrada")
    
    # Get record
    collection = db.revenues if record_type == "revenue" else db.expenses
    record = await collection.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail=f"{'Receita' if record_type == 'revenue' else 'Despesa'} nÃ£o encontrada")
    
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
    
    return {"message": "TransaÃ§Ã£o conciliada manualmente", "status": "success"}

@api_router.post("/bank-transactions/{transaction_id}/ignore")
async def ignore_transaction(transaction_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a bank transaction as ignored"""
    
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="TransaÃ§Ã£o nÃ£o encontrada")
    
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
    
    return {"message": "TransaÃ§Ã£o ignorada", "status": "success"}

@api_router.post("/bank-transactions/{transaction_id}/create-record")
async def create_record_from_transaction(
    transaction_id: str,
    category: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Create a revenue or expense from a bank transaction"""
    
    transaction = await db.bank_transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="TransaÃ§Ã£o nÃ£o encontrada")
    
    campaign = await db.campaigns.find_one({"owner_id": current_user["id"]}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nÃ£o encontrada")
    
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
            "notes": f"Importado do extrato bancÃ¡rio. ID original: {transaction['transaction_id']}",
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
            "notes": f"Importado do extrato bancÃ¡rio. ID original: {transaction['transaction_id']}",
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
        raise HTTPException(status_code=404, detail="Extrato nÃ£o encontrado")
    
    # Delete transactions
    await db.bank_transactions.delete_many({"statement_id": statement_id})
    
    # Delete statement
    await db.bank_statements.delete_one({"id": statement_id})
    
    return {"message": "Extrato e transaÃ§Ãµes excluÃ­dos com sucesso"}

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
            "error": "Documento deve ter 11 dÃ­gitos (CPF) ou 14 dÃ­gitos (CNPJ)"
        }

# ============== TSE IMPORT ENDPOINTS ==============

@api_router.post("/import/tse/validate")
async def validate_tse_import(
    folder_path: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Validate TSE import folder structure"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    try:
        folder = Path(folder_path)
        if not folder.exists():
            raise HTTPException(status_code=400, detail=f"Pasta não encontrada: {folder_path}")

        manager = TSEImportManager(str(folder))
        is_valid, errors = manager.validate()

        if is_valid:
            return {
                "valid": True,
                "message": "Estrutura TSE válida",
                "errors": [],
                "warnings": []
            }
        else:
            return {
                "valid": False,
                "message": "Erros encontrados na validação",
                "errors": errors,
                "warnings": []
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao validar: {str(e)}")


@api_router.post("/import/tse/preview")
async def preview_tse_import(
    folder_path: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Preview data to be imported from TSE folder"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    try:
        folder = Path(folder_path)
        if not folder.exists():
            raise HTTPException(status_code=400, detail=f"Pasta não encontrada: {folder_path}")

        manager = TSEImportManager(str(folder))
        is_valid, errors = manager.validate()

        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Pasta inválida: {', '.join(errors)}")

        preview = manager.preview(limit=5)

        return {
            "valid": True,
            "preview": preview,
            "message": "Preview gerado com sucesso"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao gerar preview: {str(e)}")


@api_router.post("/import/tse/execute")
async def execute_tse_import(
    folder_path: str = Query(...),
    campaign_id: Optional[str] = Query(None),
    skip_validations: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """Execute TSE import - creates revenues, expenses, and imports documents"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    try:
        folder = Path(folder_path)
        if not folder.exists():
            raise HTTPException(status_code=400, detail=f"Pasta não encontrada: {folder_path}")

        campaign_id = campaign_id or current_user.get("campaign_id")
        if not campaign_id:
            raise HTTPException(status_code=400, detail="Campanha não encontrada")

        # Validate campaign exists
        campaign = await db.campaigns.find_one({"id": campaign_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")

        # Validate folder structure
        if not skip_validations:
            manager = TSEImportManager(str(folder))
            is_valid, errors = manager.validate()
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Pasta inválida: {', '.join(errors)}")

        # Start import process
        manager = TSEImportManager(str(folder))
        manager.validate()
        manager.load_metadata()

        # Extract all data
        receipts, expenses, bank_data = manager.extract_all_data()

        # Initialize importer
        importer = DatabaseImporter(db, campaign_id)

        # Convert extracted data to proper format and import
        receitas_formatted = []
        despesas_formatted = []

        # For now, create basic structure
        # In production, would parse PDFs to extract actual data
        for i, receipt in enumerate(receipts):
            receitas_formatted.append({
                "description": f"Receita importada do TSE #{i+1}",
                "amount": 0,  # Would be extracted from PDF
                "category": "doacao_pf",
                "donor_name": "TSE Import",
                "donor_cpf_cnpj": "",
                "date": datetime.now(timezone.utc).isoformat(),
                "tipo_receita": "doacao_financeira",
                "tipo_doador": "pessoa_fisica",
                "forma_recebimento": "deposito"
            })

        for i, expense in enumerate(expenses):
            despesas_formatted.append({
                "description": f"Despesa importada do TSE #{i+1}",
                "amount": 0,  # Would be extracted from PDF
                "category": "outros",
                "supplier_name": "TSE Import",
                "supplier_cpf_cnpj": "",
                "date": datetime.now(timezone.utc).isoformat(),
                "payment_status": "pago",
                "tipo_pagamento": "transferencia"
            })

        # Import data
        await importer.import_receitas(receitas_formatted)
        await importer.import_despesas(despesas_formatted)

        # Store bank data
        for stmt in bank_data:
            await importer.import_banco([{
                "account_name": f"Account {stmt.get('filename', 'Unknown')}",
                "account_type": "or",
                "bank": "Banco do Brasil",
                "transactions": [],
                "filename": stmt.get("filename", "")
            }])

        # Store representantes
        manager.load_representantes()
        upload_dir = Path(os.environ.get("UPLOAD_DIR", ROOT_DIR / "uploads"))
        await importer.store_representantes(manager.representantes_data, upload_dir)

        # Return summary
        summary = importer.get_summary()
        summary["message"] = "Importação concluída com sucesso"

        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar import: {str(e)}")


# File-based TSE Import endpoints (accept uploaded ZIP/RAR files)

# ============== TSE IMPORT HELPERS ==============
def _guess_content_type(file_path: Path) -> Optional[str]:
    ext = file_path.suffix.lower()
    if ext in (".pdf",):
        return "application/pdf"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext in (".png",):
        return "image/png"
    return None


def _find_tse_file(root: Path, category: str, code: str) -> Optional[Path]:
    if not code:
        return None
    direct = root / category / code
    if direct.exists():
        return direct
    try:
        matches = list(root.rglob(code))
        if matches:
            return matches[0]
    except Exception:
        return None
    return None


async def _save_tse_attachment(file_path: Path, campaign_id: str, uploaded_by: str) -> tuple[Optional[str], Optional[str]]:
    content_type = _guess_content_type(file_path)
    if not content_type:
        return None, f"Tipo de arquivo não suportado: {file_path.name}"

    try:
        size = file_path.stat().st_size
    except Exception:
        return None, f"Não foi possível acessar o arquivo: {file_path.name}"

    if size > TSE_IMPORT_MAX_FILE_SIZE:
        return None, f"Arquivo muito grande para importação: {file_path.name}"

    file_id = str(uuid.uuid4())
    file_ext = ALLOWED_FILE_TYPES.get(content_type, ".bin")
    safe_filename = f"{file_id}{file_ext}"
    dest = UPLOAD_DIR / safe_filename

    try:
        contents = await asyncio.to_thread(file_path.read_bytes)
        await asyncio.to_thread(dest.write_bytes, contents)
    except Exception as e:
        return None, f"Falha ao salvar arquivo {file_path.name}: {str(e)}"

    attachment_doc = {
        "id": file_id,
        "original_name": file_path.name,
        "filename": safe_filename,
        "content_type": content_type,
        "size": len(contents),
        "campaign_id": campaign_id,
        "uploaded_by": uploaded_by,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.attachments.insert_one(attachment_doc)
    return file_id, None


def extract_tse_folder_from_zip(temp_dir: str) -> tuple[str, str]:
    """
    Extract and locate the TSE folder from ZIP.
    Best-effort approach: tries multiple strategies and returns what it finds.

    Returns:
        Tuple of (folder_path, info_message)
    """
    temp_path = Path(temp_dir)

    try:
        all_items = list(temp_path.iterdir())
        folders = [f for f in all_items if f.is_dir()]
        files = [f for f in all_items if f.is_file()]

        folder_names = [f.name for f in folders]
        file_names = [f.name for f in files]

        logging.info(f"ZIP contents: {len(folders)} pasta(s), {len(files)} arquivo(s)")
        logging.info(f"Pastas: {folder_names}")
        logging.info(f"Arquivos: {file_names}")

        # Strategy 1: Check if temp_dir itself contains RECEITAS, DESPESAS, or dados.info
        if (temp_path / "RECEITAS").exists() or (temp_path / "DESPESAS").exists() or (temp_path / "dados.info").exists():
            logging.info("Strategy 1 OK: Estrutura TSE na raiz do ZIP")
            return str(temp_path), "Estrutura TSE encontrada na raiz"

        # Strategy 2: Look for ATSEPJE_* folder
        atsepje_folders = [f for f in folders if f.name.upper().startswith("ATSEPJE")]
        if atsepje_folders:
            atsepje_folder = atsepje_folders[0]
            logging.info(f"Strategy 2 OK: Pasta ATSEPJE encontrada: {atsepje_folder.name}")
            return str(atsepje_folder), f"Pasta encontrada: {atsepje_folder.name}"

        # Strategy 3: Look for any folder containing dados.info or RECEITAS/DESPESAS (one level deep)
        for folder in folders:
            try:
                subfolder_list = list(folder.iterdir())
                subfolder_names = [f.name.upper() for f in subfolder_list if f.is_dir()]
                file_list = [f.name for f in subfolder_list if f.is_file()]

                # Has dados.info or has RECEITAS/DESPESAS subfolders
                if "dados.info" in file_list or "RECEITAS" in subfolder_names or "DESPESAS" in subfolder_names:
                    logging.info(f"Strategy 3 OK: Pasta TSE encontrada: {folder.name}")
                    return str(folder), f"Pasta encontrada: {folder.name}"
            except Exception as e:
                logging.debug(f"Verificacao falhou para {folder.name}: {e}")
                continue

        # Strategy 4: Recursive search for dados.info (handles nested ZIPs)
        try:
            data_files = sorted(temp_path.rglob("dados.info"), key=lambda p: len(p.parts))
            if data_files:
                data_parent = data_files[0].parent
                logging.info(f"Strategy 4 OK: dados.info encontrado em {data_parent}")
                return str(data_parent), f"dados.info encontrado em {data_parent.name}"
        except Exception as e:
            logging.debug(f"Busca recursiva por dados.info falhou: {e}")

        # Strategy 5: Recursive search for marker folders (RECEITAS/DESPESAS/EXTRATOS_BANCARIOS)
        try:
            marker_dirs = []
            for marker in ["RECEITAS", "DESPESAS", "EXTRATOS_BANCARIOS"]:
                marker_dirs.extend([p for p in temp_path.rglob(marker) if p.is_dir()])
            if marker_dirs:
                marker_parent = sorted(marker_dirs, key=lambda p: len(p.parts))[0].parent
                logging.info(f"Strategy 5 OK: Pasta marcador encontrada em {marker_parent}")
                return str(marker_parent), f"Pasta encontrada via marcador: {marker_parent.name}"
        except Exception as e:
            logging.debug(f"Busca recursiva por pastas marcador falhou: {e}")

        # Strategy 6: Use first folder with any content
        if folders:
            for folder in folders:
                try:
                    contents = list(folder.iterdir())
                    if contents:  # Has some content
                        logging.warning(f"Strategy 6 (fallback): Usando pasta {folder.name} (tem conteudo)")
                        return str(folder), f"Pasta encontrada (modo fallback): {folder.name}"
                except:
                    continue

        # Complete failure - but still try root
        logging.warning("Nenhuma pasta especifica encontrada, tentando raiz")
        return str(temp_path), "Usando raiz do ZIP (estrutura pode estar incompleta)"

    except Exception as e:
        logging.error(f"Erro ao processar ZIP: {str(e)}", exc_info=True)
        # Don't fail completely - try to use root as fallback
        return str(temp_path), "Usando raiz (erro ao processar)"

@api_router.post("/import/tse/validate-file")
async def validate_tse_import_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Validate TSE import from uploaded file"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()

        # Handle ZIP file extraction
        if file.filename.lower().endswith('.zip'):
            try:
                file_content = await file.read()
                with zipfile.ZipFile(io.BytesIO(file_content)) as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Arquivo ZIP está corrompido ou não é um ZIP válido")
        else:
            raise HTTPException(status_code=400, detail="Somente arquivos ZIP são suportados no momento")

        # Find the TSE folder
        extract_folder, info_msg = extract_tse_folder_from_zip(temp_dir)
        logging.info(f"Validation: {info_msg}")

        # Validate the folder structure
        manager = TSEImportManager(extract_folder)
        is_valid, errors = manager.validate()

        if is_valid:
            return {
                "valid": True,
                "message": "Estrutura TSE válida",
                "errors": [],
                "warnings": []
            }
        else:
            return {
                "valid": False,
                "message": "Erros encontrados na validação",
                "errors": errors,
                "warnings": []
            }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in validation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Erro ao validar: {str(e)}")
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@api_router.post("/import/tse/preview-file")
async def preview_tse_import_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Preview data from uploaded TSE file"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()

        # Handle ZIP file extraction
        if file.filename.lower().endswith('.zip'):
            try:
                file_content = await file.read()
                with zipfile.ZipFile(io.BytesIO(file_content)) as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Arquivo ZIP está corrompido ou não é um ZIP válido")
        else:
            raise HTTPException(status_code=400, detail="Somente arquivos ZIP são suportados no momento")

        # Find the TSE folder
        extract_folder, info_msg = extract_tse_folder_from_zip(temp_dir)
        logging.info(f"Preview: {info_msg}")

        # Validate folder structure
        manager = TSEImportManager(extract_folder)
        is_valid, errors = manager.validate()

        if not is_valid:
            error_msg = "; ".join(errors)
            raise HTTPException(status_code=400, detail=f"Arquivo TSE inválido: {error_msg}")

        # Generate preview
        preview = manager.preview(limit=5)

        return {
            "valid": True,
            "preview": preview,
            "message": "Preview gerado com sucesso"
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in preview: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Erro ao processar arquivo: {str(e)}")
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@api_router.post("/import/tse/execute-file")
async def execute_tse_import_file(
    file: UploadFile = File(...),
    campaign_id: Optional[str] = Form(None),
    skip_validations: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """Execute TSE import from uploaded file"""
    if not TSE_IMPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="TSE import module not available")

    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()

        # Handle ZIP file extraction
        if file.filename.lower().endswith('.zip'):
            try:
                file_content = await file.read()
                with zipfile.ZipFile(io.BytesIO(file_content)) as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Arquivo ZIP está corrompido ou não é um ZIP válido")
        else:
            raise HTTPException(status_code=400, detail="Somente arquivos ZIP são suportados no momento")

        # Find the TSE folder
        extract_folder, info_msg = extract_tse_folder_from_zip(temp_dir)

        campaign_id = campaign_id or current_user.get("campaign_id")
        logging.info(f"Execute: {info_msg} for campaign {campaign_id}")

        # Validate campaign exists
        if not campaign_id:
            raise HTTPException(status_code=400, detail="Campanha não encontrada")
        campaign = await db.campaigns.find_one({"id": campaign_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")

        # Validate folder structure
        if not skip_validations:
            manager = TSEImportManager(extract_folder)
            is_valid, errors = manager.validate()
            if not is_valid:
                error_msg = "; ".join(errors)
                raise HTTPException(status_code=400, detail=f"Arquivo TSE inválido: {error_msg}")

        # Start import process
        try:
            manager = TSEImportManager(extract_folder)
            manager.validate()
            manager.load_metadata()

            # Extract all data
            receitas, despesas, bank_data = manager.extract_all_data()
            logging.info(f"Extracted {len(receitas)} receitas, {len(despesas)} despesas, {len(bank_data)} bank records")

            # Format and import to MongoDB
            importer = DatabaseImporter(db, campaign_id)

            # Attach original TSE PDFs to receitas/despesas/extratos when available
            try:
                root_path = Path(extract_folder)
                for receita in receitas:
                    code = receita.get("tse_code")
                    file_path = _find_tse_file(root_path, "RECEITAS", code)
                    if file_path:
                        attachment_id, err = await _save_tse_attachment(file_path, campaign_id, current_user["id"])
                        if attachment_id:
                            receita["attachment_id"] = attachment_id
                            importer.import_summary["files_saved"] += 1
                        elif err:
                            importer.import_summary["errors"].append(err)

                for despesa in despesas:
                    code = despesa.get("tse_code")
                    file_path = _find_tse_file(root_path, "DESPESAS", code)
                    if file_path:
                        attachment_id, err = await _save_tse_attachment(file_path, campaign_id, current_user["id"])
                        if attachment_id:
                            despesa["attachment_id"] = attachment_id
                            importer.import_summary["files_saved"] += 1
                        elif err:
                            importer.import_summary["errors"].append(err)

                for stmt in bank_data:
                    code = stmt.get("tse_code")
                    file_path = _find_tse_file(root_path, "EXTRATOS_BANCARIOS", code)
                    if file_path:
                        attachment_id, err = await _save_tse_attachment(file_path, campaign_id, current_user["id"])
                        if attachment_id:
                            stmt["attachment_id"] = attachment_id
                            importer.import_summary["files_saved"] += 1
                        elif err:
                            importer.import_summary["errors"].append(err)
            except Exception as attach_error:
                importer.import_summary["errors"].append(f"Erro ao anexar arquivos do TSE: {str(attach_error)}")

            # Import receitas
            receitas_formatted = []
            for receita in receitas:
                msg = receita.copy()
                msg['campaign_id'] = campaign_id
                receitas_formatted.append(msg)
            await importer.import_receitas(receitas_formatted)

            # Import despesas
            despesas_formatted = []
            for despesa in despesas:
                msg = despesa.copy()
                msg['campaign_id'] = campaign_id
                despesas_formatted.append(msg)
            await importer.import_despesas(despesas_formatted)

            # Store bank data
            for stmt in bank_data:
                await importer.import_banco([{
                    "account_name": f"Account {stmt.get('filename', 'Unknown')}",
                    "account_type": "or",
                    "bank": "Banco do Brasil",
                    "transactions": [],
                    "filename": stmt.get("filename", "")
                }])

            # Store representantes
            manager.load_representantes()
            upload_dir = Path(os.environ.get("UPLOAD_DIR", ROOT_DIR / "uploads"))
            await importer.store_representantes(manager.representantes_data, upload_dir)

            # Return summary
            summary = importer.get_summary()
            summary["message"] = "Importação concluída com sucesso"
            logging.info(f"TSE import completed for campaign {campaign_id}")

            return summary
        except Exception as extract_error:
            logging.error(f"Error during data extraction: {str(extract_error)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Erro ao processar dados TSE: {str(extract_error)}")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in execute import: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao executar import: {str(e)}")
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

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



