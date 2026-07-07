import { test, expect } from '@playwright/test';

/**
 * Tests E2E de smoke: verifican que la SPA arranca y renderiza las vistas
 * públicas clave. No hacen login real (requeriría el backend); solo comprueban
 * que el frontend se sirve y responde en el navegador.
 */

test.describe('smoke', () => {
  test('la página de login carga y muestra el formulario', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('heading', { name: 'VERSUS Strategy' })).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ingresar' })).toBeVisible();
  });

  test('la ruta raíz redirige a login cuando no hay sesión', async ({ page }) => {
    await page.goto('/');
    // Sin sesión, AppContent renderiza el Login.
    await expect(page.getByRole('heading', { name: 'VERSUS Strategy' })).toBeVisible();
  });

  test('el formulario de login es interactivo', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#email').fill('demo@versus.io');
    await page.locator('#password').fill('secret');
    await expect(page.locator('#email')).toHaveValue('demo@versus.io');
    // El botón de mostrar contraseña alterna el tipo del input.
    await expect(page.locator('#password')).toHaveAttribute('type', 'password');
    await page.getByRole('button', { name: 'Mostrar contraseña' }).click();
    await expect(page.locator('#password')).toHaveAttribute('type', 'text');
  });
});
