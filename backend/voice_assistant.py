"""
Voice Assistant - Eleitora
Integracao com STT/TTS com fallback para SDK OpenAI.
"""
import os
import re
import json
import base64
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

try:
    from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech
    EMERGENT_VOICE_AVAILABLE = True
except ImportError:
    OpenAISpeechToText = None  # type: ignore[assignment]
    OpenAITextToSpeech = None  # type: ignore[assignment]
    EMERGENT_VOICE_AVAILABLE = False

# Voice configuration
VOICE_CONFIG = {
    "name": "Flora",
    "voice": "nova",  # Feminine voice
    "model_tts": "tts-1-hd",  # Higher quality audio
    "model_stt": "whisper-1",
    "speed": 0.85,  # Slower for clarity and diction
    "language": "pt",
}

# Command patterns for executing actions
COMMAND_PATTERNS = {
    "saldo": r"(qual|quanto|meu|ver|mostrar).*(saldo|caixa|dinheiro|dispon[ií]vel)",
    "receitas": r"(qual|quanto|minhas|total|ver|mostrar).*(receitas|doa[cç][oõ]es|arrecada[cç][aã]o)",
    "despesas": r"(qual|quanto|minhas|total|ver|mostrar).*(despesas|gastos|custos)",
    "resumo": r"(resumo|vis[aã]o geral|situa[cç][aã]o|como est[aá]).*(financeiro|campanha|conta)",
    "contratos": r"(quantos|quais|meus|ver|mostrar|listar).*(contratos|acordos)",
    "pendentes": r"(documentos?|anexos?|contratos?).*(pendentes?|faltando|incompletos?)",
    "adicionar_despesa": r"(adicionar?|criar?|registrar?|lan[cç]ar?).*(despesa|gasto|custo).*(?:de\s+)?(?:R\$\s*)?([\d.,]+)",
    "adicionar_receita": r"(adicionar?|criar?|registrar?|lan[cç]ar?).*(receita|doa[cç][aã]o).*(?:de\s+)?(?:R\$\s*)?([\d.,]+)",
    "ir_dashboard": r"(ir|abrir|mostrar|navegar).*(dashboard|painel|in[ií]cio)",
    "ir_despesas": r"(ir|abrir|mostrar|navegar).*(despesas|gastos)",
    "ir_receitas": r"(ir|abrir|mostrar|navegar).*(receitas|doa[cç][oõ]es)",
    "ir_contratos": r"(ir|abrir|mostrar|navegar).*(contratos)",
    "ir_relatorios": r"(ir|abrir|mostrar|navegar).*(relat[oó]rios|exportar)",
    "ajuda": r"(ajuda|help|o que voc[eê] pode|comandos|como funciona)",
    "conformidade": r"(conformidade|irregular|tse|lei|regras|limite)",
    "alertas": r"(alertas?|avisos?|pend[eê]ncias?|vencimentos?)",
}

# Response templates
RESPONSES = {
    "greeting": "Ola! Sou a Flora, sua assistente de voz para gestao de campanha. Como posso ajudar?",
    "not_understood": "Desculpe, nao entendi o comando. Pode repetir ou dizer 'ajuda' para ver os comandos disponiveis.",
    "help": """Posso ajudar com:
        - Consultar saldo, receitas e despesas
        - Ver contratos e documentos pendentes
        - Adicionar despesas ou receitas por voz
        - Verificar conformidade com TSE
        - Navegar pelo sistema
        Experimente dizer: 'Flora, qual e meu saldo?' ou 'Adicionar despesa de 500 reais'""",
    "processing": "Processando seu pedido...",
    "error": "Desculpe, ocorreu um erro ao processar seu pedido. Tente novamente.",
}


