import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClientesOperador, useEliminarVCOO } from '@/query/useConsulta';
import { usarAccionesOperador } from '@/store/useAppStore';
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import StatusBadge from '@/components/StatusBadge';
import Button from '@/components/Button';
import { ChevronUpDownIcon, ChevronUpIcon, ChevronDownIcon } from '@/components/icons';

const statusMap: Record<string, string> = {
  active: 'en-linea',
  completed: 'completado',
  offline: 'fuera-de-linea',
  in_progress: 'configurando',
  online: 'en-linea',
};

// Etiquetas legibles para los chips de filtro (independientes del mapa interno de estados)
const filtroEstadoLabels: Record<string, string> = {
  active: 'Activo',
  completed: 'Completado',
};
const filtroAgenteLabels: Record<string, string> = {
  online: 'En línea',
  offline: 'Fuera de línea',
};

type SortField = 'nombre' | 'estado' | 'ultimoContacto' | 'agente';
type SortDir = 'asc' | 'desc';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type RowData = Record<string, any>;

const ClientesPage = () => {
  const navigate = useNavigate();
  const { data: clientes, isLoading, isError } = useClientesOperador();
  const { establecerClientes } = usarAccionesOperador();
  const eliminarVCOO = useEliminarVCOO();
  const queryClient = useQueryClient();

  const [busqueda, setBusqueda] = useState('');
  const [filtroEstado, setFiltroEstado] = useState<string | null>(null);
  const [filtroAgente, setFiltroAgente] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('ultimoContacto');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Store in zustand when data arrives
  useEffect(() => {
    if (clientes && clientes.length > 0) {
      establecerClientes(clientes as never);
    }
  }, [clientes, establecerClientes]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const handleEliminar = (id: string, nombre: string) => {
    if (window.confirm(`¿Estás seguro de eliminar el cliente "${nombre}"? Esta acción eliminará todos los datos asociados.`)) {
      eliminarVCOO.mutate(id, {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['operador', 'clientes'] });
        },
      });
    }
  };

  const filtrados = useMemo(() => {
    if (!clientes) return [];
    let items = clientes as unknown as RowData[];
    if (busqueda) {
      const q = busqueda.toLowerCase();
      items = items.filter(c => (c.nombre as string || '').toLowerCase().includes(q));
    }
    if (filtroEstado) {
      items = items.filter(c => c.estado === filtroEstado);
    }
    if (filtroAgente) {
      items = items.filter(c => {
        const ag = c.servicios?.[0]?.estado as string || 'offline';
        return ag === filtroAgente;
      });
    }
    items.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'nombre') cmp = (a.nombre || '').localeCompare(b.nombre || '');
      else if (sortField === 'estado') cmp = (a.estado || '').localeCompare(b.estado || '');
      else if (sortField === 'ultimoContacto') cmp = (a.ultimoContacto || '').localeCompare(b.ultimoContacto || '');
      else if (sortField === 'agente') cmp = ((a.servicios?.[0]?.estado as string) || '').localeCompare((b.servicios?.[0]?.estado as string) || '');
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return items;
  }, [clientes, busqueda, filtroEstado, filtroAgente, sortField, sortDir]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronUpDownIcon className="inline-block ml-1 w-3.5 h-3.5 text-gray-300" />;
    return sortDir === 'asc'
      ? <ChevronUpIcon className="inline-block ml-1 w-3.5 h-3.5 text-primary-600" />
      : <ChevronDownIcon className="inline-block ml-1 w-3.5 h-3.5 text-primary-600" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <HeaderRow navigate={navigate} total={0} />
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
        <HeaderRow navigate={navigate} total={0} />
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
      <HeaderRow navigate={navigate} total={clientes?.length || 0} />

      {noData ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">No hay clientes registrados</h3>
          <p className="mt-2 text-sm text-gray-500">
            Crea tu primer cliente VCOO usando el botón &quot;Nuevo Cliente&quot;.
          </p>
        </div>
      ) : (
        <>
          {/* Búsqueda y filtros */}
          <div className="bg-white rounded-lg shadow p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Buscar por nombre..."
                  value={busqueda}
                  onChange={e => setBusqueda(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-gray-500 font-medium mr-1 self-center">VCOO:</span>
              {['active', 'completed'].map(s => (
                <button
                  key={s}
                  onClick={() => setFiltroEstado(filtroEstado === s ? null : s)}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                    filtroEstado === s
                      ? 'bg-primary-100 border-primary-300 text-primary-800'
                      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  {filtroEstadoLabels[s] || s}
                </button>
              ))}
              <span className="text-xs text-gray-500 font-medium mx-1 self-center">| Agente:</span>
              {['online', 'offline'].map(s => (
                <button
                  key={s}
                  onClick={() => setFiltroAgente(filtroAgente === s ? null : s)}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                    filtroAgente === s
                      ? 'bg-primary-100 border-primary-300 text-primary-800'
                      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-400'
                  }`}
                >
                  {filtroAgenteLabels[s] || s}
                </button>
              ))}
              {(busqueda || filtroEstado || filtroAgente) && (
                <button
                  onClick={() => { setBusqueda(''); setFiltroEstado(null); setFiltroAgente(null); }}
                  className="text-xs text-primary-600 hover:text-primary-700 ml-2"
                >
                  Limpiar filtros
                </button>
              )}
            </div>
          </div>

          {/* Tabla (escritorio) */}
          <div className="hidden md:block bg-white rounded-lg shadow overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {(['nombre', 'estado', 'ultimoContacto', 'agente'] as SortField[]).map(field => (
                    <th
                      key={field}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700 select-none"
                      onClick={() => toggleSort(field)}
                    >
                      {field === 'nombre' ? 'Nombre' : field === 'estado' ? 'Estado VCOO' : field === 'ultimoContacto' ? 'Último contacto' : 'Agente'}
                      <SortIcon field={field} />
                    </th>
                  ))}
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filtrados.map((cliente: RowData) => {
                  const id = cliente.id as string;
                  const nombre = (cliente.nombre as string) || 'Sin nombre';
                  const estadoRaw = (cliente.estado as string) || 'offline';
                  const estado = statusMap[estadoRaw] || estadoRaw || 'fuera-de-linea';
                  const ultimoContacto = cliente.ultimoContacto as string | undefined;
                  const agenteEstado = statusMap[cliente.servicios?.[0]?.estado as string] || 'fuera-de-linea';
                  const modulos = cliente.servicios?.[0]?.modulos as string[] | undefined;

                  return (
                    <tr
                      key={id}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/operador/clientes/${id}`)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{nombre}</div>
                        {modulos && modulos.length > 0 && (
                          <div className="flex gap-1 mt-1">
                            {modulos.filter(m => m !== 'core').slice(0, 3).map(m => (
                              <span key={m} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{m}</span>
                            ))}
                          </div>
                        )}
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
                              handleEliminar(id, nombre);
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
            {filtrados.length === 0 && (
              <div className="text-center py-8 text-sm text-gray-500">
                No se encontraron clientes con los filtros actuales.
              </div>
            )}
          </div>

          {/* Tarjetas (móvil) */}
          <div className="md:hidden space-y-3">
            {filtrados.length === 0 ? (
              <div className="bg-white rounded-lg shadow p-8 text-center text-sm text-gray-500">
                No se encontraron clientes con los filtros actuales.
              </div>
            ) : (
              filtrados.map((cliente: RowData) => {
                const id = cliente.id as string;
                const nombre = (cliente.nombre as string) || 'Sin nombre';
                const estadoRaw = (cliente.estado as string) || 'offline';
                const estado = statusMap[estadoRaw] || estadoRaw || 'fuera-de-linea';
                const ultimoContacto = cliente.ultimoContacto as string | undefined;
                const agenteEstado = statusMap[cliente.servicios?.[0]?.estado as string] || 'fuera-de-linea';
                const modulos = cliente.servicios?.[0]?.modulos as string[] | undefined;

                return (
                  <div
                    key={id}
                    className="bg-white rounded-lg shadow p-4 space-y-3 cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => navigate(`/operador/clientes/${id}`)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-900 break-words">{nombre}</div>
                        {modulos && modulos.filter(m => m !== 'core').length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {modulos.filter(m => m !== 'core').slice(0, 3).map(m => (
                              <span key={m} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{m}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
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
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
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
                        className="flex-1 text-red-600 hover:bg-red-50"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEliminar(id, nombre);
                        }}
                      >
                        Eliminar
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
};

/** Small helper component for the page header row */
const HeaderRow = ({ navigate, total }: { navigate: ReturnType<typeof useNavigate>; total: number }) => (
  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
      <p className="mt-1 text-sm text-gray-500">
        {total > 0 ? `${total} cliente${total !== 1 ? 's' : ''} registrado${total !== 1 ? 's' : ''}` : 'Gestiona todos los clientes VCOO registrados.'}
      </p>
    </div>
    <Button onClick={() => navigate('/operador/clientes/nuevo')}>
      + Nuevo Cliente
    </Button>
  </div>
);

export default ClientesPage;
