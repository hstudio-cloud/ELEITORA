import { test, expect } from '@playwright/test';
import { login, dismissToasts, removeEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://brasil-voting.preview.emergentagent.com';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
  });

  test('should display login page', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    // Check login form elements
    await expect(page.locator('input[type="email"], input[placeholder*="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole('button', { name: /entrar/i })).toBeVisible();
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    await page.locator('input[type="email"], input[placeholder*="email"]').fill('admin@test.com');
    await page.locator('input[type="password"]').fill('test123');
    await page.getByRole('button', { name: /entrar/i }).click();
    
    // Wait for successful navigation to dashboard
    await expect(page).toHaveURL(/\/(dashboard)/, { timeout: 15000 });
    
    // Should show dashboard content
    await expect(page.getByText(/dashboard/i).first()).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    await page.locator('input[type="email"], input[placeholder*="email"]').fill('invalid@test.com');
    await page.locator('input[type="password"]').fill('wrongpassword');
    await page.getByRole('button', { name: /entrar/i }).click();
    
    // Should show error message or stay on login page
    await page.waitForTimeout(2000);
    // Page should still show login form (not redirected)
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });
});

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await login(page, 'admin@test.com', 'test123');
    await page.waitForURL(/\/(dashboard|receitas|despesas|conformidade)/, { timeout: 15000 });
  });

  test('should navigate to Receitas page', async ({ page }) => {
    await page.getByRole('link', { name: /receitas/i }).click();
    await expect(page.getByTestId('receitas-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/receitas/i).first()).toBeVisible();
  });

  test('should navigate to Despesas page', async ({ page }) => {
    await page.getByRole('link', { name: /despesas/i }).click();
    await expect(page.getByTestId('despesas-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/despesas/i).first()).toBeVisible();
  });

  test('should navigate to Conformidade TSE page', async ({ page }) => {
    await page.getByRole('link', { name: /conformidade/i }).click();
    await expect(page.getByTestId('conformidade-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/conformidade tse/i).first()).toBeVisible();
  });

  test('should navigate to Contratos page', async ({ page }) => {
    await page.getByRole('link', { name: /contratos/i }).click();
    await expect(page.getByText(/contratos/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to Pagamentos page', async ({ page }) => {
    await page.getByRole('link', { name: /pagamentos/i }).click();
    await expect(page.getByText(/pagamentos/i).first()).toBeVisible({ timeout: 10000 });
  });
});
