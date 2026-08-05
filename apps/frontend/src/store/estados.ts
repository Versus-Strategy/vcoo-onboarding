/**
 * Fuente única de verdad para los estados de UI y su traducción desde los
 * estados crudos del backend. Evita que los `statusMap` duplicados por
 * página se desincronicen (era la causa de que "Sin provisionar" se mostrara
 * como "Fuera de línea" y de que el filtro de agente no coincidiera nunca).
 */

// Estados de UI que entiende StatusBadge.
export type EstadoUI =
  | 'en-linea'
  | 'fuera-de-linea'
  | 'sin-provisionar'
  | 'completado'
  | 'configurando'
  | 'bloqueado';

/**
 * Estado del VCOO (ciclo de vida): 'active' | 'completed' en el backend.
 * Nota: esto NO refleja si el agente está vivo, solo si el setup se dio por
 * terminado.
 */
export function mapEstadoVcoo(status: string | undefined | null): EstadoUI {
  switch (status) {
    case 'completed':
      return 'completado';
    case 'active':
      return 'en-linea';
    default:
      return 'sin-provisionar';
  }
}

/**
 * Estado real del AGENTE, independiente del ciclo de vida del VCOO.
 * - agente con status 'online'  -> en-linea
 * - agente con status 'offline' -> fuera-de-linea
 * - sin agente (nunca provisionado) -> sin-provisionar (NO "fuera de línea":
 *   distinguir "nunca instalado" de "instalado pero caído").
 */
export function mapEstadoAgente(agentStatus: string | undefined | null): EstadoUI {
  if (agentStatus === 'online') return 'en-linea';
  if (agentStatus === 'offline') return 'fuera-de-linea';
  return 'sin-provisionar';
}

/** Estado del onboarding: 'in_progress' | 'blocked' | 'completed' | 'unknown'. */
export function mapEstadoOnboarding(status: string | undefined | null): EstadoUI {
  switch (status) {
    case 'completed':
      return 'completado';
    case 'blocked':
      return 'bloqueado';
    case 'in_progress':
      return 'configurando';
    default:
      return 'configurando';
  }
}

// Colores (Tailwind) y etiquetas legibles por estado de UI.
export const coloresEstado: Record<EstadoUI, string> = {
  'en-linea': 'bg-green-100 text-green-800',
  'fuera-de-linea': 'bg-red-100 text-red-800',
  'sin-provisionar': 'bg-gray-100 text-gray-600',
  completado: 'bg-green-100 text-green-800',
  configurando: 'bg-primary-100 text-primary-800',
  bloqueado: 'bg-amber-100 text-amber-800',
};

export const etiquetasEstado: Record<EstadoUI, string> = {
  'en-linea': 'En línea',
  'fuera-de-linea': 'Fuera de línea',
  'sin-provisionar': 'Sin provisionar',
  completado: 'Completado',
  configurando: 'Configurando',
  bloqueado: 'Bloqueado',
};
