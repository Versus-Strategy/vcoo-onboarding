import { test, expect, request as pwRequest } from '@playwright/test';
import { OPERADOR, emailUnico } from './helpers';

const API = 'http://localhost:8000';

/** Crea un VCOO vía API (login de operador por API) y devuelve su id. */
async function crearVcooViaApi(): Promise<string> {
  const ctx = await pwRequest.newContext();
  const login = await ctx.post(`${API}/auth/login`, {
    data: { email: OPERADOR.email, password: OPERADOR.password },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token as string;
  const res = await ctx.post(`${API}/vcoo`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `E2E Wizard ${Date.now()}` },
  });
  expect(res.ok()).toBeTruthy();
  const id = (await res.json()).id as string;
  await ctx.dispose();
  return id;
}

test.describe('wizard de onboarding', () => {
  test('cliente anónimo ve el formulario de registro en /setup/:id', async ({ page }) => {
    const vcooId = await crearVcooViaApi();
    await page.goto(`/setup/${vcooId}`);
    // El backend responde requires_registration=true; el wizard muestra el
    // formulario "Crear tu cuenta".
    await expect(page.getByRole('heading', { name: 'Crear tu cuenta' })).toBeVisible({
      timeout: 20000,
    });
    await expect(page.locator('#auth-email')).toBeVisible();
    await expect(page.locator('#auth-password')).toBeVisible();
  });

  test('un cliente puede registrarse y entrar al wizard', async ({ page }) => {
    const vcooId = await crearVcooViaApi();
    await page.goto(`/setup/${vcooId}`);

    await page.locator('#auth-nombre').fill('Cliente E2E');
    await page.locator('#auth-email').fill(emailUnico());
    await page.locator('#auth-password').fill('ClientePass1');
    await page.getByRole('button', { name: 'Crear cuenta y comenzar' }).click();

    // Tras registrarse, el wizard carga el estado y muestra el indicador de
    // progreso ("Progreso de Configuración" del StepIndicator).
    await expect(page.getByText('Progreso de Configuración')).toBeVisible({
      timeout: 20000,
    });
  });
});
