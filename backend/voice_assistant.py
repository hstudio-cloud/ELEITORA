"""
Voice Assistant - Eleitora
Integração com OpenAI Whisper (STT) e TTS para comandos de voz
"""
import os
import re
import json
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

# Voice configuration
VOICE_CONFIG = {
    "name": "Eleitora",
    "voice": "nova",  # Energetic, upbeat - good for assistant
    "model_tts": "tts-1",  # Fast for real-time
    "model_stt": "whisper-1",
    "speed": 1.0,
    "language": "pt"  # Portuguese
}

# Command patterns for executing actions
COMMAND_PATTERNS = {
    # Financial queries
    "saldo": r"(qual|quanto|meu|ver|mostrar).*(saldo|caixa|dinheiro|disponível)",
    "receitas": r"(qual|quanto|minhas|total|ver|mostrar).*(receitas|doações|arrecadação)",
    "despesas": r"(qual|quanto|minhas|total|ver|mostrar).*(despesas|gastos|custos)",
    "resumo": r"(resumo|visão geral|situação|como está).*(financeiro|campanha|conta)",
    
    # Contract queries
    "contratos": r"(quantos|quais|meus|ver|mostrar|listar).*(contratos|acordos)",
    "pendentes": r"(documentos?|anexos?|contratos?).*(pendentes?|faltando|incompletos?)",
    
    # Actions - Add expense
    "adicionar_despesa": r"(adicionar?|criar?|registrar?|lançar?).*(despesa|gasto|custo).*(?:de\s+)?(?:R\$\s*)?([\d.,]+)",
    
    # Actions - Add revenue  
    "adicionar_receita": r"(adicionar?|criar?|registrar?|lançar?).*(receita|doação).*(?:de\s+)?(?:R\$\s*)?([\d.,]+)",
    
    # Navigation
    "ir_dashboard": r"(ir|abrir|mostrar|navegar).*(dashboard|painel|início)",
    "ir_despesas": r"(ir|abrir|mostrar|navegar).*(despesas|gastos)",
    "ir_receitas": r"(ir|abrir|mostrar|navegar).*(receitas|doações)",
    "ir_contratos": r"(ir|abrir|mostrar|navegar).*(contratos)",
    "ir_relatorios": r"(ir|abrir|mostrar|navegar).*(relatórios|exportar)",
    
    # Help
    "ajuda": r"(ajuda|help|o que você pode|comandos|como funciona)",
    
    # Compliance
    "conformidade": r"(conformidade|irregular|tse|lei|regras|limite)",
    
    # Alerts
    "alertas": r"(alertas?|avisos?|pendências?|vencimentos?)"
}

# Response templates
RESPONSES = {
    "greeting": "Olá! Sou a Eleitora, sua assistente de voz para gestão de campanha. Como posso ajudar?",
    "not_understood": "Desculpe, não entendi o comando. Pode repetir ou dizer 'ajuda' para ver os comandos disponíveis.",
    "help": """Posso ajudar com:
        - Consultar saldo, receitas e despesas
        - Ver contratos e documentos pendentes
        - Adicionar despesas ou receitas por voz
        - Verificar conformidade com TSE
        - Navegar pelo sistema
        Experimente dizer: 'Eleitora, qual é meu saldo?' ou 'Adicionar despesa de 500 reais'""",
    "processing": "Processando seu pedido...",
    "error": "Desculpe, ocorreu um erro ao processar seu pedido. Tente novamente."
}


