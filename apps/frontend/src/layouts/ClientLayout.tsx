import { Outlet } from 'react-router-dom';
import Header from '../components/Header';
import Footer from '../components/Footer';

const ClientLayout = () => {
  return (
    <div className="min-h-screen flex flex-col dark bg-gray-950 text-gray-100">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

export default ClientLayout;
// Updated to fix TypeScript import issue