# Eleitora 360 - PRD (Product Requirements Document)

## Problem Statement
Construir uma plataforma web de gestão eleitoral e contábil para candidatos brasileiros, funcionando como um ERP eleitoral com foco em:
- Organização financeira da campanha
- Gestão de contratos eleitorais
- Controle de receitas, despesas e pagamentos
- Conformidade com exigências da Justiça Eleitoral (TSE)
- Comunicação e rastreabilidade de ações

## User Choices
- Autenticação: JWT customizada (email/senha)
- Tipos de usuários: Candidatos + Contadores
- Funcionalidades: Completas (financeiro, contratos, dashboard)
- Relatórios: Avançados com exportação TSE (JSON, CSV)
- Tema: Escuro/Moderno

## User Personas

### Candidato
- Precisa visualizar rapidamente o status financeiro da campanha
- Acompanhar receitas e despesas
- Gerenciar contratos com fornecedores
- Exportar relatórios para prestação de contas

### Contador
- Precisa lançar receitas e despesas
- Cadastrar contratos eleitorais
- Controlar pagamentos pendentes
- Gerar relatórios TSE para prestação de contas

## Core Requirements (Static)
1. Autenticação JWT com registro e login
2. Dashboard com KPIs e gráficos
3. CRUD completo de Receitas
4. CRUD completo de Despesas
5. CRUD completo de Contratos
6. CRUD completo de Pagamentos
7. Relatórios TSE com exportação
8. Configuração de campanha

## What's Been Implemented (Date: 2026-01-21)

### Backend (FastAPI + MongoDB)
- ✅ Autenticação JWT (registro, login, verificação de token)
- ✅ CRUD de Campanhas
- ✅ CRUD de Receitas com categorias TSE
- ✅ CRUD de Despesas com categorias TSE
- ✅ CRUD de Contratos com status
- ✅ CRUD de Pagamentos com status
- ✅ Dashboard stats (totais, gráficos por categoria, fluxo mensal)
- ✅ Relatórios TSE (JSON format)

### Frontend (React + Tailwind + Shadcn UI)
- ✅ Tema escuro "Brasília Night Operations"
- ✅ Layout responsivo com sidebar
- ✅ Página de Login
- ✅ Página de Registro
- ✅ Dashboard com KPIs e gráficos (Recharts)
- ✅ Página de Receitas com CRUD
- ✅ Página de Despesas com CRUD
- ✅ Página de Contratos com CRUD
- ✅ Página de Pagamentos com CRUD
- ✅ Página de Relatórios TSE com exportação
- ✅ Página de Configurações (Campanha + Perfil)
- ✅ Rotas protegidas
- ✅ Toast notifications (Sonner)

## Prioritized Backlog

### P0 (MVP - Completed)
- [x] Autenticação
- [x] Dashboard
- [x] Receitas CRUD
- [x] Despesas CRUD
- [x] Contratos CRUD
- [x] Pagamentos CRUD
- [x] Relatórios TSE

### P1 (Next Priority)
- [ ] Exportação de relatórios em PDF
- [ ] Filtros avançados por data
- [ ] Upload de comprovantes (documentos anexos)
- [ ] Notificações de pagamentos vencidos

### P2 (Future)
- [ ] Integração com assinaturas digitais
- [ ] Multi-campanha (contador gerenciando múltiplas campanhas)
- [ ] Dashboard comparativo entre períodos
- [ ] App mobile (PWA)

## Next Tasks List
1. Adicionar exportação PDF nos relatórios TSE
2. Implementar filtros por período nas listagens
3. Adicionar upload de documentos/comprovantes
4. Sistema de alertas para pagamentos próximos do vencimento

---

## Update (2026-02-04): Templates de Contratos e Assinatura Digital

### Novas Funcionalidades Implementadas

#### Templates de Contratos
- 5 tipos de contratos baseados nos modelos TSE:
  - Locação de Bem Móvel
  - Locação de Espaço para Evento
  - Locação de Imóvel
  - Locação de Veículo com Motorista (carro de som, paredão)
  - Locação de Veículo sem Motorista

#### Dados Automatizados
- **Locador (Prestador):** Nome, CPF, RG, endereço completo, profissão, estado civil, email
- **Locatário (Candidato):** Preenchido automaticamente com dados da campanha

#### Campos Específicos por Tipo
- Veículos: Marca, modelo, ano, placa, RENAVAM
- Veículo com motorista: Dados do motorista (CNH), reboque/paredão
- Imóvel: Descrição detalhada, registro
- Espaço para evento: Horário início/fim

