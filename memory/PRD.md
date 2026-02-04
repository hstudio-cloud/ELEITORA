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
