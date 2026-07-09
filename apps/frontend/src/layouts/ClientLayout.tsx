import { Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';
import Header from '../components/Header';
import Footer from '../components/Footer';

const ClientLayout = ({ children }: { children?: ReactNode }) => {
  return (
    <div className="min-h-screen flex flex-col dark bg-gray-950 text-gray-100">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-6">
        {children ?? <Outlet />}
      </main>
      <Footer />
    </div>
  );
};

export default ClientLayout;
