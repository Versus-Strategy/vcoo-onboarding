# Plan de implementación: E2E con backend real

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ampliar los tests E2E de Playwright para cubrir flujos reales de punta a punta (login de operador, crear VCOO, registro de cliente en el wizard, wizard en modo demo, errores de login) ejecutando el backend FastAPI real contra SQLite, tanto en local como en CI.

**Architecture:** Los tests E2E arrancan el backend (`uvicorn main:application` en `:8000`, SQLite en `/tmp`) y el frontend (`vite preview` en `:4173`) mediante la opción `webServer` de Playwright (que soporta múltiples servidores). El frontend usa por defecto `VITE_API_URL=http://localhost:8000`, así que no hace falta inyectar env vars en el build. El CORS del backend ya es `*`. Los tests usan el operador sembrado (`FIRST_OPERATOR_*`) para autenticar. Un job nuevo de CI (`frontend-e2e`) instala ambas toolchains (Python + Node).

**Tech Stack:** Playwright (`@playwright/test`), FastAPI + uvicorn, SQLite, GitHub Actions.

---

## Estructura de ficheros

- **Modificar** `apps/frontend/playwright.config.ts` — pasar `webServer` de un objeto a un array de dos servidores (backend + frontend); añadir env vars del backend.
- **Crear** `apps/frontend/e2e/helpers.ts` — helpers reutilizables (login de operador, credenciales sembradas, generación de emails únicos).
- **Crear** `apps/frontend/e2e/operador.spec.ts` — login de operador, crear VCOO, errores de login.
- **Crear** `apps/frontend/e2e/wizard.spec.ts` — registro de cliente en `/setup/:id` + avance del wizard en modo demo.
- **Mantener** `apps/frontend/e2e/smoke.spec.ts` — sin cambios (los 3 smoke siguen valiendo).
- **Modificar** `.github/workflows/ci.yml` — el job `frontend-e2e` necesita Python + instalar deps del backend.
- **Modificar** `apps/frontend/README.md` (si existe sección de tests) — documentar cómo correr los E2E en local. (Opcional, solo si ya hay sección.)

**Nota sobre credenciales sembradas en CI:** el job `frontend-e2e` debe exportar las mismas env vars del backend que usa `backend-tests` (`FIRST_OPERATOR_EMAIL=admin@test.io`, `FIRST_OPERATOR_PASSWORD=AdminPass1`, `MASTER_KEY`, etc.) para que el login funcione. La `webServer` de Playwright también las necesita en local; se codifican en `playwright.config.ts` con `env`.

---

## Task 1: Configurar Playwright para arrancar backend + frontend

**Files:**
- Modify: `apps/frontend/playwright.config.ts`

- [ ] **Step 1: Reescribir la config con webServer múltiple**

Reemplaza el bloque `webServer` (objeto único) por un array de dos servidores. El backend se arranca con `uvicorn` desde `../backend` con env vars de test; el frontend con `vite preview`. Añade `PYTHONPATH` no hace falta (uvicorn se ejecuta con `cwd`).

Contenido completo del fichero:

```typescript
import { defineConfig, devices } from '@playwright/test';

/**
 * Configuración E2E de Playwright.
 *
 * Arranca DOS servidores:
 *  1. Backend FastAPI real (uvicorn) en :8000 con SQLite en /tmp.
 *  2. Frontend (vite preview) en :4173 — requiere `npm run build` previo.
 *
 * El frontend usa por defecto VITE_API_URL=http://localhost:8000, así que no
 * hace falta inyectar env vars en el build. El CORS del backend es "*".
 */

const BACKEND_ENV = {
  POSTGRES_URL: 'sqlite:////tmp/e2e_test.db',
  MASTER_KEY: 'e2e-master-key-12345',
  SECRET_KEY: 'e2e-secret-key',
  DASHBOARD_PASSWORD: 'versus',
  FIRST_OPERATOR_EMAIL: 'admin@test.io',
  FIRST_OPERATOR_PASSWORD: 'AdminPass1',
  FIRST_OPERATOR_NAME: 'Admin',
  DASHBOARD_URL: 'http://localhost:4173',
  CONTROL_PLANE: 'http://localhost:8000',
  FRONTEND_URL: 'http://localhost:4173',
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    {
      command:
        'python3 -m uvicorn main:application --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://localhost:8000/healthz',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
      env: BACKEND_ENV,
    },
    {
      command: 'npm run preview -- --port 4173',
      url: 'http://localhost:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
```

Notas:
- `fullyParallel: false` y `workers: 1` porque todos los tests comparten una única BD SQLite; evita carreras entre specs.
- `url: .../healthz` hace que Playwright espere a que el backend esté listo (el endpoint existe y devuelve 200).
- `DASHBOARD_URL`/`FRONTEND_URL` apuntan a `:4173` para que las `onboarding_url` que genera el backend sean coherentes (aunque los tests navegan por su cuenta).

- [ ] **Step 2: Verificar que el backend arranca con esas env vars en local**

