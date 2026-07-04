import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCrearVCOO } from '@/query/useConsulta';
import Button from '@/components/Button';

const MODULOS_DISPONIBLES = [
  { id: 'core', label: 'Core', descripcion: 'Funcionalidad base del agente VCOO' },
  { id: 'office', label: 'Office', descripcion: 'Integración con herramientas ofimáticas' },
  { id: 'mail', label: 'Mail', descripcion: 'Gestión de correo electrónico' },
  { id: 'planner', label: 'Planner', descripcion: 'Planificación y calendario' },
  { id: 'developer', label: 'Developer', descripcion: 'Herramientas para desarrolladores' },
];

const NuevoClientePage = () => {
  const navigate = useNavigate();
  const { mutateAsync: crearVCOO, isPending } = useCrearVCOO();
  const [nombre, setNombre] = useState('');
  const [modulos, setModulos] = useState<string[]>(['core']);
  const [resultado, setResultado] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);

  const toggleModulo = (modId: string) => {
    setModulos((prev) =>
      prev.includes(modId) ? prev.filter((m) => m !== modId) : [...prev, modId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResultado(null);

    if (!nombre.trim()) {
      setError('El nombre del cliente es obligatorio.');
      return;
    }

    if (modulos.length === 0) {
      setError('Selecciona al menos un módulo.');
      return;
    }

    try {
      const data = await crearVCOO({ name: nombre.trim(), modules: modulos });
      setResultado(data as Record<string, unknown>);
    } catch (err: unknown) {
      const mensaje =
        err instanceof Error ? err.message : 'Error al crear el cliente. Intenta de nuevo.';
      setError(mensaje);
    }
  };

  const copiarAlPortapapeles = (texto: string) => {
    navigator.clipboard.writeText(texto).then(() => {
      setCopiado(true);
      setTimeout(() => setCopiado(false), 3000);
    });
  };

  const installCommand = resultado?.install_command as string | undefined;
  const provisionToken = resultado?.token as string | undefined;
  const vcooId = resultado?.id as string | undefined;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Nuevo Cliente</h1>
        <p className="mt-1 text-sm text-gray-500">
          Registra un nuevo cliente VCOO en la plataforma.
        </p>
      </div>

      {!resultado ? (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
          {/* Client name */}
          <div>
            <label htmlFor="nombre-cliente" className="block text-sm font-medium text-gray-700 mb-1">
              Nombre del Cliente
            </label>
            <input
              id="nombre-cliente"
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej: Empresa XYZ"
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder-gray-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              disabled={isPending}
            />
          </div>

          {/* Module selection */}
          <div>
            <span className="block text-sm font-medium text-gray-700 mb-2">Módulos</span>
            <div className="space-y-3">
              {MODULOS_DISPONIBLES.map((mod) => (
                <label
                  key={mod.id}
                  className={`flex items-start p-3 rounded-lg border cursor-pointer transition-colors ${
                    modulos.includes(mod.id)
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={modulos.includes(mod.id)}
                    onChange={() => toggleModulo(mod.id)}
                    disabled={mod.id === 'core'} // core is always required
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">{mod.label}</span>
                    <p className="text-xs text-gray-500">{mod.descripcion}</p>
                  </div>
                </label>
              ))}
            </div>
            <p className="mt-1 text-xs text-gray-400">El módulo Core es obligatorio y siempre está incluido.</p>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end space-x-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate('/operador/clientes')}
              disabled={isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" loading={isPending}>
              Crear Cliente
            </Button>
          </div>
        </form>
      ) : (
        /* Success result */
        <div className="bg-white rounded-lg shadow p-6 space-y-6">
          <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg p-4">
            <p className="font-medium">¡Cliente creado exitosamente!</p>
            <p className="mt-1">
              El cliente <strong>{nombre}</strong> ha sido registrado. A continuación se muestran los
              datos de provisionamiento.
            </p>
          </div>

          {/* VCOO ID */}
          {vcooId && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ID del VCOO</label>
              <div className="flex items-center space-x-2">
                <code className="flex-1 block rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm font-mono text-gray-700">
                  {vcooId}
                </code>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => copiarAlPortapapeles(vcooId)}
                >
                  {copiado ? '¡Copiado!' : 'Copiar'}
                </Button>
              </div>
            </div>
          )}

          {/* Provision token */}
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
                  onClick={() => copiarAlPortapapeles(provisionToken)}
                >
                  {copiado ? '¡Copiado!' : 'Copiar'}
                </Button>
              </div>
            </div>
          )}

          {/* Install command */}
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
                  onClick={() => copiarAlPortapapeles(installCommand)}
                >
                  {copiado ? '¡Copiado!' : 'Copiar'}
                </Button>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => {
                setNombre('');
                setModulos(['core']);
                setResultado(null);
                setCopiado(false);
              }}
            >
              Crear Otro Cliente
            </Button>
            <Button onClick={() => navigate('/operador/clientes')}>
              Volver a Clientes
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NuevoClientePage;
