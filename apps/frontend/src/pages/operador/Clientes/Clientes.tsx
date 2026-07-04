import { useNavigate } from 'react-router-dom';
import { useClientesOperador, useEliminarVCOO } from '@/query/useConsulta';
import { usarAccionesOperador } from '@/store/useAppStore';
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import StatusBadge from '@/components/StatusBadge';
import Button from '@/components/Button';

const statusMap: Record<string, string> = {
  active: 'en-linea',
  completed: 'pausado',
  offline: 'fuera-de-linea',
  in_progress: 'configurando',
  online: 'en-linea',
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type RowData = Record<string, any>;

const ClientesPage = () => {
  const navigate = useNavigate();
  const { data: clientes, isLoading, isError } = useClientesOperador();
  const { establecerClientes } = usarAccionesOperador();
  const eliminarVCOO = useEliminarVCOO();
  const queryClient = useQueryClient();

  // Store in zustand when data arrives
  useEffect(() => {
    if (clientes && clientes.length > 0) {
      establecerClientes(clientes as never);
    }
  }, [clientes, establecerClientes]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <HeaderRow navigate={navigate} />
        <div className="bg-white rounded-lg shadow p-6">
          <div className="animate-pulse space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-gray-200 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <HeaderRow navigate={navigate} />
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">Error al cargar clientes</h3>
          <p className="mt-2 text-sm text-gray-500">
            No se pudieron cargar los clientes. Intenta de nuevo más tarde.
          </p>
        </div>
      </div>
    );
  }

  const noData = !clientes || clientes.length === 0;

  return (
    <div className="space-y-6">
      <HeaderRow navigate={navigate} />

      {noData ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">No hay clientes registrados</h3>
          <p className="mt-2 text-sm text-gray-500">
            Crea tu primer cliente VCOO usando el botón &quot;Nuevo Cliente&quot;.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Nombre
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Creado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado del Agente
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {(clientes as unknown as RowData[]).map((cliente) => {
                const id = cliente.id as string;
                const nombre = (cliente.nombre as string) || 'Sin nombre';
                const estadoRaw = (cliente.estado as string) || 'offline';
                const estado = statusMap[estadoRaw] || estadoRaw || 'fuera-de-linea';
                const ultimoContacto = cliente.ultimoContacto as string | undefined;
                const servicios = cliente.servicios as RowData[] | undefined;
                const agenteEstado = servicios?.[0]?.estado as string || 'fuera-de-linea';

                return (
                  <tr
                    key={id}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/operador/clientes/${id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {nombre}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge estado={estado} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {ultimoContacto
                        ? new Date(ultimoContacto).toLocaleDateString('es-ES', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })
                        : '—'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge estado={agenteEstado} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/operador/clientes/${id}`);
                          }}
                        >
                          Ver detalle
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:bg-red-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`¿Estás seguro de eliminar el cliente "${nombre}"? Esta acción eliminará todos los datos asociados.`)) {
                              eliminarVCOO.mutate(id, {
                                onSuccess: () => {
                                  queryClient.invalidateQueries({ queryKey: ['operador', 'clientes'] });
                                },
                              });
                            }
                          }}
                        >
                          Eliminar
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

/** Small helper component for the page header row */
const HeaderRow = ({ navigate }: { navigate: ReturnType<typeof useNavigate> }) => (
  <div className="flex justify-between items-center">
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
      <p className="mt-1 text-sm text-gray-500">
        Gestiona todos los clientes VCOO registrados.
      </p>
    </div>
    <Button onClick={() => navigate('/operador/clientes/nuevo')}>
      + Nuevo Cliente
    </Button>
  </div>
);

export default ClientesPage;
