import { defineConfig, devices } from '@playwright/test';

/**
 * Configuración E2E de Playwright.
 *
 * `webServer` arranca `vite preview` (requiere `npm run build` previo, que el
 * job de CI ya ejecuta). Los tests corren contra el build de producción en el
 * puerto 4173 (por defecto de `vite preview`).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run preview -- --port 4173',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
