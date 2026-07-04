import { useEffect, useState } from 'react';
import { useServiciosCliente } from '../../../query/useConsulta';
import { usarAccionesCliente } from '../../../store/useAppStore';
import StatusBadge from '../../../components/StatusBadge';
import DataTable from '../../../components/DataTable';
import Button from '../../../components/Button';
import type { Servicio } from '../../../store/tipos';

const ServiciosPage = () => {
  const { data: servicios, isLoading, isError } = useServiciosCliente();
  const { establecerServicios } = usarAccionesCliente();
  const [serviciosData, setServiciosData] = useState<Record<string, unknown>[]>([]);

  // Update client state when services data changes
  useEffect(() => {
    if (servicios !== undefined && servicios.length > 0) {
      setServiciosData(
        servicios.map((svc: Servicio) => ({
          nombre: svc.nombre,
          estado: svc.estado,
          modulos: svc.modulos,
          ultimoVisto: svc.ultimoVisto,
        }))
      );
      establecerServicios(servicios);
    }
  }, [servicios, establecerServicios]);

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
      render: () => (
        <Button variant="secondary" size="sm">
          Configurar
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Tus Servicios VCOO</h1>
        <Button variant="secondary" onClick={() => window.location.reload()}>
          Actualizar lista
        </Button>
      </div>

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
  );
};

export default ServiciosPage;
