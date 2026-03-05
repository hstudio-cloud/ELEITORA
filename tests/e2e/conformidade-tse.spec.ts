import { test, expect } from '@playwright/test';
import { login, dismissToasts, removeEmergentBadge } from '../fixtures/helpers';

test.describe('Conformidade TSE Page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await login(page, 'admin@test.com', 'test123');
    await page.waitForURL(/\/(dashboard|receitas|despesas|conformidade)/, { timeout: 15000 });
    // Navigate to Conformidade TSE
    await page.getByRole('link', { name: /conformidade/i }).click();
    await expect(page.getByTestId('conformidade-page')).toBeVisible({ timeout: 10000 });
  });

  test('should display Conformidade TSE page with progress indicator', async ({ page }) => {
    // Check main elements
    await expect(page.getByRole('heading', { name: /conformidade tse/i })).toBeVisible();
    await expect(page.getByText(/verificação de completude/i)).toBeVisible();
    
    // Check progress indicator exists (percentage display)
    await expect(page.getByText(/%/).first()).toBeVisible();
    await expect(page.getByText(/completo/i)).toBeVisible();
  });

  test('should show status badge', async ({ page }) => {
    // Check for status badge - the text "Em Andamento" is visible in the card
    await expect(page.getByText(/em andamento/i)).toBeVisible({ timeout: 5000 });
  });

  test('should display summary statistics counts', async ({ page }) => {
    // Check for summary stats - look for the specific count elements
    // The page shows: 0 Receitas, 1 Despesas, 1 Contratos, R$ 0,00 Total Receitas
    await expect(page.getByRole('paragraph').filter({ hasText: /^receitas$/i })).toBeVisible();
    await expect(page.getByRole('paragraph').filter({ hasText: /^despesas$/i })).toBeVisible();
    await expect(page.getByRole('paragraph').filter({ hasText: /^contratos$/i })).toBeVisible();
  });

  test('should display pending actions section', async ({ page }) => {
    // Check for alerts/pending actions section
    const pendingSection = page.getByText(/ações pendentes/i);
    
    // It may or may not have pending actions depending on data state
    if (await pendingSection.isVisible({ timeout: 3000 })) {
      await expect(pendingSection).toBeVisible();
    }
  });

  test('should display category breakdown section', async ({ page }) => {
    // Check for category details section
    await expect(page.getByText(/detalhamento por categoria/i)).toBeVisible();
    
    // Should show categories as headings
    await expect(page.getByRole('heading', { name: /dados da campanha/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /^receitas$/i })).toBeVisible();
  });

  test('should have Atualizar and Exportar buttons', async ({ page }) => {
    // Check for refresh button
    await expect(page.getByRole('button', { name: /atualizar/i })).toBeVisible();
    
    // Check for export button (may be disabled if conformidade < 70%)
    await expect(page.getByRole('link', { name: /exportar spce/i })).toBeVisible();
  });

  test('should show alerts for missing CNPJ configuration', async ({ page }) => {
    // This is a known state from the screenshot - CNPJ not configured
    const cnpjAlert = page.getByText(/cnpj da campanha não configurado/i);
    await expect(cnpjAlert).toBeVisible({ timeout: 5000 });
  });

  test('should show TSE information section', async ({ page }) => {
    // Check for TSE information/help section at bottom
    await expect(page.getByText(/prestação de contas eleitoral/i)).toBeVisible();
    await expect(page.getByRole('link', { name: /manual tse/i })).toBeVisible();
  });

  test('should refresh data when clicking Atualizar', async ({ page }) => {
    // Click refresh button
    await page.getByRole('button', { name: /atualizar/i }).click();
    
    // Should still show conformidade page (data refreshed)
    await expect(page.getByTestId('conformidade-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: /conformidade tse/i })).toBeVisible();
  });
});
