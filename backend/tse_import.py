"""
TSE Financial Disclosure Import System
Handles importing complete TSE electoral financial packages into ELEITORA
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timezone
from enum import Enum
import uuid
import pdfplumber


class ImportValidationError(Exception):
    """Raised when import validation fails"""
    pass


class DataMapper:
    """Maps TSE categories to ELEITORA enums"""

    @staticmethod
    def map_receita_category(tse_category: str) -> str:
        """Map TSE receita category to ELEITORA RevenueCategory"""
        mapping = {
            "doacao_financeira": "doacao_pf",
            "doacao_pessoa_fisica": "doacao_pf",
            "doacao_pf": "doacao_pf",
            "doacao_pessoa_juridica": "doacao_pj",
            "doacao_pj": "doacao_pj",
            "recursos_proprios": "recursos_proprios",
            "fundo_eleitoral": "fundo_eleitoral",
            "fundo_partidario": "fundo_partidario",
            "fundo_partidario_federal": "fundo_partidario",
            "fundo_partidario_estadual": "fundo_partidario",
            "rendimento_aplicacao": "outros",
            "comercializacao": "outros",
            "sobras_campanha": "outros",
            "outros": "outros"
        }
        return mapping.get(tse_category.lower().strip(), "outros")

    @staticmethod
    def map_tipo_receita_enum(tse_tipo: str) -> str:
        """Map TSE tipo receita"""
        valid_tipos = [
            "doacao_financeira",
            "doacao_estimavel",
            "recursos_proprios",
            "fundo_partidario",
            "fundo_eleitoral",
            "comercializacao",
            "rendimento_aplicacao",
            "sobras_campanha",
            "outros"
        ]
        normalized = tse_tipo.lower().strip()
        return normalized if normalized in valid_tipos else "outros"

    @staticmethod
    def map_tipo_doador(donor_type: str) -> str:
        """Map TSE tipo doador"""
        mapping = {
            "pf": "pessoa_fisica",
            "pessoa_fisica": "pessoa_fisica",
            "pj": "pessoa_juridica",
            "pessoa_juridica": "pessoa_juridica",
            "partido": "partido",
            "candidato": "candidato",
            "comite": "comite",
            "fundo_partidario": "fundo_partidario",
            "fundo_eleitoral": "fundo_eleitoral"
        }
        return mapping.get(donor_type.lower().strip(), "pessoa_fisica")

    @staticmethod
    def map_forma_recebimento(forma: str) -> str:
        """Map TSE forma de recebimento"""
        mapping = {
            "pix": "pix",
            "transferencia": "transferencia",
            "deposito": "deposito",
            "cheque": "cheque",
            "especie": "especie",
            "cartao_credito": "cartao_credito",
            "cartao_debito": "cartao_debito",
            "estimavel": "deposito"
        }
        return mapping.get(forma.lower().strip(), "deposito")

    @staticmethod
    def map_despesa_category(tse_category: str) -> str:
        """Map TSE despesa category to ELEITORA ExpenseCategory"""
        mapping = {
            "publicidade": "publicidade",
            "propaganda": "publicidade",
            "material_grafico": "material_grafico",
            "material_grafico_propagandistico": "material_grafico",
            "servicos_terceiros": "servicos_terceiros",
            "servico_diverso": "servicos_terceiros",
            "transporte": "transporte",
            "veiculo": "transporte",
            "carreata": "transporte",
            "alimentacao": "alimentacao",
            "comida": "alimentacao",
            "refeicao": "alimentacao",
            "pessoal": "pessoal",
            "staf": "pessoal",
            "eventos": "eventos",
            "evento": "eventos",
            "outros": "outros"
        }
        return mapping.get(tse_category.lower().strip(), "outros")

    @staticmethod
    def map_tipo_pagamento(pagamento: str) -> str:
        """Map TSE tipo de pagamento"""
        mapping = {
            "pix": "pix",
            "transferencia": "transferencia",
            "boleto": "boleto",
            "cheque": "cheque",
            "especie": "especie",
            "cartao_credito": "cartao_credito",
            "cartao_debito": "cartao_debito",
            "debito_automatico": "debito_automatico",
            "dinheiro": "especie"
        }
        return mapping.get(pagamento.lower().strip(), "transferencia")

    @staticmethod
    def normalize_cpf_cnpj(doc: str) -> str:
        """Normalize and validate CPF/CNPJ"""
        if not doc:
            return ""
        # Remove non-digits
        doc_clean = re.sub(r"\D", "", doc)
        return doc_clean


class PDFExtractor:
    """Extract structured data from TSE PDF files"""

    @staticmethod
    def extract_receita_data(pdf_path: str) -> List[Dict[str, Any]]:
        """Extract revenue/donation data from PDF"""
        receipts = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    tables = page.extract_tables()

                    if tables:
                        for table in tables:
                            # Parse table data
                            for row in table[1:]:  # Skip header
                                if len(row) >= 4:
                                    receipts.append({
                                        "text": text,
                                        "raw_row": row
                                    })
        except Exception as e:
            print(f"Error extracting receipts from {pdf_path}: {e}")

        return receipts

    @staticmethod
    def extract_despesa_data(pdf_path: str) -> List[Dict[str, Any]]:
        """Extract expense data from PDF"""
        expenses = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    tables = page.extract_tables()

                    if tables:
                        for table in tables:
                            for row in table[1:]:  # Skip header
                                if len(row) >= 4:
                                    expenses.append({
                                        "text": text,
                                        "raw_row": row
                                    })
        except Exception as e:
            print(f"Error extracting expenses from {pdf_path}: {e}")

        return expenses

    @staticmethod
    def extract_banco_dados(pdf_path: str) -> Dict[str, Any]:
        """Extract bank statement data from PDF"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page_text = pdf.pages[0].extract_text()
                return {"raw_text": first_page_text}
        except Exception as e:
            print(f"Error extracting bank data from {pdf_path}: {e}")

        return {}


