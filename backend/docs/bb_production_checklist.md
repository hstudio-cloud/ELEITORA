# Banco do Brasil PIX - Checklist de Producao (Render)

## 1. Variaveis obrigatorias
- `BB_APP_KEY`
- `BB_CLIENT_ID`
- `BB_CLIENT_SECRET`
- `BB_ENVIRONMENT=producao`

## 2. Variaveis opcionais (quando exigido pelo convenio BB)
- `BB_CLIENT_CERT_PATH` (caminho do certificado cliente)
- `BB_CLIENT_KEY_PATH` (caminho da chave privada)
- `BB_STRICT_MODE=true` para bloquear fallback simulado em producao

## 3. Comportamento do sistema
- `BB_STRICT_MODE=false`: tenta BB real e, se falhar, cai para `integration_mode=simulado`.
- `BB_STRICT_MODE=true`: se BB falhar, retorna erro `502` e nao cria pagamento simulado.

## 4. Teste tecnico no backend
1. Chamar `GET /api/pix/bank-info`
2. Chamar `GET /api/pix/bank-diagnostic`
3. Esperado em producao real:
   - `status=ok`
   - `oauth_ok=true`
   - `environment=producao`
   - `integration_available=true`

## 5. Teste funcional minimo
1. Criar um PIX via `POST /api/pix/payment`
2. Verificar resposta:
   - `integration_mode=real`
   - `transaction_id` preenchido
3. Consultar `GET /api/pix/check-status/{pix_id}`
4. Validar mudanca de status no pagamento e na despesa vinculada.

## 6. Observacao de fluxo
- O endpoint atual usa `cobv` (cobranca PIX), com `txid` e `pix copia e cola`.
- Para debito/pagamento direto de conta (transferencia de saida), validar com o gerente BB se o convenio habilita endpoint especifico de pagamento de saida.
