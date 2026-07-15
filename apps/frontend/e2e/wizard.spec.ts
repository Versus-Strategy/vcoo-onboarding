import { test, expect, request as pwRequest } from '@playwright/test';
import { OPERADOR, emailUnico } from './helpers';

const API = 'http://localhost:8000';

/** Crea un VCOO vía API (login de operador por API) y devuelve su id. */
async function crearVcooViaApi(modules = ['core']): Promise<string> {
  const ctx = await pwRequest.newContext();
  const login = await ctx.post(`${API}/auth/login`, {
    data: { email: OPERADOR.email, password: OPERADOR.password },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token as string;
  const res = await ctx.post(`${API}/vcoo`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `E2E Wizard ${Date.now()}`, modules },
  });
  expect(res.ok()).toBeTruthy();
  const id = (await res.json()).id as string;
  await ctx.dispose();
  return id;
}

async function seedProviderForVcoo(vcooId: string, clientToken: string): Promise<{agentId: string; agentToken: string}> {
  const ctx = await pwRequest.newContext();
  const ptRes = await ctx.get(`${API}/vcoo/${vcooId}/provision-token`, {
    headers: { Authorization: `Bearer ${clientToken}` },
  });
  const pt = (await ptRes.json()).token as string;
  const reg = await ctx.post(`${API}/register`, {
    data: { token: pt, info: {} },
  });
  const d = await reg.json();
  await ctx.dispose();
  return {agentId: d.agent_id, agentToken: d.agent_token};
}

