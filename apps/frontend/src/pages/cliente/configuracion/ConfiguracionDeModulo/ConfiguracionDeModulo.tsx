import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usarAccionesCliente } from '../../../../store/useAppStore';
import Button from '../../../../components/Button';
import Grid from '../../../../components/Grid';

const ConfiguracionDeModulo = () => {
  const { idDeModulo } = useParams<{ idDeModulo: string }>();
  const navigate = useNavigate();
  const { agregarConfiguracionDeModulo, actualizarEstadoDeInstalacion } = usarAccionesCliente();
  const [cargando, setCargando] = useState(false);
  const [seleccionadoProveedor, setSeleccionadoProveedor] = useState<string | null>(null);

  // Configuración específica por tipo de módulo
  const configuracionesModulo: Record<string, {
    titulo: string;
    descripcion: string;
    proveedores: Array<{ id: string; nombre: string; logo: string }>;
    permisos: string[];
  }> = {
    'proveedor-ia': {
      titulo: 'Conectar Proveedor de IA',
      descripcion: 'Conecta tu cuenta de proveedor de IA para habilitamiento de funcionalidades inteligentes',
      proveedores: [
        { id: 'anthropic', nombre: 'Anthropic', logo: 'https://upload.wikimedia.org/wikipedia/commons/0/09/Anthropic_logo.svg' },
        { id: 'openai', nombre: 'OpenAI', logo: 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg' },
        { id: 'google', nombre: 'Google', logo: 'https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg' },
        { id: 'xai', nombre: 'xAI', logo: 'https://pbs.twimg.com/profile_images/1633031917350174722/6vNvYvKK_400x400.jpg' }
      ],
      permisos: ['lectura de modelos', 'generación de texto']
    },
    'email': {
      titulo: 'Conectar Servicio de Email',
      descripcion: 'Conecta tu servicio de correo electrónico para notificaciones y comunicación',
      proveedores: [
        { id: 'gmail', nombre: 'Gmail', logo: 'https://upload.wikimedia.org/wikipedia/commons/4/44/Google_Gmail.svg' },
        { id: 'outlook', nombre: 'Outlook', logo: 'https://upload.wikimedia.org/wikipedia/commons/7/7e/Microsoft_Outlook_Logo_(2010-%25E2%2580%25932013).svg' },
        { id: 'sendgrid', nombre: 'SendGrid', logo: 'https://sendgrid.com/wp-content/uploads/2016/09/SendGrid_Logo_Blue_RGB.png' }
      ],
      permisos: ['envío de correos', 'lectura de bandeja de entrada']
    },
    'calendar': {
      titulo: 'Conectar Calendario',
      descripcion: 'Conecta tu servicio de calendario para programación y recordatorios',
      proveedores: [
        { id: 'google-calendar', nombre: 'Google Calendar', logo: 'https://upload.wikimedia.org/wikipedia/commons/1/19/Google_Calendar_icon.png' },
        { id: 'outlook-calendar', nombre: 'Outlook Calendar', logo: 'https://upload.wikimedia.org/wikipedia/commons/7/7e/Microsoft_Outlook_Logo_(2010-%25E2%2580%25932013).svg' }
      ],
      permisos: ['creación de eventos', 'lectura de calendario']
    },
    'storage': {
      titulo: 'Conectar Almacenamiento en la Nube',
      descripcion: 'Conecta tu servicio de almacenamiento en la nube para respaldos y archivos',
      proveedores: [
        { id: 'google-drive', nombre: 'Google Drive', logo: 'https://upload.wikimedia.org/wikipedia/commons/9/99/Unofficial_Google_Drive_logo.svg' },
        { id: 'dropbox', nombre: 'Dropbox', logo: 'https://upload.wikimedia.org/wikipedia/commons/2/2e/Dropbox_logo_blue_only.svg' },
        { id: 'aws-s3', nombre: 'AWS S3', logo: 'https://upload.wikimedia.org/wikipedia/commons/1/1b/Amazon_S3_Logo.svg' }
      ],
      permisos: ['lectura y escritura de archivos']
    }
  };

  const config = configuracionesModulo[idDeModulo || ''];

  const manejarConectar = async () => {
    if (!seleccionadoProveedor) return;

    setCargando(true);
    try {
      // Simular flujo de OAuth
      await new Promise(resolve => setTimeout(resolve, 1500));

      const proveedorSeleccionado = config.proveedores.find(p => p.id === seleccionadoProveedor);
      if (proveedorSeleccionado) {
        agregarConfiguracionDeModulo(idDeModulo!, {
          id: proveedorSeleccionado.id,
          nombre: proveedorSeleccionado.nombre,
          configurado: true,
          proveedor: proveedorSeleccionado.nombre,
          credenciales: { /* en producción, almacenar credenciales de forma segura */ }
        });

        // Actualizar el estado de instalación para marcar este módulo como configurado
        actualizarEstadoDeInstalacion((estadoActual) => ({
          modulosConfigurados: new Set([...estadoActual.modulosConfigurados, idDeModulo!])
        }));

        // Determinar siguiente paso basado en el módulo
        const siguienteModulo = obtenerSiguienteModulo(idDeModulo!);
        if (siguienteModulo) {
          navigate(`/configuracion/configuracion-de-modulo/${siguienteModulo}`);
        } else {
          navigate('/configuracion/finalizacion');
        }
      }
    } catch (error) {
      console.error('Error al conectar:', error);
    } finally {
      setCargando(false);
    }
  };

  const obtenerSiguienteModulo = (moduloActual: string): string | null => {
    const orden = ['proveedor-ia', 'email', 'calendar', 'storage'];
    const indiceActual = orden.indexOf(moduloActual);
    return indiceActual >= 0 && indiceActual < orden.length - 1 ? orden[indiceActual + 1] : null;
  };

  if (!config) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Módulo no encontrado</h1>
        <p className="text-gray-600">El módulo solicitado no está disponible.</p>
        <Button onClick={() => navigate('/configuracion/configuracion-de-proveedor')}>
          Volver a selección de proveedor
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="border rounded-lg p-4 bg-gray-50">
        <h3 className="font-semibold text-gray-900 mb-2">{config.titulo}</h3>
        <p className="text-gray-600 mb-4">{config.descripcion}</p>
        
        <div className="space-y-4">
          <div className="font-medium text-gray-700 mb-2">Proveedores disponibles:</div>
          <Grid columns={3}>
            {config.proveedores.map(proveedor => (
              <div 
                key={proveedor.id} 
                className={`border rounded-lg p-4 text-center cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary-300 ${seleccionadoProveedor === proveedor.id ? 'border-2 border-primary-500' : ''}`}
                onClick={() => setSeleccionadoProveedor(proveedor.id)}
              >
                <div className="mb-3">
                  <img src={proveedor.logo} alt={proveedor.nombre} className="h-10 w-auto mx-auto" />
                </div>
                <h4 className="font-medium text-gray-900">{proveedor.nombre}</h4>
              </div>
            ))}
          </Grid>
          
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-800 mb-2">Permisos solicitados:</h4>
            <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
              {config.permisos.map((permiso, index) => (
                <li key={index}>• {permiso}</li>
              ))}
            </ul>
          </div>
        </div>
        
        <div className="border-t pt-4">
          <div className="flex justify-end">
            <Button 
              onClick={manejarConectar}
              disabled={!seleccionadoProveedor || cargando}
              variant="primary"
              size="sm"
            >
              {cargando ? 'Conectando...' : 'Conectar y Continuar'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfiguracionDeModulo;