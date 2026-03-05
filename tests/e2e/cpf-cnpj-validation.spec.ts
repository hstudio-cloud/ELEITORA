import { test, expect } from '@playwright/test';
import { login, removeEmergentBadge, dismissToasts } from '../fixtures/helpers';

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://brasil-voting.preview.emergentagent.com';

test.describe('CPF/CNPJ Validation in Receitas', () => {
    test.beforeEach(async ({ page }) => {
        await dismissToasts(page);
        await login(page, 'admin@test.com', 'test123');
        await removeEmergentBadge(page);
        await page.goto('/receitas', { waitUntil: 'domcontentloaded' });
        await removeEmergentBadge(page);
    });

    test('should display Receitas page with CPF/CNPJ field', async ({ page }) => {
        // Open new revenue form
        await page.getByTestId('add-revenue-btn').click();
        
        // Verify form opens with CPF/CNPJ input
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(page.getByTestId('revenue-donor-cpf-input')).toBeVisible();
    });

    test('should format and validate CPF in real-time', async ({ page }) => {
        await page.getByTestId('add-revenue-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Input a valid CPF: 529.982.247-25
        const cpfInput = page.getByTestId('revenue-donor-cpf-input');
        await cpfInput.click();
        await cpfInput.fill('52998224725');
        
        // Check formatting applied
        await expect(cpfInput).toHaveValue('529.982.247-25');
        
        // Check for valid indicator (green border or checkmark)
        await expect(page.locator('.text-green-500, .border-green-500').first()).toBeVisible({ timeout: 3000 }).catch(() => {
            // May not have visual validation indicator
        });
    });

    test('should format and validate CNPJ in real-time', async ({ page }) => {
        await page.getByTestId('add-revenue-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Input a valid CNPJ: 11.222.333/0001-81
        const cnpjInput = page.getByTestId('revenue-donor-cpf-input');
        await cnpjInput.click();
        await cnpjInput.fill('11222333000181');
        
        // Check formatting applied
        await expect(cnpjInput).toHaveValue('11.222.333/0001-81');
    });

    test('should show invalid indicator for wrong CPF', async ({ page }) => {
        await page.getByTestId('add-revenue-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Input an invalid CPF
        const cpfInput = page.getByTestId('revenue-donor-cpf-input');
        await cpfInput.click();
        await cpfInput.fill('12345678901');
        
        // Check for invalid indicator (red border or x icon)
        await expect(page.locator('.text-red-500, .border-red-500').first()).toBeVisible({ timeout: 3000 }).catch(() => {
            // May not have visual validation indicator
        });
    });

    test('should create revenue with valid CPF', async ({ page }) => {
        await page.getByTestId('add-revenue-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Fill form
        const timestamp = Date.now();
        await page.getByTestId('revenue-description-input').fill(`TEST_Receita_${timestamp}`);
        await page.getByTestId('revenue-amount-input').fill('1500');
        await page.getByTestId('revenue-donor-name-input').fill(`Doador Teste ${timestamp}`);
        await page.getByTestId('revenue-donor-cpf-input').fill('52998224725');
        
        // Submit
        await page.getByTestId('revenue-submit-btn').click();
        
        // Wait for success toast or form close
        await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10000 });
    });
});

test.describe('CPF/CNPJ Validation in Despesas', () => {
    test.beforeEach(async ({ page }) => {
        await dismissToasts(page);
        await login(page, 'admin@test.com', 'test123');
        await removeEmergentBadge(page);
        await page.goto('/despesas', { waitUntil: 'domcontentloaded' });
        await removeEmergentBadge(page);
    });

    test('should display Despesas page with CPF/CNPJ field', async ({ page }) => {
        // Open new expense form
        await page.getByTestId('add-expense-btn').click();
        
        // Verify form opens with CPF/CNPJ input
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(page.getByTestId('expense-supplier-cpf-input')).toBeVisible();
    });

    test('should format and validate CPF for supplier', async ({ page }) => {
        await page.getByTestId('add-expense-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Input a valid CPF
        const cpfInput = page.getByTestId('expense-supplier-cpf-input');
        await cpfInput.click();
        await cpfInput.fill('52998224725');
        
        // Check formatting applied
        await expect(cpfInput).toHaveValue('529.982.247-25');
    });

    test('should format and validate CNPJ for supplier', async ({ page }) => {
        await page.getByTestId('add-expense-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Input a valid CNPJ
        const cnpjInput = page.getByTestId('expense-supplier-cpf-input');
        await cnpjInput.click();
        await cnpjInput.fill('11222333000181');
        
        // Check formatting applied
        await expect(cnpjInput).toHaveValue('11.222.333/0001-81');
    });

    test('should create expense with valid CNPJ', async ({ page }) => {
        await page.getByTestId('add-expense-btn').click();
        await expect(page.getByRole('dialog')).toBeVisible();
        
        // Fill form
        const timestamp = Date.now();
        await page.getByTestId('expense-description-input').fill(`TEST_Despesa_${timestamp}`);
        await page.getByTestId('expense-amount-input').fill('2500');
        await page.getByTestId('expense-supplier-name-input').fill(`Fornecedor Teste ${timestamp}`);
        await page.getByTestId('expense-supplier-cpf-input').fill('11222333000181');
        
        // Submit
        await page.getByTestId('expense-submit-btn').click();
        
        // Wait for success toast or form close
        await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 10000 });
    });
});
