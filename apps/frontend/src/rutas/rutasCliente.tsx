import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '../auth/authContext';
import Servicios from '../pages/cliente/Servicios/Servicios';

const RedirectToOnboarding = () => {
  const { auth } = useAuth();
  const vcooId = auth.usuario?.vcoo_id;
  if (vcooId) {
    return <Navigate to={`/onboarding/${vcooId}`} replace />;
  }
  return <Navigate to="/servicios" replace />;
};

const RutasCliente = () => {
  return (
    <Routes>
      <Route path="/servicios" element={<Servicios />} />
      <Route path="/configuracion/*" element={<RedirectToOnboarding />} />
      <Route path="/" element={<Servicios />} />
    </Routes>
  );
};

export default RutasCliente;
