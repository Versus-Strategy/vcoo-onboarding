import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { ProveedorDeAuth } from './auth/authContext';
import { useAuth } from './auth/authContext';
import Login from './pages/Login/Login';
import ClientLayout from '@/layouts/ClientLayout';
import OperatorLayout from '@/layouts/OperatorLayout';
// Rutas de cliente (carga diferida)
const RutasCliente = lazy(() => import('@/rutas/rutasCliente'));
// Páginas de operador (carga diferida — no se descargan para clientes)
const ClientesPage = lazy(() => import('@/pages/operador/Clientes/Clientes'));
const NuevoClientePage = lazy(() => import('@/pages/operador/Clientes/NuevoCliente'));
const DetalleClientePage = lazy(() => import('@/pages/operador/Clientes/DetalleCliente'));
// Wizard público de onboarding (carga diferida — es el archivo más grande)
const SetupWizard = lazy(() => import('@/pages/public/SetupWizard/SetupWizard'));

/** Spinner de carga a pantalla completa, reutilizado para Suspense y sesión. */
const PantallaCarga = ({ texto = 'Cargando...' }: { texto?: string }) => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <div className="text-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
      <p className="text-gray-600">{texto}</p>
    </div>
  </div>
);

function AppContent() {
  const { auth } = useAuth();

  // Ruta pública para el wizard de onboarding — no requiere autenticación
  if (window.location.pathname.startsWith('/setup/') || window.location.pathname.startsWith('/onboarding/')) {
    return (
      <Suspense fallback={<PantallaCarga />}>
        <SetupWizard />
      </Suspense>
    );
  }

  // Mostrar pantalla de carga mientras se restaura la sesión
  if (auth.cargando) {
    return <PantallaCarga texto="Cargando sesión..." />;
  }

  if (!auth.estaAutenticado) {
    return <Login />;
  }

  // Redireccionar basado en el rol
  if (auth.usuario?.rol === 'cliente') {
    return (
      <ClientLayout>
        <Suspense fallback={<PantallaCarga />}>
          <RutasCliente />
        </Suspense>
      </ClientLayout>
    );
  } else if (auth.usuario?.rol === 'operador') {
    return (
      <Suspense fallback={<PantallaCarga />}>
        <Routes>
          <Route element={<OperatorLayout />}>
            <Route
              path="/operador"
              element={<Navigate to="/operador/clientes" replace />}
            />
            <Route path="/operador/clientes" element={<ClientesPage />} />
            <Route path="/operador/clientes/nuevo" element={<NuevoClientePage />} />
            <Route path="/operador/clientes/:id" element={<DetalleClientePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/operador" replace />} />
        </Routes>
      </Suspense>
    );
  }

  // Caso por defecto (no debería ocurrir)
  return <PantallaCarga texto="Redirigiendo según su rol..." />;
}

function App() {
  return (
    <ProveedorDeAuth>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<AppContent />} />
        </Routes>
      </BrowserRouter>
    </ProveedorDeAuth>
  );
}

export default App;
