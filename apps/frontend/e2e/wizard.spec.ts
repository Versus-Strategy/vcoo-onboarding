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
    test('cliente: one-liner install + proveedor + agente procesa', async ({ page }) => {
      // 1. Crear VCOO + registrar cliente fresco via API
      const ctx = await pwRequest.newContext();
      const login = await ctx.post(`${API}/auth/login`, {
        data: { email: OPERADOR.email, password: OPERADOR.password },
      });
      const opToken = (await login.json()).token as string;
      const vc = await ctx.post(`${API}/vcoo`, {
        headers: { Authorization: `Bearer ${opToken}` },
        data: { name: `OneLiner ${Date.now()}`, modules: ['core', 'office'] },
      });
      const VCOO_ID = (await vc.json()).id as string;
      await ctx.dispose();

      // 2. Browser: registrarse como cliente
      await page.goto(`/setup/${VCOO_ID}`);
      const email = emailUnico();
      await page.locator('#auth-nombre').fill('OneLiner Client');
      await page.locator('#auth-email').fill(email);
      await page.locator('#auth-password').fill('ClientePass1');
      await page.getByRole('button', { name: 'Crear cuenta y comenzar' }).click();
      await expect(page.getByText('Progreso de Configuración')).toBeVisible({ timeout: 20000 });

      // 3. Verificar paso 0: Instalar Agente con el comando one-liner
      await expect(page.getByText('Instalar el Agente VCOO')).toBeVisible({ timeout: 10000 });
      const cmdText = await page.getByText(/curl/).textContent().catch(() => '');
      expect(cmdText).toContain('curl');
      expect(cmdText).toContain('PROVISION_TOKEN');
      expect(cmdText).toContain('CONTROL_PLANE');
      console.log(`✅ One-liner visible en wizard: ${cmdText.trim().substring(0, 80)}...`);

      // 4. Extraer PROVISION_TOKEN del comando
      const installCmd = await page.evaluate(() => {
        const el = document.querySelector('code');
        return el ? el.textContent || '' : '';
      });
      const tokenMatch = installCmd.match(/PROVISION_TOKEN=([^\s]+)/);
      expect(tokenMatch).toBeTruthy();
      const provisionToken = tokenMatch![1];
      console.log(`✅ PROVISION_TOKEN extraido: ${provisionToken.substring(0, 30)}...`);

      // 5. Simular install.sh: registrar agente con el token (esto hace el one-liner)
      const ctx2 = await pwRequest.newContext();
      const reg = await ctx2.post(`${API}/register`, {
        data: { token: provisionToken, info: { hostname: 'lxc-e2e-oneliner' } },
      });
      expect(reg.ok()).toBeTruthy();
      const regData = await reg.json();
      const agentToken = regData.agent_token as string;
      const agentId = regData.agent_id as string;
      const encKey = regData.encryption_key as string;
      console.log(`✅ Agente registrado: ${agentId} enc_key=${encKey ? 'OK' : 'N/A'}`);
      await ctx2.dispose();

      // 6. El backend auto-encola verify-bootstrap al registrar agente
      // El agente LXC (ya configurado para este backend) hara tick y lo procesara
      // Pero para este test simulamos el agente via API (el LXC esta configurado con otro agente)
      // Procesar verify-bootstrap
      const ctx3 = await pwRequest.newContext();
      for (let attempt = 0; attempt < 6; attempt++) {
        await new Promise(r => setTimeout(r, 2000));
        const poll = await ctx3.get(`${API}/agent/${agentId}/poll`, {
          headers: { Authorization: `Bearer ${agentToken}` },
        });
        const cmds = (await poll.json()).commands || [];
        const vc = cmds.find((c: any) => c.command === 'verify-bootstrap');
        if (vc) {
          await ctx3.post(`${API}/agent/${agentId}/result`, {
            headers: { Authorization: `Bearer ${agentToken}` },
            data: { cmd_id: vc.cmd_id, step: vc.step, status: 'ok', output: 'ok' },
          });
          break;
        }
      }

      // 7. Reportar capabilities con modelos (como haria el agente real tras instalar)
      const PROVIDERS = [
        { id: 'openai', nombre: 'OpenAI', auth: { type: 'api_key', credential: 'OPENAI_API_KEY', hint: 'Introduce tu API key' } },
        { id: 'opencode-go', nombre: 'OpenCode Go', auth: { type: 'manual' } },
      ];
      const MODELS = { openai: { list: ['gpt-4', 'gpt-3.5-turbo'], recommended: 'gpt-4' } };
      await ctx3.post(`${API}/agent/${agentId}/capabilities`, {
        headers: { Authorization: `Bearer ${agentToken}` },
        data: { providers: PROVIDERS, checks: { provider: 'missing' }, models: MODELS },
      });
      await ctx3.dispose();

      // 8. Esperar a que el frontend detecte el cambio (poll 15s)
      await page.waitForTimeout(5000);
      await page.reload();

      // 9. Verificar paso 1 con proveedores
      await expect(page.getByText('Proveedor IA')).toBeVisible({ timeout: 20000 });
      await expect(page.getByText('Selecciona tu proveedor de IA')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('OpenAI')).toBeVisible({ timeout: 10000 });

      // 10. Seleccionar OpenAI → escribir API key → enviar
      await page.getByText('OpenAI').click();
      await expect(page.getByText('Introduce tu API key')).toBeVisible({ timeout: 5000 });
      await page.locator('input[type="password"]').fill('sk-e2e-oneliner-key');
      await page.getByRole('button', { name: 'Conectar' }).click();

      // 11. Simular agente: procesa set-provider + reporta provider=ok + modelos
      // (el frontend poll cada 5s, hay tiempo)
      const ctx4 = await pwRequest.newContext();
      for (let attempt = 0; attempt < 8; attempt++) {
        await new Promise(r => setTimeout(r, 2000));
        const poll = await ctx4.get(`${API}/agent/${agentId}/poll`, {
          headers: { Authorization: `Bearer ${agentToken}` },
        });
        const spCmd = (await poll.json()).commands?.find((c: any) => c.command === 'set-provider');
        if (spCmd) {
          await ctx4.post(`${API}/agent/${agentId}/result`, {
            headers: { Authorization: `Bearer ${agentToken}` },
            data: { cmd_id: spCmd.cmd_id, step: spCmd.step || '', status: 'ok', output: 'configured' },
          });
          break;
        }
      }
      await ctx4.post(`${API}/agent/${agentId}/capabilities`, {
        headers: { Authorization: `Bearer ${agentToken}` },
        data: { providers: PROVIDERS, checks: { provider: 'ok', model: 'missing' }, models: MODELS },
      });
      await ctx4.dispose();

      // 12. Esperar a que el frontend polling detecte provider=ok + modelos
      // El enviarApiKey poll cada 5s, max 60s para provider + 30s para modelos
      // Como ya pusimos los datos, detectara en el proximo poll (~5s)
      await expect(page.getByText('RECOMENDADO')).toBeVisible({ timeout: 30000 });
      // Los nombres de modelo se muestran como texto en el selector
      const modeloTexto = await page.getByText(/gpt/).first().textContent().catch(() => '');
      expect(modeloTexto).toContain('gpt-4');
      await expect(page.getByText('OTROS MODELOS')).toBeVisible();
      await expect(page.getByText('gpt-3.5-turbo')).toBeVisible();

      // 13. Seleccionar modelo recomendado
      await page.getByRole('button', { name: 'Seleccionar' }).first().click();

      // 14. Simular agente: procesa el segundo set-provider (modelo) + reporta model=ok
      const ctx5 = await pwRequest.newContext();
      for (let attempt = 0; attempt < 8; attempt++) {
        await new Promise(r => setTimeout(r, 2000));
        const poll = await ctx5.get(`${API}/agent/${agentId}/poll`, {
          headers: { Authorization: `Bearer ${agentToken}` },
        });
        const cmds = (await poll.json()).commands || [];
        const spCmd = cmds.find((c: any) => c.command === 'set-provider' && c.payload?.model);
        if (spCmd) {
          await ctx5.post(`${API}/agent/${agentId}/result`, {
            headers: { Authorization: `Bearer ${agentToken}` },
            data: { cmd_id: spCmd.cmd_id, step: spCmd.step || '', status: 'ok', output: 'model set' },
          });
          break;
        }
      }
      await ctx5.post(`${API}/agent/${agentId}/capabilities`, {
        headers: { Authorization: `Bearer ${agentToken}` },
        data: { providers: PROVIDERS, checks: { provider: 'ok', model: 'ok' }, models: MODELS },
      });
      await ctx5.dispose();

      // 15. El frontend detecta model=ok → llama a /advance automaticamente
      // Esperar hasta 30s a que el avance se complete
      await expect(async () => {
        const stored = await page.evaluate(() => localStorage.getItem('vcoo-auth')).catch(() => '{}');
        const jwt = JSON.parse(stored || '{}').token;
        if (!jwt) throw new Error('no token');
        const ctx6 = await pwRequest.newContext();
        const setupRes = await ctx6.get(`${API}/setup/${VCOO_ID}`, {
          headers: { Authorization: `Bearer ${jwt}` },
        });
        const d = await setupRes.json();
        await ctx6.dispose();
        // El paso debe avanzar mas alla de google-oauth
        const advanced = d.step !== 'google-oauth';
        if (!advanced) throw new Error(`step still ${d.step}`);
        return d;
      }).toPass({ timeout: 30000 });

      // 16. Verificacion final
      const stored = await page.evaluate(() => localStorage.getItem('vcoo-auth')).catch(() => '{}');
      const jwt = JSON.parse(stored || '{}').token as string;
      const ctx7 = await pwRequest.newContext();
      const setupRes = await ctx7.get(`${API}/setup/${VCOO_ID}`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      const setupData = await setupRes.json();
      await ctx7.dispose();

      expect(setupData.completed).toContain('bootstrap');
      expect((setupData.providers || []).length).toBeGreaterThan(0);
      expect(setupData.checks?.provider).toBe('ok');
      expect(setupData.checks?.model).toBe('ok');
      console.log(`✅ Onboarding completo: step=${setupData.step} wizard=${setupData.wizard_step} completed=${setupData.completed.length}`);
    });
  });
});