#### Sistema de Assinatura Digital
- Geração de link único para assinatura do locador
- Página pública de assinatura (sem login necessário)
- Fluxo de assinatura:
  1. Candidato cria contrato e solicita assinatura
  2. Link é gerado e pode ser enviado por email/WhatsApp
  3. Locador acessa link, lê contrato e assina
  4. Candidato assina como locatário
  5. Contrato fica ativo quando ambos assinam

#### Status de Contratos
- Rascunho
- Aguardando Assinatura
- Assinado pelo Locador
- Assinado pelo Locatário
- Ativo (ambos assinaram)
- Concluído
- Cancelado

### Arquivos Modificados
- /app/backend/server.py - Novos endpoints e geração de HTML
- /app/frontend/src/pages/Contratos.jsx - Interface completa com templates
- /app/frontend/src/pages/AssinarContrato.jsx - Nova página de assinatura
- /app/frontend/src/App.js - Rota /assinar/:token

### Próximos Passos (P1)
- [ ] Integração com envio de email para link de assinatura
- [ ] Integração com GOV.BR para assinatura com certificado digital
- [ ] Geração de PDF do contrato assinado
- [ ] Notificações quando contrato for assinado

---

## Update (2026-02-04): Dados Obrigatórios SPCE e Exportação

### Novas Funcionalidades Implementadas

#### Dados do Candidato (Configurações)
- CNPJ da Campanha
- CPF do Candidato
- Número do Candidato
- Título de Eleitor
- Endereço completo da campanha

#### Contas Bancárias (3 obrigatórias TSE)
1. **Conta de Doação (Outros Recursos)** - doações PF e recursos próprios
2. **Conta do Fundo Partidário** - recursos do partido
3. **Conta FEFEC** - Fundo Especial de Financiamento de Campanha

#### Dados de Referência
- Lista de 34 partidos políticos brasileiros com siglas e números
- Lista de 27 estados com regiões (Norte, Nordeste, Sul, etc.)
- Lista de 18 bancos brasileiros
- Lista de 11 cargos eletivos

#### Exportação SPCE
- Layout DOACINTE (Doações pela Internet)
- Arquivo .TXT no formato exigido pela Justiça Eleitoral
- Exportação de doações PF e recursos próprios

### Endpoints Adicionados
- GET /api/reference/partidos
- GET /api/reference/estados
- GET /api/reference/bancos
- GET /api/reference/cargos
- GET /api/export/spce-doacoes

### Próximos Passos (P1)
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática
- [ ] Mais layouts SPCE (despesas, contratos)
- [x] Validação de CPF/CNPJ

---

## Update (2026-02-05): Filtros por Período, Alertas e Exportação PDF

### Funcionalidades Implementadas

#### Filtros por Período
- Página de Receitas: filtros de data início e fim
- Página de Despesas: filtros de data início e fim
- Botão "Limpar filtros" para resetar
- Filtros combinam com busca por texto

#### Sistema de Alertas de Pagamento
- Endpoint GET /api/payments/alerts?days_ahead=7
- Dashboard exibe alertas de pagamentos próximos ao vencimento
- Destaque visual para pagamentos atrasados (vermelho)
- Destaque para pagamentos urgentes (amarelo)
- Badge com contagem de atrasados

#### Exportação PDF
- Botão "Exportar PDF" na página de Relatórios
- Utiliza biblioteca reportlab
- Gera relatório completo com receitas e despesas

#### Validação de CPF/CNPJ
- POST /api/validate/cpf?cpf=12345678909
- POST /api/validate/cnpj?cnpj=11222333000181
- Validação com dígitos verificadores
- Retorna CPF/CNPJ formatado

#### Assinatura com Validação Facial
- Captura de selfie via webcam
- Armazenamento da imagem para validação
- Página de assinatura atualizada com interface de câmera

### Correções de Backend
- Reordenação de rotas para evitar conflito /payments/alerts vs /payments/{id}

### Arquivos Modificados
- /app/backend/server.py - Reordenação de rotas, endpoints de validação
- /app/frontend/src/pages/Dashboard.jsx - Seção de alertas
- /app/frontend/src/pages/Receitas.jsx - Filtros por período
- /app/frontend/src/pages/Despesas.jsx - Filtros por período
- /app/frontend/src/pages/Relatorios.jsx - Botão de exportação PDF
- /app/frontend/src/pages/AssinarContrato.jsx - Validação facial

### Testes
- 100% de sucesso em testes de backend
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_2.json

