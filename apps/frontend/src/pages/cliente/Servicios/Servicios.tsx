import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useServiciosCliente } from '../../../query/useConsulta';
import { usarAccionesCliente } from '../../../store/useAppStore';
import StatusBadge from '../../../components/StatusBadge';
import DataTable from '../../../components/DataTable';
import Button from '../../../components/Button';
import type { Servicio } from '../../../store/tipos';

const ServiciosPage = () => {
  const { data: servicios, isLoading, isFetching, refetch } = useServiciosCliente();
  const { establecerServicios } = usarAccionesCliente();
  const navigate = useNavigate();
  const [serviciosData, setServiciosData] = useState<Record<string, unknown>[]>([]);

  // Update client state when services data changes
  useEffect(() => {
    if (servicios !== undefined && servicios.length > 0) {
      setServiciosData(
        servicios.map((svc: Servicio) => ({
          id: svc.id,
          nombre: svc.nombre,
          estado: svc.estado,
          modulos: svc.modulos,
          ultimoVisto: svc.ultimoVisto,
        }))
      );
      establecerServicios(servicios);
    }
  }, [servicios, establecerServicios]);

  const irAConfiguracion = (id: unknown) => {
    if (id) navigate(`/onboarding/${id}`);
  };

  const columns = [
    { accessor: 'nombre', label: 'Servicio' },
    {
      accessor: 'estado',
      label: 'Estado',
      render: (value: unknown) => <StatusBadge estado={value as string} />,
    },
    {
      accessor: 'modulos',
      label: 'Módulos',
      render: (value: unknown) => `${(value as string[]).length} activos`,
    },
    {
      accessor: 'ultimoVisto',
      label: 'Último visto',
      render: (value: unknown) => new Date(value as string).toLocaleString(),
    },
    {
      accessor: 'acciones',
      label: 'Acciones',
      render: (_value: unknown, row: Record<string, unknown>) => (
        <Button variant="secondary" size="sm" onClick={() => irAConfiguracion(row.id)}>
          Configurar
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Tus Servicios VCOO</h1>
        <Button variant="secondary" onClick={() => refetch()} loading={isFetching}>
          Actualizar lista
        </Button>
      </div>

      {/* Tabla (escritorio) */}
      <div className="hidden md:block">
        <DataTable
          columns={columns}
          data={serviciosData}
          loading={isLoading}
          emptyState={{
            title: 'No tienes servicios activos',
            description: 'Contacta a soporte para activar servicios VCOO',
          }}
        />
      </div>

      {/* Tarjetas (móvil) */}
      <div className="md:hidden space-y-3">
        {isLoading ? (
          [1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-lg shadow p-4 animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/2" />
              <div className="h-3 bg-gray-200 rounded w-1/3" />
            </div>
          ))
        ) : serviciosData.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <h3 className="text-base font-medium text-gray-900">No tienes servicios activos</h3>
            <p className="mt-2 text-sm text-gray-500">Contacta a soporte para activar servicios VCOO</p>
          </div>
        ) : (
          serviciosData.map((svc) => (
            <div key={svc.id as string} className="bg-white rounded-lg shadow p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-base font-semibold text-gray-900 break-words">{svc.nombre as string}</h3>
                <StatusBadge estado={svc.estado as string} />
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div>
                  <dt className="text-gray-500">Módulos</dt>
                  <dd className="text-gray-900">{(svc.modulos as string[]).length} activos</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Último visto</dt>
                  <dd className="text-gray-900">{new Date(svc.ultimoVisto as string).toLocaleDateString()}</dd>
                </div>
              </dl>
              <Button variant="secondary" size="sm" className="w-full" onClick={() => irAConfiguracion(svc.id)}>
                Configurar
              </Button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ServiciosPage;
