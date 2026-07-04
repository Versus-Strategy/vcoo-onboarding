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
  resolve: {
    alias: {
      '@': resolve(__dirname, './src')
    }
  },
})
