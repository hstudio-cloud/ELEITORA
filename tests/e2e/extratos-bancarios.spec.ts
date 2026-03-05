import { test, expect } from '@playwright/test';
import { login, removeEmergentBadge, dismissToasts } from '../fixtures/helpers';

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://brasil-voting.preview.emergentagent.com';

test.describe('Extratos Bancários Page', () => {
    test.beforeEach(async ({ page }) => {
        await dismissToasts(page);
        await login(page, 'admin@test.com', 'test123');
        await removeEmergentBadge(page);
    });

    test('should navigate to Extratos Bancários page via sidebar', async ({ page }) => {
        // Navigate to Extratos via sidebar
        await page.getByRole('link', { name: /extratos bancários/i }).click();
        await page.waitForLoadState('domcontentloaded');
        
        // Verify page loaded
        await expect(page.getByTestId('extratos-page')).toBeVisible();
        await expect(page.getByRole('heading', { name: /extratos bancários/i })).toBeVisible();
    });

    test('should display upload button and empty state', async ({ page }) => {
        await page.goto('/extratos', { waitUntil: 'domcontentloaded' });
        await removeEmergentBadge(page);
        
        // Check upload button exists
        await expect(page.getByTestId('upload-btn')).toBeVisible();
        await expect(page.getByTestId('upload-btn')).toHaveText(/importar extrato ofx/i);
        
        // Check page structure
        await expect(page.getByText(/extratos importados/i)).toBeVisible();
    });

    test('should open upload dialog when clicking upload button', async ({ page }) => {
        await page.goto('/extratos', { waitUntil: 'domcontentloaded' });
        await removeEmergentBadge(page);
        
        // Click upload button
        await page.getByTestId('upload-btn').click();
        
        // Verify dialog opens
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(page.getByText('Importar Extrato Bancário')).toBeVisible();
        await expect(page.getByText('Formatos suportados:')).toBeVisible();
        await expect(page.getByTestId('select-file-btn')).toBeVisible();
    });

    test('should show transaction panel area', async ({ page }) => {
        await page.goto('/extratos', { waitUntil: 'domcontentloaded' });
        await removeEmergentBadge(page);
        
        // Check transaction panel exists
        await expect(page.getByText('Transações', { exact: true })).toBeVisible();
        await expect(page.getByText('Selecione um extrato para ver as transações')).toBeVisible();
    });
});
