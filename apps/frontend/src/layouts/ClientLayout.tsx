import { Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';
import Header from '../components/Header';
import Footer from '../components/Footer';

const ClientLayout = ({ children }: { children?: ReactNode }) => {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg">
        Saltar al contenido
      </a>
      <Header />
      <main id="contenido" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children ?? <Outlet />}
      </main>
      <Footer />
    </div>
  );
};

export default ClientLayout;
