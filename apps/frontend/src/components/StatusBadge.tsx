import React from 'react';
import { coloresEstado, etiquetasEstado } from '../store/estados';

interface StatusBadgeProps {
  estado: string;
}

// Alias retrocompatibles hacia los estados de UI canónicos.
const alias: Record<string, string> = {
  pausado: 'completado', // antes "pausado" representaba un VCOO completado
  bloqueado: 'bloqueado',
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ estado }) => {
  const key = alias[estado] || estado;
  const colorClass = coloresEstado[key as keyof typeof coloresEstado] || 'bg-gray-100 text-gray-800';
  const label = etiquetasEstado[key as keyof typeof etiquetasEstado] || estado;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
};

export default StatusBadge;
