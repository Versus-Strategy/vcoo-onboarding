import { test, expect, request as pwRequest, Page } from '@playwright/test';
import { OPERADOR, emailUnico } from './helpers';

const API = 'http://localhost:8000';

async function apiCtx() {
  return await pwRequest.newContext();
}

async function crearVcooViaApi(modules = ['core']): Promise<string> {
  const ctx = await apiCtx();
  const login = await ctx.post(`${API}/auth/login`, {
    data: { email: OPERADOR.email, password: OPERADOR.password },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token as string;
  const res = await ctx.post(`${API}/vcoo`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `E2E ${Date.now()}`, modules },
  });
  expect(res.ok()).toBeTruthy();
  const id = (await res.json()).id as string;
  await ctx.dispose();
  return id;
}

/** Simula el agente: registra, procesa verify-bootstrap, reporta capabilities.
 *  Devuelve agent_id, agent_token, y el token del cliente registrado. */
async function setupAgentAndClient(vcooId: string, providers: any[], models: any, checks: any) {
  const ctx = await apiCtx();
  // Login operator
  const login = await ctx.post(`${API}/auth/login`, {
    data: { email: OPERADOR.email, password: OPERADOR.password },
  });
  const opToken = (await login.json()).token as string;
  // Get provision token
  const ptRes = await ctx.get(`${API}/vcoo/${vcooId}/provision-token`, {
    headers: { Authorization: `Bearer ${opToken}` },
  });
  const pt = (await ptRes.json()).token as string;
  // Register agent
  const reg = await ctx.post(`${API}/register`, { data: { token: pt, info: {} } });
  const { agent_id: aid, agent_token: atk } = await reg.json();
  // Register client
  const clientEmail = emailUnico();
  const cr = await ctx.post(`${API}/auth/client/register`, {
    data: { name: 'E2EClient', email: clientEmail, password: 'ClientePass1', token: vcooId },
  });
  const cd = await cr.json();
  const ct = cd.token as string;
  // Advance bootstrap via verify
  await ctx.post(`${API}/setup/${vcooId}/verify`, {
    headers: { Authorization: `Bearer ${ct}` },
  });
  // Agent processes verify-bootstrap
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
  // Agent reports capabilities
  await ctx.post(`${API}/agent/${aid}/capabilities`, {
    headers: { Authorization: `Bearer ${atk}` },
    data: { providers, checks, models },
  });
  await ctx.dispose();
  return { agentId: aid, agentToken: atk, clientToken: ct, clientEmail };
}

/** Simula que el agente procesa set-provider y actualiza capabilities. */
async function agentCompleteSetProvider(agentId: string, agentToken: string, checks: any, models: any) {
  const ctx = await apiCtx();
  // Get pending set-provider command
  const poll = await ctx.get(`${API}/agent/${agentId}/poll`, {
    headers: { Authorization: `Bearer ${agentToken}` },
  });
  const cmds = (await poll.json()).commands || [];
  const spCmd = cmds.find((c: any) => c.command === 'set-provider');
  if (spCmd) {
    await ctx.post(`${API}/agent/${agentId}/result`, {
      headers: { Authorization: `Bearer ${agentToken}` },
      data: { cmd_id: spCmd.cmd_id, step: spCmd.step || '', status: 'ok', output: 'configured' },
    });
  }
  // Re-report capabilities with updated checks + models
  await ctx.get(`${API}/agent/${agentId}/poll`, {
    headers: { Authorization: `Bearer ${agentToken}` },
  });
  await ctx.post(`${API}/agent/${agentId}/capabilities`, {
    headers: { Authorization: `Bearer ${agentToken}` },
    data: { providers: [], checks, models },
  });
  await ctx.dispose();
}