Run: `cd apps/backend && POSTGRES_URL=sqlite:////tmp/e2e_test.db MASTER_KEY=e2e-master-key-12345 FIRST_OPERATOR_EMAIL=admin@test.io FIRST_OPERATOR_PASSWORD=AdminPass1 python3 -m uvicorn main:application --host 127.0.0.1 --port 8000 &`
then: `sleep 4 && curl -s http://localhost:8000/healthz && curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@test.io","password":"AdminPass1"}' | head -c 120`
Expected: healthz devuelve `{"status":"ok",...}` y el login devuelve un `token`.
Cleanup: `kill %1`

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/playwright.config.ts
git commit -m "test(e2e): run real backend + frontend via Playwright webServer"
```

---

## Task 2: Helpers de E2E (login de operador)

**Files:**
- Create: `apps/frontend/e2e/helpers.ts`

- [ ] **Step 1: Escribir los helpers**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/frontend/e2e/helpers.ts
git commit -m "test(e2e): add shared helpers (operator login, unique email)"
```

---

## Task 3: Flujo de operador — login, crear VCOO y errores

**Files:**
- Create: `apps/frontend/e2e/operador.spec.ts`

- [ ] **Step 1: Escribir el spec**

```typescript
import { test, expect } from '@playwright/test';
import { loginOperador, OPERADOR, emailUnico } from './helpers';

test.describe('operador', () => {
  test('login correcto lleva al panel de clientes', async ({ page }) => {
    await loginOperador(page);
    // El layout de operador debe estar visible (heading o nav de clientes).
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

  test('el operador puede crear un VCOO y recibe la URL de onboarding', async ({ page }) => {
    await loginOperador(page);
    // Ir al formulario de nuevo cliente.
    await page.goto('/operador/clientes/nuevo');
    const nombre = `E2E VCOO ${Date.now()}`;
    // El input de nombre no tiene id fijo garantizado; localizar por rol textbox.
    await page.getByRole('textbox').first().fill(nombre);
    await page.getByRole('button', { name: /crear/i }).click();
    // Tras crear, la página muestra el resultado con la URL de onboarding (/setup/).
    await expect(page.getByText(/\/setup\//)).toBeVisible({ timeout: 20000 });
  });
});
```

- [ ] **Step 2: Verificar los selectores contra la UI real**

Antes de dar por buenos los selectores (`getByRole('textbox').first()`, botón `/crear/i`, texto `/setup/`), lee `apps/frontend/src/pages/operador/Clientes/NuevoCliente.tsx` (líneas del formulario y del bloque `resultado`) y ajusta los localizadores si el texto del botón o la forma de mostrar la URL difieren. Si el nombre tiene un `id`/`label`, prefiérelo sobre `getByRole('textbox').first()`.

- [ ] **Step 3: Ejecutar solo este spec**

Run: `cd apps/frontend && npm run build && npx playwright test e2e/operador.spec.ts`
Expected: 3 passed.
Si falla por selector, ajusta según lo leído en el Step 2 y repite.

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/e2e/operador.spec.ts
git commit -m "test(e2e): operator login, login error and create VCOO flows"
```

---

## Task 4: Flujo del wizard — registro de cliente y modo demo

**Files:**
- Create: `apps/frontend/e2e/wizard.spec.ts`

- [ ] **Step 1: Leer el wizard para fijar selectores**

Lee `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx` centrándote en:
- El formulario de registro (caso `requires_registration`): campos de nombre, email, contraseña y botón de envío.
- Cómo se dispara la verificación/avance de paso (botón "Verificar" o similar).
Anota los textos/labels exactos para los localizadores del Step 2.

- [ ] **Step 2: Escribir el spec**

Este spec primero crea un VCOO vía API (más robusto que depender de la UI del operador para obtener el id), luego navega al wizard como cliente anónimo.

```typescript
import { test, expect, request as pwRequest } from '@playwright/test';
import { OPERADOR, emailUnico } from './helpers';

const API = 'http://localhost:8000';