class VoiceAssistant:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("EMERGENT_LLM_KEY")
        if EMERGENT_VOICE_AVAILABLE:
            self.stt = OpenAISpeechToText(api_key=self.api_key)
            self.tts = OpenAITextToSpeech(api_key=self.api_key)
        else:
            self.stt = None
            self.tts = None
        self.openai_client = AsyncOpenAI(api_key=self.api_key)
        self.config = VOICE_CONFIG

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Convert audio to text using Whisper"""
        try:
            import io

            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename

            if EMERGENT_VOICE_AVAILABLE and self.stt is not None:
                response = await self.stt.transcribe(
                    file=audio_file,
                    model=self.config["model_stt"],
                    language=self.config["language"],
                    response_format="json",
                    prompt="Comandos de voz para sistema de gestao de campanha eleitoral. Flora e o nome da assistente.",
                )
                return response.text.strip()

            if not self.api_key:
                raise RuntimeError("EMERGENT_LLM_KEY nao configurada para transcricao de voz.")

            response = await self.openai_client.audio.transcriptions.create(
                model=self.config["model_stt"],
                file=audio_file,
                language=self.config["language"],
                prompt="Comandos de voz para sistema de gestao de campanha eleitoral. Flora e o nome da assistente.",
                response_format="json",
            )
            return (response.text or "").strip()
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            raise

    async def generate_speech(self, text: str) -> bytes:
        """Convert text to speech using TTS"""
        try:
            if len(text) > 4000:
                text = text[:4000] + "..."

            if EMERGENT_VOICE_AVAILABLE and self.tts is not None:
                audio_bytes = await self.tts.generate_speech(
                    text=text,
                    model=self.config["model_tts"],
                    voice=self.config["voice"],
                    speed=self.config["speed"],
                    response_format="mp3",
                )
                return audio_bytes

            if not self.api_key:
                raise RuntimeError("EMERGENT_LLM_KEY nao configurada para sintese de voz.")

            response = await self.openai_client.audio.speech.create(
                model=self.config["model_tts"],
                voice=self.config["voice"],
                input=text,
                speed=self.config["speed"],
                response_format="mp3",
            )
            if hasattr(response, "read"):
                return await response.read()
            if hasattr(response, "content"):
                return response.content
            return bytes(response)
        except Exception as e:
            print(f"Error generating speech: {e}")
            raise

    async def generate_speech_base64(self, text: str) -> str:
        """Convert text to speech and return as base64"""
        try:
            audio_bytes = await self.generate_speech(text)
            return base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"Error generating speech base64: {e}")
            raise

    def parse_command(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Parse transcribed text to identify command and extract parameters"""
        text_lower = text.lower()
        text_lower = re.sub(r"^(oi|ola|hey|ei)?\s*(flora|eleitora)?,?\s*", "", text_lower)

        if re.search(r"^(oi|ola|hey|bom dia|boa tarde|boa noite)", text_lower):
            return "greeting", {}
        if re.search(COMMAND_PATTERNS["ajuda"], text_lower):
            return "help", {}

        expense_match = re.search(COMMAND_PATTERNS["adicionar_despesa"], text_lower)
        if expense_match:
            amount_str = expense_match.group(3) if expense_match.lastindex and expense_match.lastindex >= 3 else None
            if amount_str:
                amount = float(amount_str.replace(".", "").replace(",", "."))
                category = "outros"
                if "publicidade" in text_lower or "propaganda" in text_lower:
                    category = "publicidade"
                elif "transporte" in text_lower or "veiculo" in text_lower:
                    category = "transporte"
                elif "alimentacao" in text_lower or "comida" in text_lower:
                    category = "alimentacao"
                elif "servico" in text_lower:
                    category = "servicos_terceiros"
                return "add_expense", {"amount": amount, "category": category}

        revenue_match = re.search(COMMAND_PATTERNS["adicionar_receita"], text_lower)
        if revenue_match:
            amount_str = revenue_match.group(3) if revenue_match.lastindex and revenue_match.lastindex >= 3 else None
            if amount_str:
                amount = float(amount_str.replace(".", "").replace(",", "."))
                return "add_revenue", {"amount": amount}

        for nav_cmd in ["ir_dashboard", "ir_despesas", "ir_receitas", "ir_contratos", "ir_relatorios"]:
            if re.search(COMMAND_PATTERNS[nav_cmd], text_lower):
                route = nav_cmd.replace("ir_", "/")
                return "navigate", {"route": route}

        for query_cmd in ["saldo", "receitas", "despesas", "resumo", "contratos", "pendentes", "conformidade", "alertas"]:
            if re.search(COMMAND_PATTERNS[query_cmd], text_lower):
                return f"query_{query_cmd}", {}

        return "ai_chat", {"message": text}

    def format_currency(self, value: float) -> str:
        """Format value as Brazilian currency for speech"""
        if value >= 1000:
            return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " reais"
        return f"{value:.2f}".replace(".", ",") + " reais"


# Singleton instance
voice_assistant = VoiceAssistant()
