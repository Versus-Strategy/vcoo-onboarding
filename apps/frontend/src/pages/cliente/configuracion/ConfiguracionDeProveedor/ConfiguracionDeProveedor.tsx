import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usarAccionesCliente } from '../../../../store/useAppStore';
import StepIndicator from '../../../../components/StepIndicator';
import Button from '../../../../components/Button';
import Grid from '../../../../components/Grid';
import OAuthButton from '../../../../components/OAuthButton';

interface Proveedor {
  id: string;
  nombre: string;
  logo: string; // URL o path del logo
  color: string; // clase de color de Tailwind
}

const proveedores: Proveedor[] = [
  {
    id: 'anthropic',
    nombre: 'Anthropic',
    logo: 'https://www.anthropic.com/logo.svg',
    color: 'text-orange-600'
  },
  {
    id: 'openai',
    nombre: 'OpenAI',
    logo: 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/ChatGPT_logo.svg/640px-ChatGPT_logo.svg.png',
    color: 'text-green-600'
  },
  {
    id: 'google',
    nombre: 'Google',
    logo: 'https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png',
    color: 'text-blue-600'
  },
  {
    id: 'mistral',
    nombre: 'Mistral AI',
    logo: 'https://mistral.ai/logo.svg',
    color: 'text-purple-600'
  },
  {
    id: 'xai',
    nombre: 'xAI',
    logo: 'https://x.ai/logo.svg',
    color: 'text-gray-800'
  },
  {
    id: 'cohere',
    nombre: 'Cohere',
    logo: 'https://cohere.com/logo.svg',
    color: 'text-red-600'
  }
];

const ConfiguracionDeProveedor = () => {
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [conectando, setConectando] = useState<Record<string, boolean>>({});
  const navigate = useNavigate();
  const { establecerConfiguracionDeProveedor, establecerPasoDeIncorporacion, actualizarEstadoDeInstalacion } = usarAccionesCliente();

  const manejarSeleccion = (id: string) => {
    setSeleccionado(id);
  };

  const manejarConectar = async (id: string) => {
    setConectando(prev => ({ ...prev, [id]: true }));
    try {
      // Simular flujo de OAuth (en producción sería una llamada real)
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const proveedorSeleccionado = proveedores.find(p => p.id === id);
      if (proveedorSeleccionado) {
        establecerConfiguracionDeProveedor({
          id: proveedorSeleccionado.id,
          nombre: proveedorSeleccionado.nombre,
          tipo: 'IA'
        });
        
        // Actualizar el estado de instalación para indicar que el proveedor está conectado
        actualizarEstadoDeInstalacion({
          proveedorConectado: true
        });
        
        establecerPasoDeIncorporacion(2);
        navigate('/configuracion/configuracion-de-modulo/proveedor-ia');
      }
    } catch (error) {
      console.error('Error al conectar con el proveedor:', error);
      // En producción mostrar error al usuario
    } finally {
      setConectando(prev => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div className="space-y-6">
      <StepIndicator
        pasoActual={1}
        pasosTotales={4}
        pasos={['Instalar Agente', 'Configurar Proveedor de IA', 'Configurar Módulos', 'Finalización']}
      />
      
      <div className="space-y-4">
        <div className="border rounded-lg p-4 bg-gray-50">
          <h3 className="font-semibold text-gray-900 mb-2">
            Selecciona tu proveedor de IA preferido
          </h3>
          <p className="text-gray-600 mb-4">
            Este proveedor será utilizado para potenciar los servicios de VCOO
          </p>
          
          <Grid columns={3}>
            {proveedores.map(proveedor => (
              <div 
                key={proveedor.id} 
                className={`border rounded-lg p-4 text-center cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary-300 ${seleccionado === proveedor.id ? 'border-2 border-primary-500' : ''}`}
                onClick={() => manejarSeleccion(proveedor.id)}
              >
                <div className="mb-3">
                  <img src={proveedor.logo} alt={proveedor.nombre} className="h-12 w-auto mx-auto" />
                </div>
                <h4 className="font-medium text-gray-900 mb-2">{proveedor.nombre}</h4>
                <p className="text-sm text-gray-500">
                  Conectar cuenta
                </p>
              </div>
            ))}
          </Grid>
        </div>
        
        {seleccionado && (
          <div className="border-t pt-4">
            <div className="flex justify-between items-start">
              <Button
                onClick={() => manejarConectar(seleccionado!)}
                disabled={conectando[seleccionado!]}
                variant="primary"
                size="sm"
              >
                {conectando[seleccionado!] ? 'Conectando...' : `Conectar con ${proveedores.find(p => p.id === seleccionado!)?.nombre}`}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConfiguracionDeProveedor;