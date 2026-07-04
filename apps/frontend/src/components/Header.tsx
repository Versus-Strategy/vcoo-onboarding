import React from 'react';
import { useAuth } from '../auth/authContext';

const Header: React.FC = () => {
  const { auth, cerrarSesion } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
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
              className="text-sm text-gray-500 hover:text-gray-700"
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
