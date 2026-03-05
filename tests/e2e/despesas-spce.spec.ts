import { test, expect } from '@playwright/test';
import { login, dismissToasts, removeEmergentBadge } from '../fixtures/helpers';

test.describe('Despesas SPCE Fields', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await login(page, 'admin@test.com', 'test123');
    await page.waitForURL(/\/(dashboard|receitas|despesas|conformidade)/, { timeout: 15000 });
    // Navigate to Despesas
    await page.getByRole('link', { name: /despesas/i }).click();
    await expect(page.getByTestId('despesas-page')).toBeVisible({ timeout: 10000 });
  });

  test('should display Despesas page with summary card', async ({ page }) => {
    await expect(page.getByTestId('expense-summary-card')).toBeVisible();
    await expect(page.getByText(/total de despesas/i)).toBeVisible();
    await expect(page.getByTestId('add-expense-btn')).toBeVisible();
  });

  test('should open Nova Despesa form with SPCE fields', async ({ page }) => {
    await page.getByTestId('add-expense-btn').click();
    
    // Wait for dialog
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('heading', { name: 'Nova Despesa' })).toBeVisible();
    
    // Check SPCE section label
    await expect(page.getByText(/campos spce/i)).toBeVisible();
    
    // Check SPCE fields exist
    await expect(page.getByTestId('expense-tipo-pagamento-select')).toBeVisible();
    await expect(page.getByTestId('expense-doc-fiscal-input')).toBeVisible();
    await expect(page.getByTestId('expense-data-pagamento-input')).toBeVisible();
  });

  test('should change payment type in SPCE fields', async ({ page }) => {
    await page.getByTestId('add-expense-btn').click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // Test changing Forma de Pagamento
    await page.getByTestId('expense-tipo-pagamento-select').click();
    await page.getByRole('option', { name: /pix/i }).click();
    
    // Verify PIX is now selected
    await expect(page.getByTestId('expense-tipo-pagamento-select')).toContainText(/pix/i);
  });
});