### Próximas Tarefas (P1)
- [ ] Integração com Resend para envio de e-mail automático
- [ ] Geração automática de PDF do contrato assinado
- [ ] Mais layouts de exportação SPCE (despesas, contratos)
- [ ] Importação de extratos bancários

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil para assinatura certificada
- [ ] Conciliação bancária automática
- [x] Upload de anexos em documentos

---

## Update (2026-02-05): Upload de Comprovantes e Parcelas de Contratos

### Funcionalidades Implementadas

#### Upload de Comprovantes (JPEG, PNG, PDF)
- **Receitas:** POST /api/revenues/{id}/attach-receipt
- **Despesas:** POST /api/expenses/{id}/attach-receipt (muda status para "pago")
- **Contratos:** POST /api/contracts/{id}/attach
- Validação de tipos de arquivo: apenas JPEG, PNG, PDF aceitos
- Limite de 10MB por arquivo

#### Sistema de Parcelas para Contratos
- Número de parcelas configurável (1 a 4)
- Geração automática de despesas com status "pendente"
- Cálculo automático de valor por parcela
- Distribuição de datas de vencimento (início e fim do contrato)
- Opção de desativar geração de despesas

#### Status de Pagamento em Despesas
- Novo campo payment_status: "pendente" ou "pago"
- Coluna de status na tabela com badges coloridos
- Botão de upload para despesas pendentes
- Mudança automática para "pago" ao anexar comprovante

#### Dialog de Despesas do Contrato
- Resumo de valores: Total Pago / Total Pendente
- Lista de parcelas com status individual
- Acessível via botão $ na linha do contrato

### Endpoints Criados
- POST /api/expenses/{id}/attach-receipt
- POST /api/revenues/{id}/attach-receipt
- POST /api/contracts/{id}/attach
- GET /api/contracts/{id}/expenses

### Modelos Atualizados
- ExpenseCreate: payment_status, contract_id
- ContractCreate: num_parcelas, gerar_despesas, parcelas_config

### Testes
- 100% de sucesso em testes de backend (30/30)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_3.json

### Próximas Tarefas (P1)
- [ ] Integração com Resend para envio de e-mail automático
- [ ] Geração automática de PDF do contrato assinado

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil para assinatura certificada
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática

---

## Update (2026-02-05): Exportação SPCE ZIP Completa

### Funcionalidades Implementadas

#### Exportação SPCE em formato ZIP
- Endpoint GET /api/export/spce-zip
- Estrutura completa com 14 pastas obrigatórias:
  - RECEITAS, DESPESAS, DEMONSTRATIVOS
  - EXTRATOS_BANCARIOS, EXTRATO_PRESTACAO
  - NOTAS_EXPLICATIVAS, REPRESENTANTES
  - ASSUNCAO_DIVIDAS, SOBRAS_CAMPANHA
  - AVULSOS_OUTROS, AVULSOS_SPCE, COMERCIALIZACAO
  - DEVOLUCAO_RECEITAS, SIGILOSO_SPCE
- Arquivo dados.info com metadados JSON
- Geração automática de arquivos PDF para receitas e despesas
- Inclusão de comprovantes anexados nas pastas corretas
- Demonstrativos gerados automaticamente

#### Integração Resend para E-mail
- Endpoint POST /api/email/send-signature-request
- Template HTML para solicitação de assinatura
- Link de assinatura com token JWT
- Envio em background (não bloqueia request)
- **Requer RESEND_API_KEY em .env para funcionar**

### Arquivos Modificados
- /app/backend/server.py - Endpoint /api/export/spce-zip
- /app/frontend/src/pages/Relatorios.jsx - Botão "Exportar Pacote ZIP Completo"

### Testes
- 100% de sucesso em testes de backend (41/41)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_4.json

### Próximas Tarefas (P1)
- [ ] Geração automática de PDF do contrato assinado
- [x] Configurar RESEND_API_KEY para ativar envio de e-mails

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil para assinatura certificada
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática

---

## Update (2026-02-05): Sistema de Anexos Obrigatórios + Resend

### Funcionalidades Implementadas

#### Sistema de Anexos Obrigatórios por Tipo de Contrato
Cada tipo de contrato tem documentos específicos obrigatórios:

**Locação de Veículo (com/sem motorista):**
- Documento do Veículo (CRLV)
- Documento do Proprietário (RG/CPF)
- CNH do Motorista/Proprietário
- Comprovante de Residência
- Comprovante de Pagamento (opcional)

**Locação de Imóvel:**
- Documento do Imóvel (Escritura/Contrato)
- Documento do Proprietário/Locador
- Comprovante de Residência
- Comprovante de Pagamento (opcional)