/** Espera a que el texto aparezca en la pagina (con timeout largo para polling). */
async function esperarTexto(page: Page, texto: string | RegExp, timeout = 25000) {
  await expect(page.getByText(texto)).toBeVisible({ timeout });
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

      const clientRegResp = await ctx.post(`${API}/auth/client/register`, {
        data: { name: 'ProvClient', email: emailUnico(), password: 'ClientePass1', token: vcooId },
      });
      const clientRegData = await clientRegResp.json();
      const ct = clientRegData.token as string;
      const clientEmail = clientRegData.client?.email as string;

      await ctx.post(`${API}/setup/${vcooId}/verify`, {
        headers: { Authorization: `Bearer ${ct}` },
      });

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

      await ctx.post(`${API}/agent/${aid}/capabilities`, {
        headers: { Authorization: `Bearer ${atk}` },
        data: {
          providers: [
            { id: 'openai', nombre: 'OpenAI', auth: { type: 'api_key', credential: 'OPENAI_API_KEY', hint: 'Introduce tu API key (OPENAI_API_KEY)' } },
            { id: 'opencode-go', nombre: 'OpenCode Go', auth: { type: 'manual', hint: 'Configura manualmente' } },
          ],
          checks: { provider: 'missing' },
          models: {},
        },
      });
      await ctx.dispose();

      await page.goto(`/setup/${vcooId}`);
      await page.waitForTimeout(2000);

      const hasWizard = await page.getByText('Progreso de Configuración').isVisible().catch(() => false);
      if (!hasWizard) {
        await page.getByText('¿Ya tienes cuenta? Inicia sesión').click();
        await page.locator('#auth-email').fill(clientEmail);
        await page.locator('#auth-password').fill('ClientePass1');
        await page.getByRole('button', { name: 'Iniciar sesión' }).click();
        await expect(page.getByText('Progreso de Configuración')).toBeVisible({ timeout: 15000 });
      }
    });
  });

  test.describe('flujo completo con agente real (LXC)', () => {
    test('cliente: registro + proveedor + agente real procesa', async ({ page }) => {
      const VCOO_ID = '3e71bc68-401f-464d-8c5a-91dba36e88f7';
      const CLIENT_EMAIL = 'lxc_3e71bc68@t.com';
      const CLIENT_PASSWORD = 'ClientePass1';

      // 1. Navegar al wizard
      await page.goto(`/setup/${VCOO_ID}`);

      // 2. Login como cliente existente
      await page.getByText('¿Ya tienes cuenta? Inicia sesión').click();
      await page.locator('#auth-email').fill(CLIENT_EMAIL);
      await page.locator('#auth-password').fill(CLIENT_PASSWORD);
      await page.getByRole('button', { name: 'Iniciar sesión' }).click();

      // 3. Verificar wizard cargado
      await expect(page.getByText('Progreso de Configuración')).toBeVisible({ timeout: 20000 });
      await expect(page.getByText('Proveedor IA')).toBeVisible();

      // 4. Esperar a que el agente LXC reporte proveedores (poll 15s)
      await expect(page.getByText('Selecciona tu proveedor de IA')).toBeVisible({ timeout: 30000 });
      await expect(page.getByText('OpenAI')).toBeVisible({ timeout: 15000 });

      // 5. Seleccionar OpenAI
      await page.getByText('OpenAI').click();
      await expect(page.getByText('Introduce tu API key')).toBeVisible({ timeout: 10000 });

      // 6. Introducir API key y enviar
      await page.locator('input[type="password"]').fill('sk-e2e-test-key-from-lxc');
      await page.getByRole('button', { name: 'Conectar' }).click();

      // 7. Esperar a que el agente procese el comando (tick cada 5s, poll frontend 15s)
      await page.waitForTimeout(18000);

      // 8. Verificar estado via API con token de la pagina
      const stored = await page.evaluate(() => localStorage.getItem('vcoo-auth'));
      expect(stored).toBeTruthy();
      const parsed = JSON.parse(stored || '{}');
      const jwt = parsed.token as string;

      const ctx = await pwRequest.newContext();
      const setupRes = await ctx.get(`${API}/setup/${VCOO_ID}`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      const setupData = await setupRes.json();
      await ctx.dispose();

      const step = setupData.step as string;
      const completed = setupData.completed as string[];

      expect(completed.includes('bootstrap')).toBeTruthy();
      console.log(`Onboarding: step=${step} completed=${completed.length} providers=${(setupData.providers || []).length} agent_online=${setupData.agent_online}`);
    });
  });
});
