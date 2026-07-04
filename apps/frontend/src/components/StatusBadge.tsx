import React from 'react';

interface StatusBadgeProps {
  estado: string;
}

const statusColors: Record<string, string> = {
  'en-linea': 'bg-green-100 text-green-800',
  'fuera-de-linea': 'bg-red-100 text-red-800',
  pausado: 'bg-yellow-100 text-yellow-800',
  configurando: 'bg-blue-100 text-blue-800',
};

const statusLabels: Record<string, string> = {
  'en-linea': 'En línea',
  'fuera-de-linea': 'Fuera de línea',
  pausado: 'Pausado',
  configurando: 'Configurando',
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ estado }) => {
  const colorClass = statusColors[estado] || 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {statusLabels[estado] || estado}
    </span>
  );
};

export default StatusBadge;