**Bem Móvel / Espaço de Evento:**
- Documento do Proprietário
- Comprovante de Residência
- Documento do Bem/Espaço (se houver)
- Comprovante de Pagamento (opcional)

#### Endpoints Criados
- GET /api/contracts/{id}/required-attachments - Lista anexos com status
- POST /api/contracts/{id}/attachments/{key} - Upload de anexo específico
- GET /api/contracts/attachment-types - Lista tipos disponíveis

#### Lógica de Pagamento Automático
Quando o "comprovante_pagamento" é anexado, todas as despesas pendentes do contrato são automaticamente marcadas como "pago".

#### Integração Resend Configurada
- RESEND_API_KEY configurada em /app/backend/.env
- Endpoint POST /api/email/send-signature-request funcionando
- Template HTML para e-mail de solicitação de assinatura

### Frontend Atualizado
- Dialog de "Anexos Obrigatórios do Contrato" com:
  - Barra de progresso (X/Y enviados)
  - Lista de documentos com status (pendente/enviado)
  - Botões de Upload/Ver/Substituir
  - Alerta visual para anexos pendentes
- Botão de anexos na tabela de contratos

### Testes
- 100% de sucesso em testes de backend (13/13)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_5.json

### Próximas Tarefas (P1)
- [ ] Geração automática de PDF do contrato assinado

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática

---

## Update (2026-02-06): Assistente IA Eleitoral com GPT-5.2

### Funcionalidades Implementadas

#### Assistente IA Eleitoral
Chatbot inteligente integrado com GPT-5.2 via Emergent LLM Key que:
- Analisa dados da campanha em tempo real (receitas, despesas, contratos)
- Alerta sobre limites de gastos e prazos
- Verifica conformidade com regras do TSE
- Sugere otimizações de gastos
- Responde dúvidas sobre legislação eleitoral

#### Endpoints Criados
- POST /api/ai/chat - Chat com o assistente (com contexto da campanha)
- GET /api/ai/chat/history - Histórico de conversas
- DELETE /api/ai/chat/history - Limpar histórico
- POST /api/ai/analyze-expenses - Análise detalhada de despesas
- POST /api/ai/check-compliance - Verificação de conformidade
- GET /api/ai/tse-rules - Regras do TSE

#### Arquivos Criados
- /app/backend/ai_assistant.py - Classe ElectoralAssistant com integração GPT-5.2
- /app/frontend/src/pages/Assistente.jsx - Interface de chat

#### Interface do Frontend
- Página de chat com histórico de mensagens
- Ações rápidas: Resumo financeiro, Verificar conformidade, Analisar despesas, Documentos pendentes
- Menu lateral com destaque "Novo" para o Assistente IA
- Alertas em tempo real sobre pendências

#### Capacidades do Assistente
- Resumo financeiro personalizado (total receitas, despesas, saldo)
- Verificação de conformidade com Lei 9.504/97 e Resoluções TSE
- Análise de despesas por categoria
- Alerta sobre documentos pendentes em contratos
- Orientações sobre limites de gastos por cargo

### Testes
- 100% de sucesso em testes de backend (18/18)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_6.json

### Próximas Tarefas (P1)
- [x] Geração automática de PDF do contrato assinado
- [ ] Integração com web scraping do TSE para normas atualizadas

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática

---

## Update (2026-02-06): Assistente de Voz "Eleitora"

### Funcionalidades Implementadas

#### Assistente de Voz com OpenAI Whisper e TTS
Nome da assistente: **Eleitora**
- Speech-to-Text via OpenAI Whisper
- Text-to-Speech via OpenAI TTS (voz "nova")
- Execução de comandos por voz
- Resposta com áudio sintetizado

#### Comandos de Voz Suportados
- **Consultas:** "Qual é meu saldo?", "Minhas despesas", "Contratos pendentes"
- **Ações:** "Adicionar despesa de 500 reais em publicidade"
- **Navegação:** "Ir para despesas", "Mostrar relatórios"
- **Compliance:** "Verificar conformidade", "Meus alertas"
- **Fallback:** Perguntas complexas vão para a IA do GPT-5.2

#### Endpoints Criados
- POST /api/voice/command - Pipeline completo (transcrição → comando → ação → resposta TTS)
- POST /api/voice/transcribe - Apenas transcrição de áudio
- POST /api/voice/speak - Apenas síntese de voz
- GET /api/voice/greeting - Saudação da Eleitora

#### Arquivos Criados
- /app/backend/voice_assistant.py - Classe VoiceAssistant
- /app/frontend/src/pages/Assistente.jsx - Interface com gravação de voz

