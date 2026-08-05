import React from 'react';
import { useNavigate } from 'react-router-dom';
import StatusBadge from '@/components/StatusBadge';
import Button from '@/components/Button';

interface ClienteCardProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cliente: Record<string, any>;
  onEliminar: () => void;
}

const ClienteCard: React.FC<ClienteCardProps> = ({ cliente, onEliminar }) => {
  const navigate = useNavigate();
  const id = cliente.id as string;
  const nombre = (cliente.nombre as string) || 'Sin nombre';
  const estado = (cliente.estado as string) || 'sin-provisionar';
  const ultimoContacto = cliente.ultimoContacto as string | undefined;
  const agenteEstado = (cliente.servicios?.[0]?.estado as string) || 'sin-provisionar';
  const modulos = cliente.servicios?.[0]?.modulos as string[] | undefined;

  return (
    <div className="bg-white rounded-lg shadow-sm p-4 space-y-3 hover:bg-gray-50 transition-colors">
      <button
        type="button"
        onClick={() => navigate(`/operador/clientes/${id}`)}
        className="w-full text-left focus-ring rounded-lg cursor-pointer"
      >
        <span className="text-sm font-medium text-gray-900 break-words block">{nombre}</span>
      </button>
      {modulos && modulos.filter(m => m !== 'core').length > 0 && (
        <div className="flex flex-wrap gap-1">
          {modulos.filter(m => m !== 'core').slice(0, 3).map(m => (
            <span key={m} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{m}</span>
          ))}
        </div>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <dt className="text-gray-500 text-xs">Estado VCOO</dt>
          <dd className="mt-0.5"><StatusBadge estado={estado} /></dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">Agente</dt>
          <dd className="mt-0.5"><StatusBadge estado={agenteEstado} /></dd>
        </div>
        <div className="col-span-2">
          <dt className="text-gray-500 text-xs">Último contacto</dt>
          <dd className="mt-0.5 text-gray-900">
            {ultimoContacto
              ? new Date(ultimoContacto).toLocaleDateString('es-ES', {
                  year: 'numeric', month: 'short', day: 'numeric',
                })
              : '—'}
          </dd>
        </div>
      </dl>
      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="ghost"
          size="sm"
          className="flex-1"
          onClick={() => navigate(`/operador/clientes/${id}`)}
        >
          Ver detalle
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="flex-1 text-red-600 hover:bg-red-50"
          onClick={onEliminar}
        >
          Eliminar
        </Button>
      </div>
    </div>
  );
};

export default ClienteCard;
