import { useState } from 'react';
import { useAuthActions } from '../../auth/useAuth';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [recordarme, setRecordarme] = useState(false);
  const { iniciarSesion } = useAuthActions();
  const navigate = useNavigate();

  const manejarEnvio = async (e: React.FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setError(null);

    try {
      await iniciarSesion(email, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError('Correo electrónico o contraseña inválidos');
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-primary-600">
            VERSUS Strategy
          </h2>
          <p className="text-gray-600">
            Acceso al Panel de Control VCOO
          </p>
        </div>

        <form onSubmit={manejarEnvio} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Correo electrónico
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div className="relative">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Contraseña
            </label>
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700 mt-6"
              aria-label="Mostrar contraseña"
            >
              {showPassword ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={recordarme}
                onChange={(e) => setRecordarme(e.target.checked)}
              />
              Recordarme
            </label>
            <a href="#" className="text-sm text-primary-600 hover:underline">
              ¿Olvidó su contraseña?
            </a>
          </div>

          <button
            type="submit"
            disabled={cargando}
            className="w-full flex items-center justify-center px-4 py-2 bg-primary-600 text-white font-medium rounded-md disabled:opacity-50 hover:bg-primary-700 transition-colors"
          >
            {cargando ? 'Iniciando sesión...' : 'Ingresar'}
          </button>

          {error && (
            <p className="text-sm text-red-600 text-center">
              {error}
            </p>
          )}

          <div className="text-center text-sm text-gray-500">
            ¿No tiene cuenta? <a href="#" className="text-primary-600 hover:underline">Solicitar acceso</a>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