#### Interface do Frontend
- Botão grande "Falar" para gravação
- Indicador "Eleitora falando..." durante reprodução
- Toggle Voz Ativa/Desativada
- Exemplos de comandos de voz
- Integração com chat de texto

### Testes
- 100% de sucesso em testes de backend (11/11)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_7.json

### Próximas Tarefas (P1)
- [ ] Aba Contador/Advogado com sistema de autorização
- [ ] Integração com Ativa Contabilidade
- [ ] Integração bancária (Banco do Brasil)

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática

---

## Update (2026-02-06): Portal do Contador + Limites TSE

### Funcionalidades Implementadas

#### Portal do Contador (Ativa Contabilidade)
Sistema completo de acesso para contadores e advogados:

**Login do Contador:**
- Acesso via /contador/login
- Conta admin: diretoria@ativacontabilidade.cnt.br (senha: ativa2024)
- Token JWT independente do sistema de candidatos
- Criação automática do admin no primeiro login

**Dashboard do Contador:**
- Visão consolidada de todas as campanhas
- KPIs agregados: Total Receitas, Despesas, Saldo
- Lista de profissionais da equipe
- Filtros e busca por campanhas

**Gestão de Equipe:**
- Convite de novos contadores/advogados via email
- Atribuição de campanhas a profissionais
- Controle de acesso por campanha
- Integração com Resend para envio de convites

#### Sistema de Limites de Gastos TSE
Implementação completa dos limites eleitorais:

**Cálculo Automático:**
- Baseado na Portaria TSE 593/2024
- Limites por cargo (Prefeito/Vereador)
- Faixas por número de eleitores do município
- Suporte a primeiro e segundo turno

**Faixas de Eleitorado:**
| Faixa | Eleitores | Limite Prefeito 1T |
|-------|-----------|-------------------|
| Micro | 0-10k | R$ 159.850,76 |
| Pequeno | 10k-50k | R$ 500.000,00 |
| Médio | 50k-200k | R$ 2.000.000,00 |
| Grande | 200k-1M | R$ 10.000.000,00 |
| Metrópole | 1M+ | R$ 67.200.000,00 |

**Card de Limite no Dashboard:**
- Exibe limite TSE da campanha
- Mostra total gasto e disponível
- Barra de progresso com % utilizado
- Alertas automáticos:
  - Verde (OK): < 75%
  - Amarelo (Atenção): 75-90%
  - Laranja (Crítico): 90-100%
  - Vermelho (Excedido): > 100%

**Penalidades Informadas:**
- Multa de 100% do valor excedente
- Abuso de poder econômico
- Cassação do registro/diploma
- Inelegibilidade por 8 anos

#### Endpoints Criados
- GET /api/tse/spending-limits - Calcula limite por cargo/eleitores
- GET /api/tse/municipio/{codigo_ibge} - Limites por município
- GET /api/tse/campaign-status - Status de gastos da campanha atual
- POST /api/admin/contador/login - Login do contador
- POST /api/admin/contador/invite - Convite de profissional
- GET /api/admin/contador/professionals - Lista profissionais
- GET /api/admin/contador/all-campaigns - Lista todas campanhas
- POST /api/admin/contador/assign-campaign - Atribui campanha
- GET /api/contador/my-campaigns - Campanhas do contador logado
- GET /api/contador/campaign/{id}/details - Detalhes da campanha

#### Arquivos Criados
- /app/frontend/src/pages/ContadorLogin.jsx - Login do contador
- /app/frontend/src/pages/ContadorDashboard.jsx - Dashboard do contador

#### Arquivos Modificados
- /app/backend/server.py - Novos endpoints TSE e Contador
- /app/frontend/src/App.js - Rotas /contador/*
- /app/frontend/src/pages/Dashboard.jsx - Card de Limite TSE
- /app/frontend/src/pages/Login.jsx - Link para portal contador

### Testes
- 100% de sucesso em testes de backend (18/18)
- 100% de sucesso em testes de frontend
- Arquivo: /app/test_reports/iteration_8.json

### Credenciais de Teste
| Tipo | Email | Senha |
|------|-------|-------|
| Candidato | admin@test.com | test123 |
| Contador Admin | diretoria@ativacontabilidade.cnt.br | ativa2024 |

### Próximas Tarefas (P1)
- [ ] Integração PIX Banco do Brasil (aguardando credenciais)
- [ ] Geração automática de PDF do contrato assinado

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [ ] Importação de extratos bancários (OFX)
- [ ] Conciliação bancária automática
- [ ] Role de admin para contadores gerenciarem equipe

---
