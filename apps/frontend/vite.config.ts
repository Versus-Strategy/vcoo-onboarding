/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    react({
      fastRefresh: false,
    }),
    {
      name: 'remove-react-refresh-preamble',
      enforce: 'post',
      transformIndexHtml(html) {
        return html.replace(
          /<script type="module">import.*?react-refresh.*?<\/script>\n*/g,
          ''
        );
      },
    },
    {
      name: 'spa-fallback',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url && req.url.startsWith('/setup/') && !req.url.startsWith('/setup?token=')) {
            req.url = '/';
          }
          next();
        });
      },
    },
  ],
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      output: {
        // Separa las dependencias estables en su propio chunk para mejorar el
        // cacheo entre despliegues (el vendor cambia mucho menos que el código).
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'data-vendor': ['@tanstack/react-query', 'axios', 'zustand'],
          'icons-vendor': ['@heroicons/react/24/outline', '@thesvg/react'],
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src')
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
