"""
AI Electoral Assistant - Assistente IA para Campanhas Eleitorais
Integração com GPT-5.2 via Emergent LLM Key
"""
import os
import json
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Emergent LLM Integration
from emergentintegrations.llm.chat import LlmChat, UserMessage

# TSE URLs for scraping electoral rules
TSE_URLS = {
    "legislacao": "https://www.tse.jus.br/legislacao",
    "eleicoes": "https://www.tse.jus.br/eleicoes",
    "prestacao_contas": "https://www.tse.jus.br/eleicoes/eleicoes-2024/prestacao-de-contas",
    "limites_gastos": "https://www.tse.jus.br/comunicacao/noticias",
}

# System prompt for the electoral assistant
SYSTEM_PROMPT = """Você é o Assistente IA Eleitoral do sistema Eleitora 360, especializado em campanhas eleitorais brasileiras.

Seu papel é:
1. AJUDAR candidatos com dúvidas sobre gestão financeira de campanhas
2. ALERTAR sobre limites de gastos, prazos e conformidade legal
3. ANALISAR receitas e despesas para otimização
4. ORIENTAR sobre documentação necessária (contratos, comprovantes)
5. INFORMAR sobre regras do TSE e Justiça Eleitoral

REGRAS IMPORTANTES que você deve sempre lembrar:
- Limite de gastos varia por cargo e município (verificar tabela TSE)
- Doações de pessoas físicas: máximo de 10% dos rendimentos do doador
- Doações de pessoas jurídicas: PROIBIDAS desde 2015
- Prestação de contas: parcial durante campanha, final após eleição
- Contratos de locação precisam de documentação completa (CRLV, CNH, comprovante residência)
- Recursos do Fundo Eleitoral e Fundo Partidário têm regras específicas

FORMATO DAS RESPOSTAS:
- Seja conciso e objetivo
- Use bullet points quando apropriado
- Cite a legislação quando relevante (Lei 9.504/97, Resolução TSE)
- Alerte sobre riscos de irregularidades
- Sugira ações práticas

DADOS DA CAMPANHA serão fornecidos no contexto. Use-os para dar respostas personalizadas.
"""

