from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from enum import Enum

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

# Create the main app
app = FastAPI(title="Eleitora 360 API", version="1.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

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

class RevenueCreate(BaseModel):
    description: str
    amount: float
    category: RevenueCategory
    donor_name: Optional[str] = None
    donor_cpf_cnpj: Optional[str] = None
    date: str
    receipt_number: Optional[str] = None
    notes: Optional[str] = None

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

class ExpenseCreate(BaseModel):
    description: str
    amount: float
    category: ExpenseCategory
    supplier_name: Optional[str] = None
    supplier_cpf_cnpj: Optional[str] = None
    date: str
    invoice_number: Optional[str] = None
    notes: Optional[str] = None

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

class DashboardStats(BaseModel):
    total_revenues: float
    total_expenses: float
    balance: float
    pending_payments: int
    active_contracts: int
    revenues_by_category: dict
    expenses_by_category: dict
    monthly_flow: List[dict]

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
@api_router.post("/revenues", response_model=RevenueResponse)
async def create_revenue(data: RevenueCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("campaign_id"):
        raise HTTPException(status_code=400, detail="Configure uma campanha primeiro")
    
    revenue_id = str(uuid.uuid4())
    revenue_doc = {
        "id": revenue_id,
        **data.model_dump(),
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
    return contract_doc

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
    if contract.get("locador_assinatura_hash"):
        update_data["status"] = "ativo"
    else:
        update_data["status"] = "assinado_locatario"
    
    await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
    
    # Regenerate HTML with signature
    campaign = await db.campaigns.find_one({"id": current_user["campaign_id"]}, {"_id": 0})
    updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
    html = generate_contract_html(updated_contract, campaign)
    await db.contracts.update_one({"id": contract_id}, {"$set": {"contract_html": html}})
    
    return {"message": "Contrato assinado pelo locatário", "status": update_data["status"]}

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
        if contract.get("locatario_assinatura_hash"):
            update_data["status"] = "ativo"
        else:
            update_data["status"] = "assinado_locador"
        
        await db.contracts.update_one({"id": contract_id}, {"$set": update_data})
        
        # Regenerate HTML
        campaign = await db.campaigns.find_one({"id": contract["campaign_id"]}, {"_id": 0})
        updated_contract = await db.contracts.find_one({"id": contract_id}, {"_id": 0})
        html = generate_contract_html(updated_contract, campaign)
        await db.contracts.update_one({"id": contract_id}, {"$set": {"contract_html": html}})
        
        return {"message": "Contrato assinado pelo locador", "status": update_data["status"]}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token inválido")

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

# ============== HEALTH CHECK ==============
@api_router.get("/")
async def root():
    return {"message": "Eleitora 360 API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
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
