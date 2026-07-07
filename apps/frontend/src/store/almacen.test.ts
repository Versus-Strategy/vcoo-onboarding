import { describe, it, expect, beforeEach } from 'vitest';
import { usarAlmacen } from './almacen';
import { usarAccionesDeAplicacion } from './useAppStore';

// Estado inicial limpio antes de cada test (el store es un singleton)
const estadoInicialApp = () => ({
  rol: null,
  barraLateralColapsada: false,
  tema: 'sistema' as const,
  notificaciones: [],
  cargandoGlobal: false,
});

describe('store de aplicación (zustand)', () => {
  beforeEach(() => {
    usarAlmacen.setState({ app: estadoInicialApp() });
  });

  it('establece el rol', () => {
    const { establecerRol } = usarAccionesDeAplicacion();
    establecerRol('operador');
    expect(usarAlmacen.getState().app.rol).toBe('operador');
  });

  it('colapsa la barra lateral', () => {
    const { establecerBarraLateralColapsada } = usarAccionesDeAplicacion();
    establecerBarraLateralColapsada(true);
    expect(usarAlmacen.getState().app.barraLateralColapsada).toBe(true);
  });

  it('añade una notificación con id generado', () => {
    const { anadirNotificacion } = usarAccionesDeAplicacion();
    anadirNotificacion({ tipo: 'exito', mensaje: 'Guardado' } as never);
    const notis = usarAlmacen.getState().app.notificaciones;
    expect(notis).toHaveLength(1);
    expect(notis[0].id).toBeTruthy();
    expect(notis[0].mensaje).toBe('Guardado');
  });

  it('elimina una notificación por id', () => {
    const { anadirNotificacion, eliminarNotificacion } = usarAccionesDeAplicacion();
    anadirNotificacion({ tipo: 'error', mensaje: 'Fallo' } as never);
    const id = usarAlmacen.getState().app.notificaciones[0].id;
    eliminarNotificacion(id);
    expect(usarAlmacen.getState().app.notificaciones).toHaveLength(0);
  });

  it('establece el estado de carga global', () => {
    const { establecerCargandoGlobal } = usarAccionesDeAplicacion();
    establecerCargandoGlobal(true);
    expect(usarAlmacen.getState().app.cargandoGlobal).toBe(true);
  });
});
