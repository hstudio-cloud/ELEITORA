import { test, expect } from '@playwright/test';
import { login, dismissToasts, removeEmergentBadge } from '../fixtures/helpers';

test.describe('Receitas SPCE Fields', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await login(page, 'admin@test.com', 'test123');
    await page.waitForURL(/\/(dashboard|receitas|despesas|conformidade)/, { timeout: 15000 });
    // Navigate to Receitas
    await page.getByRole('link', { name: /receitas/i }).click();
    await expect(page.getByTestId('receitas-page')).toBeVisible({ timeout: 10000 });
  });

  test('should display Receitas page with summary card', async ({ page }) => {
    await expect(page.getByTestId('revenue-summary-card')).toBeVisible();
    await expect(page.getByText(/total de receitas/i)).toBeVisible();
    await expect(page.getByTestId('add-revenue-btn')).toBeVisible();
  });

  test('should open Nova Receita form with SPCE fields', async ({ page }) => {
    await page.getByTestId('add-revenue-btn').click();
    
    // Wait for dialog
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('heading', { name: 'Nova Receita' })).toBeVisible();
    
    // Check SPCE section label
    await expect(page.getByText(/campos spce/i)).toBeVisible();
    
    // Check SPCE fields exist
    await expect(page.getByTestId('revenue-tipo-receita-select')).toBeVisible();
    await expect(page.getByTestId('revenue-tipo-doador-select')).toBeVisible();
    await expect(page.getByTestId('revenue-forma-recebimento-select')).toBeVisible();
  });

  test('should show Título de Eleitor field for Pessoa Física donor type', async ({ page }) => {
    await page.getByTestId('add-revenue-btn').click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    
    // With default "Pessoa Física" selected, the field should be visible
    await expect(page.getByTestId('revenue-titulo-eleitor-input')).toBeVisible();
  });
});
