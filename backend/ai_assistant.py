"""
AI Assistant - Flora (ChatGPT integration)
"""
import os
import json
from typing import List, Dict, Any
from openai import AsyncOpenAI

DEFAULT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

SYSTEM_PROMPT = (
    "Voce e a Flora, assistente virtual do sistema Eleitora. "
    "Fale sempre em portugues, com tom feminino, profissional e amigavel. "
    "Responda de forma curta e direta. "
    "Ajude o candidato com receitas, despesas, contratos, pagamentos, relatorios, conformidade e navegacao. "
    "Quando o usuario pedir uma acao, explique o proximo passo de forma objetiva. "
    "Nao use jargoes tecnicos sem explicar."
)

class Assistant:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada")
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = DEFAULT_MODEL

    def _build_messages(
        self,
        message: str,
        campaign_context: Dict[str, Any],
        chat_history: List[Dict[str, Any]] | None = None
    ) -> List[Dict[str, str]]:
        context_text = json.dumps(campaign_context, ensure_ascii=False)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"Contexto da campanha: {context_text}"},
        ]
        if chat_history:
            for item in chat_history[-12:]:
                role = item.get("role")
                content = item.get("content")
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})
        return messages

    async def chat(
        self,
        session_id: str,
        message: str,
        campaign_context: Dict[str, Any],
        chat_history: List[Dict[str, Any]] | None = None
    ) -> str:
        messages = self._build_messages(message, campaign_context, chat_history)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            max_tokens=350,
        )
        return response.choices[0].message.content.strip()

async def get_tse_rules_summary() -> Dict[str, str]:
    return {
        "rules": "Resumo generico de regras eleitorais. Consulte sempre as normas oficiais do TSE.",
        "limits": "Limites variam por cargo e municipio. Verifique o limite vigente no TSE."
    }

assistant = Assistant()
