import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';
import { queryClient } from './query/clienteDeConsulta';
import { useTiempoReal } from './tiempo-real/useTiempoReal';

const queryClientInstance = queryClient;

const AppConProveedores = () => {
  useTiempoReal(); // Initialize real-time connection

  return (
    <QueryClientProvider client={queryClientInstance}>
      <App />
    </QueryClientProvider>
  );
};

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppConProveedores />
  </React.StrictMode>
);
