import { test, expect } from '@playwright/test';
import { loginOperador, OPERADOR } from './helpers';

test.describe('operador', () => {
  test('login correcto lleva al panel de clientes', async ({ page }) => {
    await loginOperador(page);
    await expect(page).toHaveURL(/\/operador\/clientes/);
  });

  test('login con contraseña incorrecta muestra error', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#email').fill(OPERADOR.email);
    await page.locator('#password').fill('contraseña-mala');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    // El componente Login muestra el detalle del error 401 en rojo.
    await expect(page.getByText(/inválid|incorrect/i)).toBeVisible({ timeout: 15000 });
    // No debe navegar al panel.
    await expect(page).not.toHaveURL(/\/operador/);
  });

  test('el operador puede crear un VCOO', async ({ page }) => {
    await loginOperador(page);
    await page.goto('/operador/clientes/nuevo');

    const nombre = `E2E VCOO ${Date.now()}`;
    await page.locator('#nombre-cliente').fill(nombre);
    await page.getByRole('button', { name: 'Crear Cliente' }).click();

    // Tras crear, la página muestra el mensaje de éxito y los datos de provisión.
    await expect(page.getByText('¡Cliente creado exitosamente!')).toBeVisible({
      timeout: 20000,
    });
    // El nombre creado aparece en el resumen de éxito.
    await expect(page.getByText(nombre)).toBeVisible();
  });
});
