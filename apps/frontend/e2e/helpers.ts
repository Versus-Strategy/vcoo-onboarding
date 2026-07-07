import { Page, expect } from '@playwright/test';

export const OPERADOR = {
  email: 'admin@test.io',
  password: 'AdminPass1',
};

/** Genera un email único para evitar colisiones entre ejecuciones/tests. */
export function emailUnico(prefijo = 'cliente'): string {
  const rnd = Math.random().toString(36).slice(2, 8);
  return `${prefijo}-${Date.now()}-${rnd}@test.io`;
}

/**
 * Inicia sesión como operador vía la UI y espera a aterrizar en el panel.
 * Deja la página en /operador/clientes.
 */
export async function loginOperador(page: Page): Promise<void> {
  await page.goto('/login');
  await page.locator('#email').fill(OPERADOR.email);
  await page.locator('#password').fill(OPERADOR.password);
  await page.getByRole('button', { name: 'Ingresar' }).click();
  // Tras login, AppContent redirige a /operador -> /operador/clientes.
  await expect(page).toHaveURL(/\/operador\/clientes/, { timeout: 15000 });
}