class TSEImportValidator:
    """Validate TSE import folder structure and content"""

    REQUIRED_FOLDERS = ["RECEITAS", "DESPESAS", "EXTRATOS_BANCARIOS"]
    OPTIONAL_FOLDERS = [
        "REPRESENTANTES", "DEMONSTRATIVOS", "CONTRATOS",
        "AVULSOS_OUTROS", "AVAL", "DOACAO_ESTIMAVEL"
    ]

    @staticmethod
    def validate_folder_structure(folder_path: Path) -> Tuple[bool, List[str]]:
        """Validate that TSE folder has correct structure"""
        errors = []

        if not folder_path.exists():
            return False, [f"Pasta não encontrada: {folder_path}"]

        # Check for dados.info
        if not (folder_path / "dados.info").exists():
            errors.append("Arquivo dados.info não encontrado")

        # Check for at least some required folders
        found_folders = [f for f in TSEImportValidator.REQUIRED_FOLDERS
                        if (folder_path / f).exists()]

        if not found_folders:
            errors.append(f"Nenhuma pasta necessária encontrada. Esperado: {', '.join(TSEImportValidator.REQUIRED_FOLDERS)}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_metadata(metadata: Dict) -> Tuple[bool, List[str]]:
        """Validate metadata from dados.info"""
        errors = []

        required_fields = ["electionCode", "candidateName", "candidateCPF"]
        for field in required_fields:
            if field not in metadata:
                errors.append(f"Campo obrigatório faltando: {field}")

        return len(errors) == 0, errors


class TSEImportManager:
    """Main orchestrator for TSE import process"""

    def __init__(self, folder_path: str):
        self.folder_path = Path(folder_path)
        self.metadata = {}
        self.validation_errors = []
        self.receitas_data = []
        self.despesas_data = []
        self.banco_data = []
        self.representantes_data = {}

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate import folder"""
        # Check folder structure
        is_valid, errors = TSEImportValidator.validate_folder_structure(self.folder_path)
        if not is_valid:
            return False, errors

        # Load and validate metadata
        metadata_valid, meta_errors = self.load_metadata()
        if not metadata_valid:
            return False, meta_errors

        validation_errors, validation_warnings = [], []
        is_valid, validation_errors = TSEImportValidator.validate_metadata(self.metadata)

        return is_valid, validation_errors + (validation_warnings if not is_valid else [])

    def load_metadata(self) -> Tuple[bool, List[str]]:
        """Load and parse dados.info"""
        try:
            metadata_path = self.folder_path / "dados.info"
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            return True, []
        except Exception as e:
            return False, [f"Erro ao ler dados.info: {str(e)}"]

    def preview(self, limit: int = 5) -> Dict[str, Any]:
        """Preview data that will be imported"""
        preview = {
            "campaign_info": self.metadata.get("candidateInfo", {}),
            "receitas_count": 0,
            "receitas_sample": [],
            "despesas_count": 0,
            "despesas_sample": [],
            "banco_count": 0,
            "banco_accounts": [],
            "representantes": self.representantes_data,
            "total_amount_income": 0,
            "total_amount_expenses": 0
        }

        # Count and sample receipts
        receitas_folder = self.folder_path / "RECEITAS"
        if receitas_folder.exists():
            pdf_files = list(receitas_folder.glob("*.pdf"))
            preview["receitas_count"] = len(pdf_files)
            preview["receitas_sample"] = [f.name for f in pdf_files[:limit]]

        # Count and sample expenses
        despesas_folder = self.folder_path / "DESPESAS"
        if despesas_folder.exists():
            pdf_files = list(despesas_folder.glob("*.pdf"))
            preview["despesas_count"] = len(pdf_files)
            preview["despesas_sample"] = [f.name for f in pdf_files[:limit]]

        # Count bank statements
        banco_folder = self.folder_path / "EXTRATOS_BANCARIOS"
        if banco_folder.exists():
            pdf_files = list(banco_folder.glob("*.pdf"))
            preview["banco_count"] = len(pdf_files)
            preview["banco_accounts"] = [f.name for f in pdf_files]

        # Load representantes info
        self.load_representantes()
        preview["representantes"] = self.representantes_data

        return preview

    def load_representantes(self):
        """Load accountant and lawyer information"""
        repr_folder = self.folder_path / "REPRESENTANTES"
        if not repr_folder.exists():
            return

        # Look for accountant and lawyer files
        for file_path in repr_folder.glob("*.pdf"):
            filename = file_path.name.lower()
            if "cont" in filename:  # Contador (Accountant)
                self.representantes_data["contador"] = {
                    "file": filename,
                    "path": str(file_path)
                }
            elif "adv" in filename:  # Advogado (Lawyer)
                self.representantes_data["advogado"] = {
                    "file": filename,
                    "path": str(file_path)
                }

    def extract_all_data(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Extract all relevant data from PDFs"""
        receipts = []
        expenses = []
        bank_data = []

        # Extract receipts
        receitas_folder = self.folder_path / "RECEITAS"
        if receitas_folder.exists():
            for pdf in receitas_folder.glob("*.pdf"):
                data = PDFExtractor.extract_receita_data(str(pdf))
                receipts.extend(data)

        # Extract expenses
        despesas_folder = self.folder_path / "DESPESAS"
        if despesas_folder.exists():
            for pdf in despesas_folder.glob("*.pdf"):
                data = PDFExtractor.extract_despesa_data(str(pdf))
                expenses.extend(data)

        # Extract bank data
        banco_folder = self.folder_path / "EXTRATOS_BANCARIOS"
        if banco_folder.exists():
            for pdf in banco_folder.glob("*.pdf"):
                data = PDFExtractor.extract_banco_dados(str(pdf))
                bank_data.append({
                    "filename": pdf.name,
                    "data": data
                })

        return receipts, expenses, bank_data


class DatabaseImporter:
    """Handle import of data into MongoDB"""

    def __init__(self, db, campaign_id: str):
        self.db = db
        self.campaign_id = campaign_id
        self.import_summary = {
            "receitas_created": 0,
            "despesas_created": 0,
            "banco_created": 0,
            "files_saved": 0,
            "errors": []
        }

    async def import_receitas(self, receitas: List[Dict]) -> int:
        """Import revenues to database"""
        count = 0
        try:
            for receita in receitas:
                doc = {
                    "id": str(uuid.uuid4()),
                    "campaign_id": self.campaign_id,
                    "description": receita.get("description", "Importado do TSE"),
                    "amount": float(receita.get("amount", 0)),
                    "category": receita.get("category", "outros"),
                    "donor_name": receita.get("donor_name", ""),
                    "donor_cpf_cnpj": DataMapper.normalize_cpf_cnpj(receita.get("donor_cpf_cnpj", "")),
                    "date": receita.get("date", datetime.now(timezone.utc).isoformat()),
                    "tipo_receita": receita.get("tipo_receita", "outros"),
                    "tipo_doador": receita.get("tipo_doador", "pessoa_fisica"),
                    "forma_recebimento": receita.get("forma_recebimento", "deposito"),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

                result = await self.db.revenues.insert_one(doc)
                if result.inserted_id:
                    count += 1
        except Exception as e:
            self.import_summary["errors"].append(f"Erro ao importar receitas: {str(e)}")

        self.import_summary["receitas_created"] = count
        return count

    async def import_despesas(self, despesas: List[Dict]) -> int:
        """Import expenses to database"""
        count = 0
        try:
            for despesa in despesas:
                doc = {
                    "id": str(uuid.uuid4()),
                    "campaign_id": self.campaign_id,
                    "description": despesa.get("description", "Importado do TSE"),
                    "amount": float(despesa.get("amount", 0)),
                    "category": despesa.get("category", "outros"),
                    "supplier_name": despesa.get("supplier_name", ""),
                    "supplier_cpf_cnpj": DataMapper.normalize_cpf_cnpj(despesa.get("supplier_cpf_cnpj", "")),
                    "date": despesa.get("date", datetime.now(timezone.utc).isoformat()),
                    "payment_status": despesa.get("payment_status", "pago"),
                    "tipo_pagamento": despesa.get("tipo_pagamento", "transferencia"),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

                result = await self.db.expenses.insert_one(doc)
                if result.inserted_id:
                    count += 1
        except Exception as e:
            self.import_summary["errors"].append(f"Erro ao importar despesas: {str(e)}")

        self.import_summary["despesas_created"] = count
        return count

    async def import_banco(self, banco_data: List[Dict]) -> int:
        """Import bank statements to database"""
        count = 0
        try:
            for stmt in banco_data:
                doc = {
                    "id": str(uuid.uuid4()),
                    "campaign_id": self.campaign_id,
                    "account_name": stmt.get("account_name", ""),
                    "account_type": stmt.get("account_type", "or"),
                    "bank": stmt.get("bank", "Banco do Brasil"),
                    "statement_date": datetime.now(timezone.utc).isoformat(),
                    "transactions": stmt.get("transactions", []),
                    "source_file": stmt.get("filename", ""),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

                result = await self.db.bank_statements.insert_one(doc)
                if result.inserted_id:
                    count += 1
        except Exception as e:
            self.import_summary["errors"].append(f"Erro ao importar extratos: {str(e)}")

        self.import_summary["banco_created"] = count
        return count

    async def store_representantes(self, representantes: Dict, upload_dir: Path) -> bool:
        """Store accountant and lawyer information"""
        try:
            for role, info in representantes.items():
                if "path" in info:
                    # Copy file to upload directory
                    source = Path(info["path"])
                    if source.exists():
                        dest = upload_dir / f"representante_{role}_{uuid.uuid4()}.pdf"
                        with open(source, 'rb') as src, open(dest, 'wb') as dst:
                            dst.write(src.read())

                        # Store in database
                        await self.db.campaigns.update_one(
                            {"_id": self.campaign_id},
                            {
                                "$set": {
                                    f"representantes.{role}": {
                                        "file": info.get("file", ""),
                                        "attachment_id": dest.name,
                                        "uploaded_at": datetime.now(timezone.utc).isoformat()
                                    }
                                }
                            }
                        )
            return True
        except Exception as e:
            self.import_summary["errors"].append(f"Erro ao armazenar representantes: {str(e)}")
            return False

    def get_summary(self) -> Dict[str, Any]:
        """Get import summary"""
        return self.import_summary
