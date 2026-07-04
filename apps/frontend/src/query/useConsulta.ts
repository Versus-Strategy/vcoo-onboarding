import { useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '../api/apiClient';
import type { Servicio } from '../store/tipos';

// Generic query hook
export function useApiConsulta<TData = unknown, TError = unknown>(
  key: string[],
  queryFn: () => Promise<TData>,
  options?: {
    staleTime?: number;
    cacheTime?: number;
  }
) {
  return useQuery<TData, TError>({
    queryKey: key,
    queryFn,
    ...options,
  });
}

// Generic mutation hook
export function useApiMutacion<TData = unknown, TVariables = void, TError = unknown>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: {
    onSuccess?: (data: TData, variables: TVariables, context: unknown) => void;
    onError?: (error: TError, variables: TVariables, context: unknown) => void;
    onSettled?: (
      data: TData | undefined,
      error: TError | null,
      variables: TVariables,
      context: unknown
    ) => void;
  }
) {
  return useMutation<TData, TError, TVariables>({
    mutationFn,
    onSuccess: (data, variables, context) => {
      options?.onSuccess?.(data, variables, context);
    },
    onError: (error, variables, context) => {
      options?.onError?.(error, variables, context);
    },
    onSettled: (data, error, variables, context) => {
      options?.onSettled?.(data, error, variables, context);
    },
  });
}

// ── Mapeo de VCOO (backend) a Servicio (frontend) ──

function vcooToServicio(vcoo: Record<string, unknown>): Servicio {
  const agent = vcoo.agent as Record<string, unknown> | undefined;
  let estado: string;

  if (vcoo.status === 'completed') {
    estado = 'pausado';
  } else if (agent) {
    // Agent exists — use its computed online/offline status
    estado = agent.status === 'online' ? 'en-linea' : 'fuera-de-linea';
  } else {
    // No agent yet — pending provisioning
    estado = 'configurando';
  }

  return {
    id: vcoo.id as string,
    nombre: (vcoo.name as string) || 'VCOO Sin Nombre',
    estado,
    modulos: (vcoo.modules as string[]) || ['core'],
    ultimoVisto: (agent?.last_seen as string)
      || (vcoo.created_at as string)
      || new Date().toISOString(),
  };
}

// ── Client Service Hooks ──

/** Get services for a client (list of VCOOs) */
export const useServiciosCliente = () => {
  return useApiConsulta<Servicio[], Error>(
    ['cliente', 'servicios'],
    () => apiClient.get('/vcoos').then((res) =>
      (res.data as Record<string, unknown>[]).map(vcooToServicio)
    ),
    { staleTime: 2 * 60 * 1000 }
  );
};

/** Get onboarding/installation state for a client */
export const useEstadoDeIncorporacionCliente = (vcooId: string) => {
  return useApiConsulta<{ paso: number; estado: string }, Error>(
    ['cliente', 'estado-incorporacion', vcooId],
    () => apiClient.get(`/vcoo/${vcooId}/state`).then((res) => {
      const data = res.data as Record<string, unknown>;
      return {
        paso: ((data.completed_steps as string[]) || []).length,
        estado: (data.onboarding_status as string) || 'in_progress',
      };
    })
  );
};

/** Create a new VCOO (service) for a client */
export const useCrearVCOO = () => {
  return useMutation({
    mutationFn: (variables: { name: string; modules?: string[] }) =>
      apiClient.post('/vcoo', {
        name: variables.name,
        modules: variables.modules || ['core'],
      }).then(res => res.data),
  });
};

/** Delete a VCOO (cascading delete) */
export const useEliminarVCOO = () => {
  return useMutation({
    mutationFn: (vcooId: string) =>
      apiClient.delete(`/vcoo/${vcooId}`).then(res => res.data),
  });
};

/** Get provision token for a VCOO */
export const useTokenDeProvision = (vcooId: string) => {
  return useApiConsulta<{ token: string; install_command: string }, Error>(
    ['vcoo', vcooId, 'token'],
    () => apiClient.get(`/vcoo/${vcooId}/provision-token`).then(res => res.data as { token: string; install_command: string }),
    { staleTime: 60 * 1000 }
  );
};

// ── Operator Hooks ──

interface ClienteInfo {
  id: string;
  nombre: string;
  email: string;
  estado: string;
  servicios: Servicio[];
  ultimoContacto: string;
}

/** Get all VCOOs (client list) for operator */
export const useClientesOperador = () => {
  return useApiConsulta<ClienteInfo[], Error>(
    ['operador', 'clientes'],
    () => apiClient.get('/vcoos').then((res) => {
      const vcoos = res.data as Record<string, unknown>[];
      return vcoos.map(v => ({
        id: v.id as string,
        nombre: (v.name as string) || 'Sin nombre',
        email: (v.name as string)?.toLowerCase().replace(/\s+/g, '.') + '@cliente.vcoo' || 'desconocido@vcoo',
        estado: (v.status as string) || 'offline',
        servicios: [vcooToServicio(v)],
        ultimoContacto: ((v.agent as Record<string, unknown>)?.last_seen as string) || (v.created_at as string) || '',
      }));
    }),
    { staleTime: 5 * 60 * 1000 }
  );
};

/** Get detail for a specific VCOO */
export const useDetalleVCOO = (vcooId: string) => {
  return useApiConsulta<Record<string, unknown>, Error>(
    ['vcoo', vcooId, 'detail'],
    () => apiClient.get(`/vcoo/${vcooId}/state`).then(res => res.data as Record<string, unknown>),
  );
};
