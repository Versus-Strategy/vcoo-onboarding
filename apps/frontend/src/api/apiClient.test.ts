import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { AxiosRequestConfig, AxiosAdapter } from 'axios';
import apiClient from './apiClient';

/**
 * Estos tests ejercitan los interceptores de apiClient sin red real:
 * - request interceptor: adjunta el Bearer desde localStorage.
 * - response interceptor: refresh en 401, no reintento en 429.
 *
 * Sustituimos el adapter de axios por una función controlada por el test.
 */

function setAdapter(fn: AxiosAdapter) {
  apiClient.defaults.adapter = fn;
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  // reset del adapter por defecto entre tests
  setAdapter(async (config) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }));
});

describe('apiClient — request interceptor', () => {
  it('adjunta Authorization Bearer desde localStorage', async () => {
    localStorage.setItem('vcoo-auth', JSON.stringify({ token: 'abc123' }));
    let seen: AxiosRequestConfig | undefined;
    setAdapter(async (config) => {
      seen = config;
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    });

    await apiClient.get('/whatever');
    expect(seen?.headers?.Authorization).toBe('Bearer abc123');
  });

  it('no adjunta Authorization si no hay token guardado', async () => {
    let seen: AxiosRequestConfig | undefined;
    setAdapter(async (config) => {
      seen = config;
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    });

    await apiClient.get('/whatever');
    expect(seen?.headers?.Authorization).toBeUndefined();
  });

  it('ignora JSON corrupto en localStorage sin lanzar', async () => {
    localStorage.setItem('vcoo-auth', '{not valid json');
    await expect(apiClient.get('/whatever')).resolves.toBeDefined();
  });
});

describe('apiClient — response interceptor', () => {
  it('propaga el error 429 sin reintentar', async () => {
    let calls = 0;
    setAdapter(async (config) => {
      calls += 1;
      return Promise.reject({
        config,
        response: { status: 429, data: {}, statusText: 'Too Many', headers: {} },
      });
    });

    await expect(apiClient.get('/limited')).rejects.toBeDefined();
    expect(calls).toBe(1); // no reintento
  });

  it('renueva el token en 401 y reintenta la petición original', async () => {
    localStorage.setItem(
      'vcoo-auth',
      JSON.stringify({ token: 'old', refreshToken: 'refresh-1' })
    );

    let phase = 0;
    setAdapter(async (config) => {
      const url = config.url || '';
      if (url.includes('/auth/refresh')) {
        // El refresh devuelve un token nuevo
        return {
          data: { token: 'new-token' },
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        };
      }
      // Primera llamada al recurso: 401. Segunda (tras refresh): 200.
      phase += 1;
      if (phase === 1) {
        return Promise.reject({
          config,
          response: { status: 401, data: {}, statusText: 'Unauthorized', headers: {} },
        });
      }
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
    });

    const res = await apiClient.get('/protegido');
    expect(res.status).toBe(200);
    expect(res.data).toEqual({ ok: true });

    // El nuevo token se persistió en localStorage
    const stored = JSON.parse(localStorage.getItem('vcoo-auth') || '{}');
    expect(stored.token).toBe('new-token');
  });
});
