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

---

## Update (2026-02-06): Interface PIX + PDF de Contratos

### Funcionalidades Implementadas

#### Interface PIX Completa na Aba de Pagamentos
- **Duas Tabs:** "Pagamentos" (tradicional) e "PIX" 
- **Cards de Resumo:**
  - PIX Agendados (azul)
  - PIX Executados (verde)  
  - Total de PIX
- **Formulário "Novo PIX":**
  - Nome do Destinatário
  - CPF/CNPJ do Destinatário
  - Tipo de Chave PIX (CPF, CNPJ, Email, Telefone, Aleatória)
  - Chave PIX
  - Valor (R$)
  - Data de Agendamento
  - Descrição
  - Vincular a Despesa (opcional)
- **Tabela de PIX:**
  - Lista todos os pagamentos PIX
  - Status: Agendado, Processando, Executado, Falhou, Cancelado
  - Botão para simular execução
  - Modal de detalhes

#### API PIX Endpoints
- POST /api/pix/payment - Criar pagamento PIX
- GET /api/pix/payments - Listar pagamentos
- GET /api/pix/payment/{id} - Buscar PIX específico
- POST /api/pix/simulate-execution/{id} - Simular execução
- GET /api/pix/bank-info - Info do Banco do Brasil

**Nota:** Integração é SIMULADA. Credenciais do BB necessárias para operação real.

#### Geração Automática de PDF do Contrato
- PDF gerado automaticamente quando ambas as partes assinam
- Inclui:
  - Cabeçalho da campanha
  - Título do contrato
  - Conteúdo completo
  - Seção de assinaturas digitais com hashes
  - Rodapé com ID e timestamp

#### API PDF Endpoints
- GET /api/contracts/{id}/pdf - Gerar PDF do contrato
- GET /api/contracts/{id}/download-signed-pdf - Download PDF assinado

### Testes
- Backend: 100% (22/22 testes)
- Frontend: 100%
- Arquivo: /app/test_reports/iteration_9.json

### Arquivos Modificados
- /app/frontend/src/pages/Pagamentos.jsx - Interface PIX completa
- /app/backend/server.py - APIs PIX e PDF automático

### Bug Corrigido
- SelectItem com valor vazio no dropdown de despesas (Pagamentos.jsx linha 702)

---

---

## Update (2026-02-06): Integração BB PIX Real + Layouts SPCE Expandidos

### Integração Banco do Brasil PIX

#### Configuração
Credenciais configuradas em `/app/backend/.env`:
- BB_APP_KEY: Chave do desenvolvedor
- BB_CLIENT_ID: ID do cliente OAuth
- BB_CLIENT_SECRET: Secret do cliente OAuth
- BB_ENVIRONMENT: homologacao

#### Classe BancoDoBrasilPIX
Implementação completa da integração:
- **get_access_token()**: Autenticação OAuth2 com fallback
- **create_pix_payment()**: Criação de cobranças PIX (cobv)
- **check_pix_status()**: Consulta de status
- **list_pix_received()**: Lista PIX recebidos

#### Endpoints PIX Atualizados
- POST /api/pix/payment - Cria PIX (usa BB real quando disponível)
- GET /api/pix/check-status/{id} - Consulta status no BB
- POST /api/pix/execute/{id} - Executa PIX agendado
- GET /api/pix/bank-info - Info da integração (integration_available: true)

#### Funcionalidades
- Geração de PIX Copia e Cola
- Geração de QR Code
- Consulta de status em tempo real
- Fallback para modo simulado se OAuth falhar

### Layouts SPCE Expandidos

#### SPCE DESPAGTOS (Despesas)
Formato oficial conforme Resolução TSE 23.607/2019:
- Header: versao|tipo|cnpj|uf|ano
- Detail: versao|tipo|seq|data|cpf_cnpj|nome|valor|categoria|descricao|doc_fiscal
- Trailer: versao|tipo|total_registros|valor_total

**Categorias de Despesas (15 tipos):**
- 101: Propaganda
- 102: Pessoal
- 103: Transporte
- 104: Material de Expediente
- 105: Alimentação
- 106: Combustível
- 107: Locação de Veículo
- 108: Locação de Imóvel
- 109: Eventos
- 110: Serviços de Terceiros
- 111: Água/Luz/Telefone
- 112: Taxas Bancárias
- 113: Produção Audiovisual
- 114: Impulsionamento
- 199: Outras Despesas

#### SPCE CONTRATOS
- Tipo de contrato com código
- Status de assinatura (S/N)
- Período de vigência
- Valor e parcelas

**Tipos de Contrato (13 tipos):**
- 01: Locação Veículo c/ Motorista
- 02: Locação Veículo s/ Motorista
- 03: Locação Imóvel para Comitê
- 04: Locação Imóvel para Evento
- 05: Serviços Gráficos
- 06: Publicidade
- 07: Pesquisa
- 08: Jurídico
- 09: Contábil
- 10: TI
- 11: Produção Audiovisual
- 12: Impulsionamento
- 99: Outros

#### Endpoints SPCE
- GET /api/export/spce-despagtos - Layout DESPAGTOS (TXT)
- GET /api/export/spce-contratos - Layout CONTRATOS (TXT)
- GET /api/export/spce-despesas-pdf - Relatório despesas (PDF)
- GET /api/export/spce-contratos-pdf - Relatório contratos (PDF)
- GET /api/export/spce-categorias - Lista categorias disponíveis

### Testes
- Backend: 100% (8/8 testes)
- Frontend: 100%
- Arquivo: /app/test_reports/iteration_10.json

### Requisitos para Exportação SPCE
- **CNPJ da campanha** deve estar configurado
- Configurar em: Dashboard > Configurações > Dados da Campanha

