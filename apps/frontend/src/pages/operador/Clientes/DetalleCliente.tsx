import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDetalleVCOO, useTokenDeProvision, useEliminarVCOO } from '@/query/useConsulta';
import apiClient from '@/api/apiClient';
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

const DetalleClientePage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    data: estado,
    isLoading: cargandoEstado,
    isError: errorEstado,
  } = useDetalleVCOO(id || '');

  const {
    data: tokenData,
    isLoading: cargandoToken,
    isError: errorToken,
  } = useTokenDeProvision(id || '');

  const eliminarVCOO = useEliminarVCOO();
  const queryClient = useQueryClient();

  const [copiado, setCopiado] = useState<string | null>(null);

  // Reset copy state after 3 seconds
  useEffect(() => {
    if (copiado) {
      const timer = setTimeout(() => setCopiado(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [copiado]);

  const copiarAlPortapapeles = (texto: string, label: string) => {
    navigator.clipboard.writeText(texto).then(() => {
      setCopiado(label);
    });
  };

  if (!id) {
    return (
      <div className="text-center py-12">
        <h2 className="text-lg font-medium text-gray-900">ID de cliente no válido</h2>
        <Button className="mt-4" onClick={() => navigate('/operador/clientes')}>
          Volver a Clientes
        </Button>
      </div>
    );
  }

  if (cargandoEstado || cargandoToken) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-3">
          <Button variant="ghost" onClick={() => navigate('/operador/clientes')}>
            &larr; Volver
          </Button>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200 rounded w-1/3" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-20 bg-gray-200 rounded" />
            <div className="h-20 bg-gray-200 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (errorEstado) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-3">
          <Button variant="ghost" onClick={() => navigate('/operador/clientes')}>
            &larr; Volver
          </Button>
        </div>
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">Error al cargar detalle del cliente</h3>
          <p className="mt-2 text-sm text-gray-500">
            No se pudo obtener la información del cliente. Intenta de nuevo más tarde.
          </p>
          <Button className="mt-4" onClick={() => navigate('/operador/clientes')}>
            Volver a Clientes
          </Button>
        </div>
      </div>
    );
  }

  const estadoData = estado as Record<string, unknown> | undefined;
  const nombre = (estadoData?.name as string) || (estadoData?.nombre as string) || 'Cliente sin nombre';
  const estadoCliente = statusMap[(estadoData?.status as string) || 'offline'] || 'fuera-de-linea';
  const createdAt = (estadoData?.created_at as string) || (estadoData?.createdAt as string) || '';
  const agentInfo = estadoData?.agent as Record<string, unknown> | undefined;
  const agentStatus = agentInfo?.status as string || 'offline';
  const agentStatusLocal = statusMap[agentStatus] || agentStatus || 'fuera-de-linea';
  const lastSeen = agentInfo?.last_seen as string | undefined;
  const capabilities = agentInfo?.capabilities as Record<string, unknown> | undefined;
  const providers = capabilities?.providers as Array<Record<string, unknown>> | undefined;
  const completedSteps = (estadoData?.completed_steps as string[]) || [];
  const onboardingStatus = (estadoData?.onboarding_status as string) || 'in_progress';
  const modulos = (estadoData?.modules as string[]) || [];
  const totalPasos = 5; // Assuming 5 onboarding steps

  const provisionToken = tokenData?.token as string | undefined;
  const installCommand = tokenData?.install_command as string | undefined;
  const onboardingUrl = tokenData?.onboarding_url as string | undefined;

  // ── Provider configuration state ──
  const [provider, setProvider] = useState('openrouter');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [configuring, setConfiguring] = useState(false);
  const [configResult, setConfigResult] = useState<string | null>(null);

  const handleSetProvider = async () => {
    if (!provider || !apiKey) return;
    setConfiguring(true);
    setConfigResult(null);
    try {
      const { data } = await apiClient.post(`/vcoo/${id}/set-provider`, {
        provider,
        model,
        api_key: apiKey,
      });
      setConfigResult(`✅ Comando enviado: ${data.provider}${data.model ? ` (${data.model})` : ''}`);
      setApiKey('');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || (err as Error).message || 'Error desconocido';
      setConfigResult(`❌ Error: ${msg}`);
    } finally {
      setConfiguring(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div className="flex items-center space-x-3">
        <Button variant="ghost" onClick={() => navigate('/operador/clientes')}>
          &larr; Volver
        </Button>
      </div>

      {/* Header card */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{nombre}</h1>
            <p className="mt-1 text-sm text-gray-500">
              ID: <code className="font-mono text-gray-700">{id}</code>
            </p>
          </div>
          <StatusBadge estado={estadoCliente} />
        </div>
        {createdAt && (
          <p className="mt-2 text-sm text-gray-500">
            Creado el{' '}
            {new Date(createdAt).toLocaleDateString('es-ES', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        )}
      </div>

      {/* Agent status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Estado del Agente</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <span className="text-sm text-gray-500">Estado</span>
            <div className="mt-1">
              <StatusBadge estado={agentStatusLocal} />
            </div>
          </div>
          <div>
            <span className="text-sm text-gray-500">Última conexión</span>
            <p className="mt-1 text-sm text-gray-900">
              {lastSeen
                ? new Date(lastSeen).toLocaleString('es-ES', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                : '—'}
            </p>
          </div>
        </div>
      </div>

      {/* Provision Token & Install Command */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Provisionamiento</h2>

        {cargandoToken && (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-gray-200 rounded w-1/4" />
            <div className="h-10 bg-gray-200 rounded" />
            <div className="h-4 bg-gray-200 rounded w-1/4 mt-4" />
            <div className="h-10 bg-gray-200 rounded" />
          </div>
        )}

        {errorToken && !cargandoToken && (
          <p className="text-sm text-red-600">
            No se pudo obtener el token de provisionamiento. Es posible que el cliente no tenga un
            token activo.
          </p>
        )}

        {provisionToken && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Token de Provisionamiento
            </label>
            <div className="flex items-center space-x-2">
              <code className="flex-1 block rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm font-mono text-gray-700 break-all">
                {provisionToken}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => copiarAlPortapapeles(provisionToken, 'token')}
              >
                {copiado === 'token' ? '¡Copiado!' : 'Copiar'}
              </Button>
            </div>
          </div>
        )}

        {installCommand && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Comando de Instalación
            </label>
            <div className="flex items-center space-x-2">
              <code className="flex-1 block rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm font-mono text-gray-700 break-all">
                {installCommand}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => copiarAlPortapapeles(installCommand, 'comando')}
              >
                {copiado === 'comando' ? '¡Copiado!' : 'Copiar'}
              </Button>
            </div>
          </div>
        )}

        {onboardingUrl && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              🌐 Enlace de incorporación para el cliente
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Comparte este enlace con tu cliente para que complete la configuración inicial.
            </p>
            <div className="flex items-center space-x-2">
              <code className="flex-1 block rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm font-mono text-gray-700 break-all">
                {onboardingUrl}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => copiarAlPortapapeles(onboardingUrl, 'enlace')}
              >
                {copiado === 'enlace' ? '¡Copiado!' : 'Copiar'}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Provider configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">🤖 Proveedor de IA</h2>
        <p className="text-sm text-gray-500 mb-4">
          Configura el proveedor de inteligencia artificial del agente. La API key se envía cifrada y el agente la aplica automáticamente.
        </p>

        {!providers ? (
          <div className="bg-gray-50 rounded-lg p-6 text-center">
            <p className="text-sm text-gray-500">
              ⏳ Esperando a que el agente reporte sus capacidades...
            </p>
            <p className="text-xs text-gray-400 mt-2">
              El agente debe estar en línea para poder configurar el proveedor de IA.
              Una vez que el agente se conecte, los proveedores disponibles aparecerán aquí.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Proveedor</label>
              <select
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setModel('');
                }}
              >
                {providers.length === 0 ? (
                  <option value="">No hay proveedores disponibles</option>
                ) : (
                  providers.map((p) => (
                    <option key={p.id as string} value={p.id as string}>
                      {p.name as string}
                    </option>
                  ))
                )}
              </select>
            </div>

            {(() => {
              const currentProvider = providers.find((p) => p.id === provider) as Record<string, unknown> | undefined;
              const models = (currentProvider?.models as string[]) || [];

              if (models.length > 0) {
                return (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Modelo <span className="text-gray-400">(opcional)</span>
                    </label>
                    <select
                      className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                    >
                      <option value="">Seleccionar modelo...</option>
                      {models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              }

              return (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Modelo <span className="text-gray-400">(opcional)</span>
                  </label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
                    placeholder="p.ej. openrouter/deepseek-v4, claude-sonnet-4, gpt-4o"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  />
                </div>
              );
            })()}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input
                type="password"
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>

            <Button
              onClick={handleSetProvider}
              disabled={configuring || !provider || !apiKey}
            >
              {configuring ? 'Enviando...' : 'Configurar proveedor'}
            </Button>

            {configResult && (
              <p className={`text-sm ${configResult.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>
                {configResult}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Onboarding progress */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Progreso de Incorporación</h2>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Estado</span>
            <StatusBadge estado={statusMap[onboardingStatus] || onboardingStatus} />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Pasos completados</span>
            <span className="font-medium text-gray-900">
              {completedSteps.length} / {totalPasos}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
            <div
              className="bg-primary-600 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.round((completedSteps.length / totalPasos) * 100)}%` }}
            />
          </div>
          {completedSteps.length > 0 && (
            <div className="mt-3">
              <span className="text-sm text-gray-500">Pasos completados:</span>
              <ul className="mt-1 space-y-1">
                {completedSteps.map((paso, idx) => (
                  <li key={idx} className="text-sm text-gray-700 flex items-center">
                    <svg
                      className="h-4 w-4 text-green-500 mr-2 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth="2"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                    {paso}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Modules / Services detail */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Módulos</h2>
        {modulos.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {modulos.map((mod) => (
              <span
                key={mod}
                className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
              >
                {mod}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No hay módulos configurados.</p>
        )}
      </div>

      {/* Delete client */}
      <div className="bg-white rounded-lg shadow p-6 border border-red-200">
        <h2 className="text-lg font-semibold text-red-700 mb-2">Zona de peligro</h2>
        <p className="text-sm text-gray-600 mb-4">
          Eliminar este cliente borrará todos los datos asociados de forma permanente. Esta acción no se puede deshacer.
        </p>
        <Button
          variant="secondary"
          className="text-red-600 hover:bg-red-50 border-red-200"
          onClick={() => {
            if (window.confirm(`¿Estás seguro de eliminar el cliente "${nombre}"? Esta acción eliminará todos los datos asociados de forma permanente.`)) {
              eliminarVCOO.mutate(id, {
                onSuccess: () => {
                  queryClient.invalidateQueries({ queryKey: ['operador', 'clientes'] });
                  navigate('/operador/clientes');
                },
              });
            }
          }}
        >
          Eliminar Cliente
        </Button>
      </div>

      {/* Raw state data (expandable for debugging) */}
      {estadoData && Object.keys(estadoData).length > 0 && (
        <details className="bg-white rounded-lg shadow p-6">
          <summary className="text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900">
            Datos técnicos (JSON)
          </summary>
          <pre className="mt-3 text-xs text-gray-600 bg-gray-50 rounded-lg p-3 overflow-x-auto max-h-96">
            {JSON.stringify(estadoData, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
};

export default DetalleClientePage;
