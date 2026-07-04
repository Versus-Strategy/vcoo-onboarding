import type { AuthState } from '../auth/authContext';

export interface Servicio {
  id: string;
  nombre: string;
  estado: 'en-linea' | 'fuera-de-linea' | 'pausado' | 'configurando';
  modulos: string[];
  ultimoVisto: string; // ISO timestamp
}

export interface ConfiguracionDeModulo {
  id: string;
  nombre: string;
  configurado: boolean;
  proveedor: string | null;
  credenciales: Record<string, unknown> | null;
}

export interface EstadoCliente {
  pasoDeIncorporacion: number;
  servicios: Servicio[];
  servicioActual: Servicio | null;
  configuracionDeProveedor: {
    id: string;
    nombre: string;
    tipo: string;
  } | null;
  configuracionesDeModulo: Record<string, ConfiguracionDeModulo>;
  estadoDeInstalacion: {
    agenteInstalado: boolean;
    proveedorConectado: boolean;
    modulosConfigurados: Set<string>;
  };
}

export type EstadoClienteInfo = {
  id: string;
  nombre: string;
  email: string;
  estado: 'en-linea' | 'fuera-de-linea' | 'pausado';
  servicios: Servicio[];
  ultimoContacto: string;
};

export interface ClienteActual {
  id: string;
  nombre: string;
  email: string;
  telefono: string;
  direccion: string;
  servicios: Servicio[];
  estadisticas: {
    comandosEjecutados: number;
    tiempoActivoHoras: number;
    almacenamientoUtilizadoGB: number;
    integracionesActivas: number;
  };
}

export interface Producto {
  id: string;
  nombre: string;
  descripcion: string;
  precio: number;
  modulos: string[];
}

export interface EstadoOperador {
  clientes: EstadoClienteInfo[];
  clienteActual: ClienteActual | null;
  productos: Producto[];
  filtros: {
    estado: ('en-linea' | 'fuera-de-linea' | 'pausado')[];
    rangoDeFecha: { desde: string | null; hasta: string | null };
  };
  consultaDeBusqueda: string;
  paginacion: {
    pagina: number;
    limite: number;
    total: number;
  };
}

export interface AppState {
  rol: 'cliente' | 'operador' | null;
  barraLateralColapsada: boolean;
  tema: 'claro' | 'oscuro' | 'sistema';
  notificaciones: Array<{
    id: string;
    tipo: 'exito' | 'error' | 'advertencia' | 'informacion';
    mensaje: string;
    marcaDeTiempo: string;
  }>;
  cargandoGlobal: boolean;
}

export interface ApiState {
  ultimaEncuesta: number | null;
  estaRealizandoEncuesta: boolean;
  websocket: {
    conectado: boolean;
    intentosDeReconexion: number;
    ultimoMensaje: number | null;
  };
  solicitudesPendientes: Set<string>;
  limitesDeError: Record<string, string>;
}

export interface AppStoreState {
  auth: AuthState;
  app: AppState;
  cliente: EstadoCliente | null;
  operador: EstadoOperador | null;
  api: ApiState;
}