class ElectoralAssistant:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("EMERGENT_LLM_KEY")
        self.sessions: Dict[str, LlmChat] = {}
    
    def get_or_create_session(self, session_id: str, system_message: str = None) -> LlmChat:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=system_message or SYSTEM_PROMPT
            ).with_model("openai", "gpt-5.2")
        return self.sessions[session_id]
    
    async def chat(
        self, 
        session_id: str, 
        message: str, 
        campaign_context: dict = None,
        chat_history: List[dict] = None
    ) -> str:
        """Send message to assistant with campaign context"""
        
        # Build context message
        context_parts = []
        
        if campaign_context:
            context_parts.append(f"""
DADOS ATUAIS DA CAMPANHA:
- Candidato: {campaign_context.get('candidate_name', 'N/A')}
- Partido: {campaign_context.get('party', 'N/A')}
- Cargo: {campaign_context.get('position', 'N/A')}
- Cidade/UF: {campaign_context.get('city', 'N/A')}/{campaign_context.get('state', 'N/A')}
- Ano: {campaign_context.get('election_year', 'N/A')}
- CNPJ: {campaign_context.get('cnpj', 'N/A')}

RESUMO FINANCEIRO:
- Total Receitas: R$ {campaign_context.get('total_revenues', 0):,.2f}
- Total Despesas: R$ {campaign_context.get('total_expenses', 0):,.2f}
- Saldo Atual: R$ {campaign_context.get('balance', 0):,.2f}
- Limite de Gastos: R$ {campaign_context.get('limite_gastos', 0):,.2f}
- Despesas Pendentes: R$ {campaign_context.get('pending_expenses', 0):,.2f}

ALERTAS:
{self._generate_alerts(campaign_context)}
""")
        
        # Add chat history context if provided
        if chat_history and len(chat_history) > 0:
            history_text = "\nHISTÓRICO RECENTE DA CONVERSA:\n"
            for msg in chat_history[-5:]:  # Last 5 messages
                role = "Usuário" if msg.get("role") == "user" else "Assistente"
                history_text += f"{role}: {msg.get('content', '')[:200]}...\n"
            context_parts.append(history_text)
        
        # Build full message with context
        full_message = ""
        if context_parts:
            full_message = "\n".join(context_parts) + "\n\n"
        full_message += f"PERGUNTA DO CANDIDATO: {message}"
        
        # Get or create chat session
        chat = self.get_or_create_session(session_id)
        
        # Send message
        user_message = UserMessage(text=full_message)
        response = await chat.send_message(user_message)
        
        return response
    
    def _generate_alerts(self, context: dict) -> str:
        """Generate alerts based on campaign data"""
        alerts = []
        
        # Check spending limit
        total_expenses = context.get('total_expenses', 0)
        limite = context.get('limite_gastos', 0)
        if limite > 0:
            percentage = (total_expenses / limite) * 100
            if percentage >= 90:
                alerts.append(f"⚠️ CRÍTICO: Gastos em {percentage:.1f}% do limite!")
            elif percentage >= 75:
                alerts.append(f"⚠️ ATENÇÃO: Gastos em {percentage:.1f}% do limite")
        
        # Check pending expenses
        pending = context.get('pending_expenses', 0)
        if pending > 0:
            alerts.append(f"📋 {context.get('pending_count', 0)} despesa(s) pendente(s) de pagamento (R$ {pending:,.2f})")
        
        # Check missing attachments
        missing_attachments = context.get('contracts_missing_docs', 0)
        if missing_attachments > 0:
            alerts.append(f"📎 {missing_attachments} contrato(s) com documentos pendentes")
        
        # Check balance
        balance = context.get('balance', 0)
        if balance < 0:
            alerts.append(f"🚨 DÉFICIT: Saldo negativo de R$ {abs(balance):,.2f}")
        
        return "\n".join(alerts) if alerts else "✅ Nenhum alerta no momento"
    
    async def analyze_expenses(self, expenses: List[dict], campaign_context: dict) -> str:
        """Analyze expenses and provide optimization suggestions"""
        session_id = f"analysis_{campaign_context.get('campaign_id', 'default')}"
        
        # Group expenses by category
        by_category = {}
        for exp in expenses:
            cat = exp.get('category', 'outros')
            if cat not in by_category:
                by_category[cat] = {'total': 0, 'count': 0}
            by_category[cat]['total'] += exp.get('amount', 0)
            by_category[cat]['count'] += 1
        
        analysis_prompt = f"""
Analise as despesas desta campanha e forneça:
1. Categorias com maior gasto
2. Possíveis otimizações
3. Riscos de irregularidade
4. Sugestões de economia

DESPESAS POR CATEGORIA:
{json.dumps(by_category, indent=2, ensure_ascii=False)}

TOTAL DE DESPESAS: R$ {sum(e.get('amount', 0) for e in expenses):,.2f}
LIMITE DE GASTOS: R$ {campaign_context.get('limite_gastos', 0):,.2f}
"""
        
        return await self.chat(session_id, analysis_prompt, campaign_context)
    
    async def check_compliance(self, campaign_context: dict, contracts: List[dict]) -> str:
        """Check campaign compliance with electoral rules"""
        session_id = f"compliance_{campaign_context.get('campaign_id', 'default')}"
        
        compliance_prompt = f"""
Verifique a conformidade desta campanha com as regras eleitorais:

CONTRATOS ATIVOS: {len(contracts)}
{json.dumps([{
    'titulo': c.get('title'),
    'valor': c.get('value'),
    'tipo': c.get('template_type'),
    'docs_completos': bool(c.get('attachments'))
} for c in contracts], indent=2, ensure_ascii=False)}

Analise:
1. Documentação dos contratos está completa?
2. Valores estão dentro dos limites?
3. Há algum risco de irregularidade?
4. O que precisa ser corrigido?
"""
        
        return await self.chat(session_id, compliance_prompt, campaign_context)


# Singleton instance
assistant = ElectoralAssistant()


async def get_tse_rules_summary() -> str:
    """Fetch and summarize current TSE rules (cached)"""
    # This would normally scrape TSE website, but for now return static rules
    return """
REGRAS ELEITORAIS 2024 (TSE):

1. LIMITES DE GASTOS:
   - Prefeito: varia por município (população)
   - Vereador: definido por cada TRE
   
2. FONTES DE RECURSOS PERMITIDAS:
   - Recursos próprios do candidato
   - Doações de pessoas físicas (máx. 10% da renda)
   - Fundo Especial de Financiamento de Campanha (FEFC)
   - Fundo Partidário
   
3. FONTES PROIBIDAS:
   - Pessoas jurídicas (desde 2015)
   - Entidades estrangeiras
   - Órgãos públicos
   - Concessionárias de serviços públicos
   
4. PRESTAÇÃO DE CONTAS:
   - Parcial: durante a campanha
   - Final: até 30 dias após eleição
   
5. DOCUMENTAÇÃO OBRIGATÓRIA:
   - Contratos de locação: documentos do bem e proprietário
   - Notas fiscais para todas as despesas
   - Recibos eleitorais para doações
"""
