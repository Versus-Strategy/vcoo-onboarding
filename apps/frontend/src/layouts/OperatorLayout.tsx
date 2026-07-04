import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/authContext';
import Footer from '@/components/Footer';

const OperatorLayout = () => {
  const { auth, cerrarSesion } = useAuth();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium pb-2 border-b-2 transition-colors ${
      isActive
        ? 'text-primary-600 border-primary-600'
        : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'
    }`;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center">
              <span className="text-xl font-bold text-primary-600">VERSUS</span>
              <span className="ml-2 text-sm text-gray-400">| VCOO</span>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {auth.usuario?.nombre || 'Usuario'}
              </span>
              <button
                onClick={cerrarSesion}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
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
      <main className="flex-1 container mx-auto px-4 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

export default OperatorLayout;