---

## Update (2026-03-05): Campos SPCE Completos em Receitas e Despesas

### Funcionalidades Implementadas

#### Campos SPCE em Receitas
Frontend atualizado com campos de conformidade SPCE:
- **Tipo de Receita**: Doação Financeira, Doação Estimável, Recursos Próprios, Fundo Partidário, etc.
- **Tipo de Doador**: Pessoa Física, Pessoa Jurídica, Partido, Candidato, etc.
- **Forma de Recebimento**: PIX, Transferência Bancária, Depósito, Cheque, etc.
- **Título de Eleitor do Doador**: Campo condicional (aparece apenas para Pessoa Física)

#### Campos SPCE em Despesas
Frontend atualizado com campos de conformidade SPCE:
- **Forma de Pagamento**: PIX, Transferência Bancária, Boleto, Cheque, etc.
- **Nº Documento Fiscal (NF)**: Campo para número da nota fiscal
- **Data do Pagamento**: Data efetiva do pagamento

#### Botão Download Recibo Eleitoral
- Botão de download em cada linha da tabela de Receitas
- Endpoint: GET /api/revenues/{revenue_id}/recibo-pdf
- Gera PDF formatado com dados da receita e doador

#### Correção de Bug
- Corrigido erro de import em ConformidadeTSE.jsx (FileContract → FileSignature)

### Arquivos Modificados
- /app/frontend/src/pages/Receitas.jsx - Campos SPCE e botão download recibo
- /app/frontend/src/pages/Despesas.jsx - Campos SPCE (tipo_pagamento, etc.)
- /app/frontend/src/pages/ConformidadeTSE.jsx - Corrigido import de ícone

### Testes
- Backend: 100% (14/14 testes)
- Frontend: 100% (23/23 testes)
- Arquivo: /app/test_reports/iteration_11.json

### Próximas Tarefas (P1)
- [ ] Atualizar Relatorios.jsx com controles UI para exportação SPCE expandida
- [ ] Investigar/corrigir expiração de sessão se reportada pelo usuário

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [x] Importação de extratos bancários (OFX)
- [x] Conciliação bancária automática
- [ ] Portal personalizado Ativa Contabilidade

---

## Update (2026-03-05): Importação OFX, Conciliação Bancária e Validação CPF/CNPJ

### Funcionalidades Implementadas

#### 1. Importação de Extratos Bancários OFX
Nova página dedicada "Extratos Bancários" em `/extratos`:
- Upload de arquivos OFX/QFX (Open Financial Exchange)
- Parser usando biblioteca `ofxparse`
- Preview das transações importadas
- Armazenamento de transações no MongoDB
- Listagem de extratos com totais de crédito/débito
- Progress bar de conciliação

**Endpoints:**
- `POST /api/bank-statements/upload` - Upload de arquivo OFX
- `GET /api/bank-statements` - Lista todos os extratos
- `GET /api/bank-statements/{id}` - Detalhes do extrato com transações
- `DELETE /api/bank-statements/{id}` - Excluir extrato

#### 2. Conciliação Bancária Automática
Sistema de match automático entre transações bancárias e receitas/despesas:
- **Algoritmo de Match:**
  - Valor: 40% peso (match exato = 40pts, ±5% = 30pts, ±10% = 15pts)
  - Data: 30% peso (mesmo dia = 30pts, ±1 dia = 25pts, ±3 dias = 15pts)
  - Descrição: 30% peso (fuzzy matching por palavras comuns)
- Threshold de confiança: 70% para auto-match
- Status de conciliação: pending, reconciled, manual, divergent, ignored

**Endpoints:**
- `POST /api/bank-statements/{id}/reconcile` - Conciliação automática
- `POST /api/bank-transactions/{id}/reconcile-manual` - Conciliação manual
- `POST /api/bank-transactions/{id}/ignore` - Ignorar transação
- `POST /api/bank-transactions/{id}/create-record` - Criar receita/despesa

#### 3. Validação em Tempo Real de CPF/CNPJ
Componente reutilizável `CpfCnpjInput`:
- Formatação automática durante digitação
- Validação matemática de dígitos verificadores
- Indicador visual (verde=válido, vermelho=inválido)
- Suporte a CPF (11 dígitos) e CNPJ (14 dígitos)

**Aplicado em:**
- Receitas: Campo "CPF/CNPJ do Doador"
- Despesas: Campo "CPF/CNPJ do Fornecedor"

**Endpoint de validação:**
- `GET /api/validate/document?cpf_cnpj=...` - Valida e formata documento

### Arquivos Criados/Modificados
- `/app/frontend/src/pages/ExtratosBancarios.jsx` - Nova página
- `/app/frontend/src/components/CpfCnpjInput.jsx` - Componente de validação
- `/app/frontend/src/components/Layout.jsx` - Adicionado link "Extratos Bancários"
- `/app/frontend/src/App.js` - Adicionada rota `/extratos`
- `/app/frontend/src/pages/Receitas.jsx` - Integrado CpfCnpjInput
- `/app/frontend/src/pages/Despesas.jsx` - Integrado CpfCnpjInput
- `/app/backend/server.py` - Novos endpoints e modelos
- `/app/backend/requirements.txt` - Adicionado ofxparse

### Testes
- Backend: 100% (14/14 testes)
- Frontend: 100% (39/39 testes)
- Arquivo: /app/test_reports/iteration_12.json

### Próximas Tarefas (P1)
- [ ] Atualizar Relatorios.jsx com controles UI para exportação SPCE expandida

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil
- [ ] Portal personalizado Ativa Contabilidade

---
