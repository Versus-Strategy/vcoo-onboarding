import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/authContext';
import Footer from '@/components/Footer';
import Logo from '@/components/Logo';

const OperatorLayout = () => {
  const { auth, cerrarSesion } = useAuth();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium pb-2 border-b-2 transition-colors focus-ring ${
      isActive
        ? 'text-primary-600 border-primary-600'
        : 'text-gray-600 border-transparent hover:text-gray-700 hover:border-gray-300'
    }`;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg">
        Saltar al contenido
      </a>
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Logo />
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {auth.usuario?.nombre || 'Usuario'}
              </span>
              <button
                onClick={cerrarSesion}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors cursor-pointer focus-ring rounded-md"
              >
                Cerrar sesión
              </button>
            </div>
          </div>
          <nav className="flex space-x-6 -mb-px">
            <NavLink to="/operador/clientes" className={navLinkClass}>
              Clientes
            </NavLink>
            <NavLink to="/operador/clientes/nuevo" className={navLinkClass}>
              Nuevo Cliente
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="contenido" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

export default OperatorLayout;
