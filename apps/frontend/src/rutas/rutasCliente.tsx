import { Routes, Route } from 'react-router-dom';
import Servicios from '../pages/cliente/Servicios/Servicios';
import InstalacionDeAgente from '../pages/cliente/configuracion/InstalacionDeAgente/InstalacionDeAgente';
import ConfiguracionDeProveedor from '../pages/cliente/configuracion/ConfiguracionDeProveedor/ConfiguracionDeProveedor';
import ConfiguracionDeModulo from '../pages/cliente/configuracion/ConfiguracionDeModulo/ConfiguracionDeModulo';
import Finalizacion from '../pages/cliente/configuracion/Finalizacion/Finalizacion';

const RutasCliente = () => {
  return (
    <Routes>
      <Route path="/servicios" element={<Servicios />} />
      <Route path="/configuracion/instalacion-de-agente" element={<InstalacionDeAgente />} />
      <Route path="/configuracion/configuracion-de-proveedor" element={<ConfiguracionDeProveedor />} />
      <Route path="/configuracion/configuracion-de-modulo/:idDeModulo" element={<ConfiguracionDeModulo />} />
      <Route path="/configuracion/finalizacion" element={<Finalizacion />} />
      <Route path="/" element={<Servicios />} />
    </Routes>
  );
};

export default RutasCliente;