// Crea un VCOO vía API y devuelve su id. Usa el login del operador por API.
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
    // El backend responde requires_registration=true; el wizard muestra el form.
    // AJUSTAR el texto/label según lo leído en el Step 1.
    await expect(page.getByText(/registr|crea tu cuenta|contraseña/i).first()).toBeVisible({
      timeout: 20000,
    });
  });

  test('un cliente puede registrarse y entrar al wizard', async ({ page }) => {
    const vcooId = await crearVcooViaApi();
    await page.goto(`/setup/${vcooId}`);

    // AJUSTAR estos localizadores a los campos reales del formulario de registro.
    const email = emailUnico();
    await page.getByLabel(/nombre/i).fill('Cliente E2E');
    await page.getByLabel(/email|correo/i).fill(email);
    await page.getByLabel(/contraseña|password/i).first().fill('ClientePass1');
    await page.getByRole('button', { name: /registr|crear cuenta|continuar/i }).click();

    // Tras registrarse, el wizard carga el estado (deja de pedir registro).
    // Señal robusta: aparece el indicador de progreso o el paso del wizard.
    await expect(page.getByText(/progreso|configuración|paso/i).first()).toBeVisible({
      timeout: 20000,
    });
  });
});
```

- [ ] **Step 3: Ejecutar y ajustar selectores**

Run: `cd apps/frontend && npm run build && npx playwright test e2e/wizard.spec.ts`
Expected: 2 passed.
Los localizadores marcados con "AJUSTAR" casi seguro necesitan afinarse tras leer el wizard (Step 1). Si un `getByLabel` no encuentra el campo (porque el input no está asociado a un `<label htmlFor>`), usa `getByPlaceholder` o un selector por `id`. Itera hasta verde. Usa `npx playwright test e2e/wizard.spec.ts --debug` o `--headed` si necesitas inspeccionar.

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/e2e/wizard.spec.ts
git commit -m "test(e2e): client registration and onboarding wizard (demo mode)"
```

---

## Task 5: Actualizar CI para arrancar el backend en el job E2E

**Files:**
- Modify: `.github/workflows/ci.yml` (job `frontend-e2e`)

- [ ] **Step 1: Añadir Python + deps del backend al job frontend-e2e**

El job `frontend-e2e` actual solo instala Node. Como ahora Playwright arranca el backend, hay que instalar Python 3.11 y las deps del backend. La `webServer` de Playwright ya arranca uvicorn con sus env vars (definidas en `playwright.config.ts`), así que **no** hace falta declararlas de nuevo en el YAML.

Reemplaza el job `frontend-e2e` completo por:

```yaml
  frontend-e2e:
    name: Frontend (Playwright E2E)
    runs-on: ubuntu-latest
    needs: frontend-unit
    defaults:
      run:
        working-directory: apps/frontend
    steps:
      - uses: actions/checkout@v5

      - name: Set up Node
        uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: apps/frontend/package-lock.json

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: pip

      - name: Install backend dependencies
        working-directory: apps/backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Install frontend dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium

      - name: Build frontend
        run: npm run build

      - name: Run E2E tests
        run: npm run test:e2e

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v6
        with:
          name: playwright-report
          path: apps/frontend/playwright-report/
          retention-days: 7
          if-no-files-found: ignore
```

- [ ] **Step 2: Validar el YAML**

Run: `cd /home/ubuntu/versus/vcoo-onboarding && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML valido')"`
Expected: `YAML valido`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: start real backend in the E2E job (install Python + deps)"
```

---

## Task 6: Verificación completa en local

- [ ] **Step 1: Ejecutar toda la suite E2E de una vez**

Run: `cd apps/frontend && npm run build && npx playwright test`
Expected: todos los tests pasan (3 smoke + 3 operador + 2 wizard = 8). Playwright arranca y para el backend y el frontend automáticamente.
Si algún test es intermitente (flaky) por timing, sube el `timeout` del `expect` correspondiente o añade un `await expect(...).toBeVisible()` sobre un elemento estable previo.

- [ ] **Step 2: Limpiar artefactos locales**

Run: `cd apps/frontend && rm -rf test-results playwright-report /tmp/e2e_test.db`

- [ ] **Step 3: Push y verificación de CI**

```bash
git push origin main
```
Luego espera al workflow y confirma que `Frontend (Playwright E2E)` termina en `success` con `gh run list` / `gh run view`.

---

## Self-review (cobertura del spec)

- **Login de operador** → Task 3, test "login correcto lleva al panel de clientes". ✓
- **Casos de error de login** → Task 3, test "login con contraseña incorrecta muestra error". ✓ (Rate limiting 429 se deja fuera a propósito: sería frágil en E2E y ya está cubierto en `test_auth.py::test_17_rate_limiting`.)
- **Crear VCOO (operador)** → Task 3, test "el operador puede crear un VCOO...". ✓
- **Registro de cliente en el wizard** → Task 4, test "un cliente puede registrarse y entrar al wizard". ✓
- **Wizard de onboarding (modo demo)** → Task 4, cubierto por el registro que carga el estado del wizard; el avance de paso en modo demo (auto_completed) queda validado a nivel API en `test_onboarding.py::test_verify_auto_completes_in_demo_mode`. Si se quiere el clic de "Verificar" en la UI, se puede añadir un test extra tras leer el wizard (Step 1 de Task 4), pero no se fuerza para no depender de timing del polling de 15s.

**Decisión de alcance registrada:** el rate limiting y el avance visual paso-a-paso del wizard se cubren a nivel API/unitario, no E2E, por robustez. El resto de flujos van E2E reales.

**Riesgo principal:** los selectores del wizard y del formulario de nuevo cliente son la parte más incierta (dependen del marcado real). Por eso las Tasks 3 y 4 incluyen un paso explícito de "leer el componente y ajustar selectores" antes de dar por bueno el test.
