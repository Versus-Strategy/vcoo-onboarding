import { useEffect } from 'react';
import { usarAlmacen } from '../../../../store/almacen';
import { usarAccionesCliente } from '../../../../store/useAppStore';
import { useNavigate } from 'react-router-dom';
import Button from '../../../../components/Button';
import StepIndicator from '../../../../components/StepIndicator';
import StatusBadge from '../../../../components/StatusBadge';

const Finalizacion = () => {
  const navigate = useNavigate();
  const { establecerPasoDeIncorporacion } = usarAccionesCliente();
  const estado = usarAlmacen((state) => state);
  
  useEffect(() => {
    // Marcar el último paso como completado
    establecerPasoDeIncorporacion(4);
  }, [establecerPasoDeIncorporacion]);

  const cliente = estado.cliente;
  if (!cliente) {
    return <div>Cargando...</div>;
  }

  return (
    <div className="space-y-6">
      <StepIndicator
        pasoActual={4}
        pasosTotales={4}
        pasos={['Instalar Agente', 'Configurar Proveedor de IA', 'Configurar Módulos', 'Finalización']}
      />
      
      <div className="text-center">
        <div className="flex items-center justify-center mb-6">
          <div className="bg-green-100 text-green-800 rounded-full p-4">
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
        
        <h1 className="text-2xl font-bold text-gray-900 mb-4">¡Configuración Completada!</h1>
        <p className="text-gray-600 mb-6">
          Tu instancia de VCOO ha sido configurada exitosamente y está lista para usar.
        </p>
        
        <div className="space-y-4">
          <div className="border rounded-lg p-4 bg-white">
            <h3 className="font-semibold text-gray-900 mb-3">Resumen de Configuración</h3>
            
            <div className="space-y-3">
              <div className="flex items-center">
                <span className="mr-3 flex-shrink-0">
                  <StatusBadge estado={cliente.estadoDeInstalacion.agenteInstalado ? 'en-linea' : 'fuera-de-linea'} />
                </span>
                <div>
                  <h4 className="font-medium text-gray-900">Agente VCOO</h4>
                  <p className="text-sm text-gray-500">
                    {cliente.estadoDeInstalacion.agenteInstalado ? 'Instalado y activo' : 'No instalado'}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center">
                <span className="mr-3 flex-shrink-0">
                  <StatusBadge estado={cliente.estadoDeInstalacion.proveedorConectado ? 'en-linea' : 'fuera-de-linea'} />
                </span>
                <div>
                  <h4 className="font-medium text-gray-900">Proveedor de IA</h4>
                  <p className="text-sm text-gray-500">
                    {cliente.estadoDeInstalacion.proveedorConectado ? 'Conectado' : 'No conectado'}
                    {cliente.configuracionDeProveedor ? ` (${cliente.configuracionDeProveedor.nombre})` : ''}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center">
                <span className="mr-3 flex-shrink-0">
                  <span className="flex items-center">
                    {Object.keys(cliente.configuracionesDeModulo || {}).length > 0 ? (
                      <span className="mr-1">
                        <StatusBadge estado="en-linea" />
                      </span>
                    ) : (
                      <span className="mr-1">
                        <StatusBadge estado="fuera-de-linea" />
                      </span>
                    )}
                  </span>
                </span>
                <div>
                  <h4 className="font-medium text-gray-900">Módulos Configurados</h4>
                  <p className="text-sm text-gray-500">
                    {Object.keys(cliente.configuracionesDeModulo || {}).length} de 4 módulos configurados
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900 mb-2">Próximos Pasos</h3>
          <ol className="list-decimal list-inside space-y-2 text-gray-700">
            <li>Explora el panel de control para ver tus servicios activos</li>
            <li>Configura notificaciones y alertas según tus preferencias</li>
            <li>Invita a miembros de tu equipo para colaborar</li>
            <li>Programa tu primera tarea de automatización</li>
          </ol>
        </div>
        
        <div className="flex justify-center space-x-3">
          <Button variant="outline" size="sm" onClick={() => navigate('/servicios')}>
            Ir al Panel de Control
          </Button>
          <Button variant="secondary" size="sm" onClick={() => navigate('/configuracion/cuenta')}>
            Configuración de Cuenta
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Finalizacion;