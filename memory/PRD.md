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
- [ ] Configurar RESEND_API_KEY para ativar envio de e-mails

### Backlog (P2)
- [ ] Integração com GOV.BR/ICP-Brasil para assinatura certificada
- [ ] Importação de extratos bancários
- [ ] Conciliação bancária automática
