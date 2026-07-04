import { usarAlmacen } from './almacen';
import type { AppState, EstadoCliente, EstadoOperador } from './tipos';

// App state hooks
export const usarEstadoDeAplicacion = () => usarAlmacen((state) => state.app);

export const usarAccionesDeAplicacion = () => {
  return {
    establecerRol: (rol: 'cliente' | 'operador') =>
      usarAlmacen.setState((state) => ({ app: { ...state.app, rol } })),
    establecerBarraLateralColapsada: (colapsada: boolean) =>
      usarAlmacen.setState((state) => ({ app: { ...state.app, barraLateralColapsada: colapsada } })),
    establecerTema: (tema: AppState['tema']) =>
      usarAlmacen.setState((state) => ({ app: { ...state.app, tema } })),
    anadirNotificacion: (notificacion: Omit<AppState['notificaciones'][number], 'id'>) =>
      usarAlmacen.setState((state) => {
        const nuevaNotificacion = {
          ...notificacion,
          id: Math.random().toString(36).substring(2, 11),
        };
        return {
          app: {
            ...state.app,
            notificaciones: [...state.app.notificaciones, nuevaNotificacion],
          },
        };
      }),
    eliminarNotificacion: (id: string) =>
      usarAlmacen.setState((state) => ({
        app: {
          ...state.app,
          notificaciones: state.app.notificaciones.filter((n) => n.id !== id),
        },
      })),
    establecerCargandoGlobal: (cargando: boolean) =>
      usarAlmacen.setState((state) => ({ app: { ...state.app, cargandoGlobal: cargando } })),
  };
};

// Client state hooks
export const usarEstadoCliente = () => {
  const cliente = usarAlmacen((state) => state.cliente);
  if (!cliente) {
    throw new Error('Estado de cliente accedido cuando no está en modo cliente');
  }
  return cliente;
};

export const usarAccionesCliente = () => {
  return {
    establecerPasoDeIncorporacion: (paso: number) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return { cliente: { ...state.cliente, pasoDeIncorporacion: paso } };
        }
        return state;
      }),
    establecerServicios: (servicios: EstadoCliente['servicios']) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return { cliente: { ...state.cliente, servicios } };
        }
        return state;
      }),
    establecerServicioActual: (servicio: EstadoCliente['servicioActual']) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return { cliente: { ...state.cliente, servicioActual: servicio } };
        }
        return state;
      }),
    establecerConfiguracionDeProveedor: (config: EstadoCliente['configuracionDeProveedor']) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return { cliente: { ...state.cliente, configuracionDeProveedor: config } };
        }
        return state;
      }),
    agregarConfiguracionDeModulo: (idDeModulo: string, config: EstadoCliente['configuracionesDeModulo'][string]) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return {
            cliente: {
              ...state.cliente,
              configuracionesDeModulo: {
                ...state.cliente.configuracionesDeModulo,
                [idDeModulo]: config,
              },
            },
          };
        }
        return state;
      }),
    actualizarEstadoDeInstalacion: (actualizaciones: Partial<EstadoCliente['estadoDeInstalacion']>) =>
      usarAlmacen.setState((state) => {
        if (state.cliente) {
          return {
            cliente: {
              ...state.cliente,
              estadoDeInstalacion: {
                ...state.cliente.estadoDeInstalacion,
                ...actualizaciones,
              },
            },
          };
        }
        return state;
      }),
  };
};

// Operator state hooks
export const usarEstadoOperador = () => {
  const operador = usarAlmacen((state) => state.operador);
  if (!operador) {
    throw new Error('Estado de operador accedido cuando no está en modo operador');
  }
  return operador;
};

export const usarAccionesOperador = () => {
  return {
    establecerClientes: (clientes: EstadoOperador['clientes']) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, clientes },
      })),
    establecerClienteActual: (cliente: EstadoOperador['clienteActual']) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, clienteActual: cliente },
      })),
    establecerProductos: (productos: EstadoOperador['productos']) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, productos },
      })),
    establecerConsultaDeBusqueda: (consulta: string) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, consultaDeBusqueda: consulta },
      })),
    establecerFiltros: (filtros: EstadoOperador['filtros']) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, filtros },
      })),
    establecerPaginacion: (paginacion: EstadoOperador['paginacion']) =>
      usarAlmacen.setState((state) => ({
        operador: { ...state.operador!, paginacion },
      })),
  };
};
