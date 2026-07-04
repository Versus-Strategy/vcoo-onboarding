import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usarAlmacen } from '../../../../store/almacen';
import { usarAccionesCliente } from '../../../../store/useAppStore';
import Button from '../../../../components/Button';
import StepIndicator from '../../../../components/StepIndicator';

const InstalacionDeAgente = () => {
  const [estaInstalado, setEstaInstalado] = useState(false);
  const [ultimaVerificacion, setUltimaVerificacion] = useState<Date | null>(null);
  const [verificando, setVerificando] = useState(false);
  const navigate = useNavigate();
  const { establecerPasoDeIncorporacion, actualizarEstadoDeInstalacion } = usarAccionesCliente();

  const manejarCompletar = async () => {
    setVerificando(true);
    try {
      // Simular verificación de instalación
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Marcar como instalado en el estado local
      setEstaInstalado(true);
      setUltimaVerificacion(new Date());
      
      // Actualizar el estado de instalación en el almacén
      actualizarEstadoDeInstalacion({
        agenteInstalado: true
      });
      
      // Avanzar al siguiente paso
      establecerPasoDeIncorporacion(1);
    } catch (error) {
      console.error('Error al verificar instalación:', error);
      // En producción mostrar error al usuario
    } finally {
      setVerificando(false);
    }
  };

  return (
    <div className="space-y-6">
      <StepIndicator
        pasoActual={0}
        pasosTotales={4}
        pasos={['Instalar Agente', 'Configurar Proveedor de IA', 'Configurar Módulos', 'Finalización']}
      />
      
      <div className="space-y-4">
        <div className="border rounded-lg p-4 bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-2">
            Instalar el Agente VCOO
          </h3>
          <p className="text-gray-600 mb-4">
            Copie y ejecute el siguiente comando en su servidor para instalar el agente VCOO:
          </p>
          
          <div className="bg-gray-800 text-gray-100 rounded-lg p-4 font-mono mb-4">
            curl -sSL https://instalar.vcoo.dev | sudo bash
          </div>
          
          <p className="text-sm text-gray-500">
            Este comando instalará y configurará el agente VCOO en su sistema.
          </p>
          
          <div className="border-t pt-4">
            <div className="flex justify-end">
              <Button 
                onClick={manejarCompletar}
                disabled={verificando}
                variant="primary"
                size="sm"
              >
                {verificando ? 'Verificando...' : 'Marcar como completado'}
              </Button>
            </div>
          </div>
        </div>
        
        {estaInstalado && (
          <div className="border-t pt-4">
            <div className="flex items-center space-x-3">
              <span className="text-green-600 font-medium">✅ Instalado correctamente</span>
              <span className="text-sm text-gray-500">
                Última verificación: {ultimaVerificacion ? ultimaVerificacion.toLocaleTimeString() : 'Nunca'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InstalacionDeAgente;