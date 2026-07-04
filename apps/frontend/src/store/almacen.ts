import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { AppStoreState } from './tipos';

export const usarAlmacen = create<AppStoreState>()(
  devtools(
    persist(
      (set) => ({
        auth: {
          usuario: null,
          token: null as string | null,
          refreshToken: null as string | null,
          estaAutenticado: false,
          cargando: false,
          error: null,
        },

        app: {
          rol: null,
          barraLateralColapsada: false,
          tema: 'sistema' as const,
          notificaciones: [],
          cargandoGlobal: false,
        },

        cliente: null,

        operador: null,

        api: {
          ultimaEncuesta: null,
          estaRealizandoEncuesta: false,
          websocket: {
            conectado: false,
            intentosDeReconexion: 0,
            ultimoMensaje: null,
          },
          solicitudesPendientes: new Set<string>(),
          limitesDeError: {},
        },
      }),
      {
        name: 'almacenamiento-vcoo',
        partialize: (state) => ({
          app: state.app,
          cliente: state.cliente,
          operador: state.operador,
        }),
      }
    ),
    { name: 'vcoo-store' }
  )
);
