import React from 'react';
import { useAuth } from '../auth/authContext';

const Header: React.FC = () => {
  const { auth, cerrarSesion } = useAuth();

  return (
    <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center">
            <span className="text-xl font-bold text-primary-600">VERSUS</span>
            <span className="ml-2 text-sm text-gray-400 dark:text-gray-500">| VCOO</span>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {auth.usuario?.nombre || 'Usuario'}
            </span>
            <button
              onClick={cerrarSesion}
              className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