class VoiceAssistant:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("EMERGENT_LLM_KEY")
        self.stt = OpenAISpeechToText(api_key=self.api_key)
        self.tts = OpenAITextToSpeech(api_key=self.api_key)
        self.config = VOICE_CONFIG
    
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Convert audio to text using Whisper"""
        try:
            # Create a file-like object from bytes
            import io
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename
            
            response = await self.stt.transcribe(
                file=audio_file,
                model=self.config["model_stt"],
                language=self.config["language"],
                response_format="json",
                prompt="Comandos de voz para sistema de gestão de campanha eleitoral. Eleitora é o nome da assistente."
            )
            
            return response.text.strip()
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            raise
    
    async def generate_speech(self, text: str) -> bytes:
        """Convert text to speech using TTS"""
        try:
            # Limit text to 4096 characters
            if len(text) > 4000:
                text = text[:4000] + "..."
            
            audio_bytes = await self.tts.generate_speech(
                text=text,
                model=self.config["model_tts"],
                voice=self.config["voice"],
                speed=self.config["speed"],
                response_format="mp3"
            )
            
            return audio_bytes
        except Exception as e:
            print(f"Error generating speech: {e}")
            raise
    
    async def generate_speech_base64(self, text: str) -> str:
        """Convert text to speech and return as base64"""
        try:
            if len(text) > 4000:
                text = text[:4000] + "..."
            
            audio_base64 = await self.tts.generate_speech_base64(
                text=text,
                model=self.config["model_tts"],
                voice=self.config["voice"],
                speed=self.config["speed"],
                response_format="mp3"
            )
            
            return audio_base64
        except Exception as e:
            print(f"Error generating speech base64: {e}")
            raise
    
    def parse_command(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Parse transcribed text to identify command and extract parameters"""
        text_lower = text.lower()
        
        # Remove "eleitora" prefix if present
        text_lower = re.sub(r"^(oi|olá|hey|ei)?\s*(eleitora)?,?\s*", "", text_lower)
        
        # Check for greeting
        if re.search(r"^(oi|olá|hey|bom dia|boa tarde|boa noite)", text_lower):
            return "greeting", {}
        
        # Check for help
        if re.search(COMMAND_PATTERNS["ajuda"], text_lower):
            return "help", {}
        
        # Check for add expense with amount
        expense_match = re.search(COMMAND_PATTERNS["adicionar_despesa"], text_lower)
        if expense_match:
            amount_str = expense_match.group(3) if expense_match.lastindex >= 3 else None
            if amount_str:
                amount = float(amount_str.replace(".", "").replace(",", "."))
                # Try to extract category
                category = "outros"
                if "publicidade" in text_lower or "propaganda" in text_lower:
                    category = "publicidade"
                elif "transporte" in text_lower or "veículo" in text_lower:
                    category = "transporte"
                elif "alimentação" in text_lower or "comida" in text_lower:
                    category = "alimentacao"
                elif "serviço" in text_lower:
                    category = "servicos_terceiros"
                
                return "add_expense", {"amount": amount, "category": category}
        
        # Check for add revenue with amount
        revenue_match = re.search(COMMAND_PATTERNS["adicionar_receita"], text_lower)
        if revenue_match:
            amount_str = revenue_match.group(3) if revenue_match.lastindex >= 3 else None
            if amount_str:
                amount = float(amount_str.replace(".", "").replace(",", "."))
                return "add_revenue", {"amount": amount}
        
        # Check for navigation commands
        for nav_cmd in ["ir_dashboard", "ir_despesas", "ir_receitas", "ir_contratos", "ir_relatorios"]:
            if re.search(COMMAND_PATTERNS[nav_cmd], text_lower):
                route = nav_cmd.replace("ir_", "/")
                return "navigate", {"route": route}
        
        # Check for query commands
        for query_cmd in ["saldo", "receitas", "despesas", "resumo", "contratos", "pendentes", "conformidade", "alertas"]:
            if re.search(COMMAND_PATTERNS[query_cmd], text_lower):
                return f"query_{query_cmd}", {}
        
        # If no pattern matched, treat as general question for AI
        return "ai_chat", {"message": text}
    
    def format_currency(self, value: float) -> str:
        """Format value as Brazilian currency for speech"""
        if value >= 1000:
            return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " reais"
        return f"{value:.2f}".replace(".", ",") + " reais"


# Singleton instance
voice_assistant = VoiceAssistant()
