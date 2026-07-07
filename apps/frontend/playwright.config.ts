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
  // Los tests hacen varios logins reales; subimos el límite para no chocar con
  // el rate limiter (por defecto 5/300s en producción).
  LOGIN_RATE_MAX_ATTEMPTS: '1000',
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
      // Sirve el build de dist/. El build debe hacerse antes con
      // VITE_API_URL=http://localhost:8000 (ver script test:e2e / paso de CI)
      // para no depender de un .env local que apunte a otra IP.
      command: 'npm run preview -- --port 4173',
      url: 'http://localhost:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