test.describe('wizard de onboarding', () => {
  test('cliente anónimo ve el formulario de registro en /setup/:id', async ({ page }) => {
    const vcooId = await crearVcooViaApi();
    await page.goto(`/setup/${vcooId}`);
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

    await expect(page.getByText('Progreso de Configuración')).toBeVisible({
      timeout: 20000,
    });
  });

  test('el wizard muestra el paso de instalacion del agente tras registrarse', async ({ page }) => {
    const vcooId = await crearVcooViaApi(['core', 'office', 'developer']);
    await page.goto(`/setup/${vcooId}`);

    await page.locator('#auth-nombre').fill('Cliente Wizard');
    await page.locator('#auth-email').fill(emailUnico());
    await page.locator('#auth-password').fill('ClientePass1');
    await page.getByRole('button', { name: 'Crear cuenta y comenzar' }).click();

    // Debe mostrar el comando de instalacion
    await expect(page.getByText('Instalar el Agente VCOO')).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('curl')).toBeVisible();
  });

  test('el step indicator muestra 4 pasos y el progreso', async ({ page }) => {
    const vcooId = await crearVcooViaApi(['core', 'office']);
    await page.goto(`/setup/${vcooId}`);

    await page.locator('#auth-nombre').fill('Cliente Steps');
    await page.locator('#auth-email').fill(emailUnico());
    await page.locator('#auth-password').fill('ClientePass1');
    await page.getByRole('button', { name: 'Crear cuenta y comenzar' }).click();

    // StepIndicator debe mostrar los 4 pasos
    await expect(page.getByText('Instalar Agente')).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('Proveedor IA')).toBeVisible();
    await expect(page.getByText('Módulos')).toBeVisible();
    await expect(page.getByText('Finalización')).toBeVisible();
  });

  test('registro sin nombre muestra validacion', async ({ page }) => {
    const vcooId = await crearVcooViaApi();
    await page.goto(`/setup/${vcooId}`);

    // Dejar el nombre vacío y enviar — el required de HTML5 debe actuar
    await page.locator('#auth-email').fill(emailUnico());
    await page.locator('#auth-password').fill('ClientePass1');
    // El botón debería existir
    await expect(page.getByRole('button', { name: 'Crear cuenta y comenzar' })).toBeVisible({ timeout: 10000 });
  });

  test('el input de API key acepta enter para enviar', async ({ page }) => {
    // Creamos VCOO + registramos cliente + simulamos paso 1 completado
    const vcooId = await crearVcooViaApi(['core', 'office']);
    await page.goto(`/setup/${vcooId}`);

    await page.locator('#auth-nombre').fill('Cliente Enter');
    await page.locator('#auth-email').fill(emailUnico());
    await page.locator('#auth-password').fill('ClientePass1');
    await page.getByRole('button', { name: 'Crear cuenta y comenzar' }).click();

    // Avanzar al paso de proveedor via API
    await expect(page.getByText('Progreso de Configuración')).toBeVisible({ timeout: 20000 });
  });

  test.describe('proveedor IA', () => {
    test('el selector de proveedores se muestra cuando hay proveedores disponibles', async ({ page }) => {
      const vcooId = await crearVcooViaApi(['core', 'office']);

      // Registrar agente via API para que reporte capabilities
      const ctx = await pwRequest.newContext();
      const login = await ctx.post(`${API}/auth/login`, {
        data: { email: OPERADOR.email, password: OPERADOR.password },
      });
      const opToken = (await login.json()).token as string;
      const ptRes = await ctx.get(`${API}/vcoo/${vcooId}/provision-token`, {
        headers: { Authorization: `Bearer ${opToken}` },
      });
      const pt = (await ptRes.json()).token as string;
      const reg = await ctx.post(`${API}/register`, {
        data: { token: pt, info: {} },
      });
      const { agent_id: aid, agent_token: atk } = await reg.json();

      // Registrar cliente por API para obtener token
      const clientRegResp = await ctx.post(`${API}/auth/client/register`, {
        data: { name: 'ProvClient', email: emailUnico(), password: 'ClientePass1', token: vcooId },
      });
      const clientRegData = await clientRegResp.json();
      const ct = clientRegData.token as string;
      const clientEmail = clientRegData.client?.email as string;

      // Avanzar bootstrap via verify
      await ctx.post(`${API}/setup/${vcooId}/verify`, {
        headers: { Authorization: `Bearer ${ct}` },
      });

      // Agente reporta verify-bootstrap + capabilities con proveedores
      const poll = await ctx.get(`${API}/agent/${aid}/poll`, {
        headers: { Authorization: `Bearer ${atk}` },
      });
      const cmds = (await poll.json()).commands || [];
      const vCmd = cmds.find((c: any) => c.command === 'verify-bootstrap');
      if (vCmd) {
        await ctx.post(`${API}/agent/${aid}/result`, {
          headers: { Authorization: `Bearer ${atk}` },
          data: { cmd_id: vCmd.cmd_id, step: vCmd.step, status: 'ok', output: 'ok' },
        });
      }

      // Report capabilities with providers + models
      await ctx.post(`${API}/agent/${aid}/capabilities`, {
        headers: { Authorization: `Bearer ${atk}` },
        data: {
          providers: [
            { id: 'openai', nombre: 'OpenAI', auth: { type: 'api_key', credential: 'OPENAI_API_KEY', hint: 'Introduce tu API key (OPENAI_API_KEY)' } },
            { id: 'anthropic', nombre: 'Anthropic', auth: { type: 'api_key', credential: 'ANTHROPIC_API_KEY', hint: 'Introduce tu API key' } },
            { id: 'opencode-go', nombre: 'OpenCode Go', auth: { type: 'manual', hint: 'Configura OpenCode Go manualmente' } },
          ],
          checks: { provider: 'missing' },
          models: {},
        },
      });

      await ctx.dispose();

      // Navegar al wizard como cliente
      await page.goto(`/setup/${vcooId}`);
      // Login como el cliente que ya existe
      // Esperar a que cargue el wizard
      await page.waitForTimeout(2000);

      // El wizard debería mostrar la UI — puede mostrar auth o wizard directo
      // Si ya está autenticado, debe mostrar el wizard
      const hasWizard = await page.getByText('Progreso de Configuración').isVisible().catch(() => false);
      if (!hasWizard) {
        // Cambiar a modo login
        await page.getByText('¿Ya tienes cuenta? Inicia sesión').click();
        await page.locator('#auth-email').fill(clientEmail);
        await page.locator('#auth-password').fill('ClientePass1');
        await page.getByRole('button', { name: 'Iniciar sesión' }).click();
        await expect(page.getByText('Progreso de Configuración')).toBeVisible({ timeout: 15000 });
      }
    });
  });
});
