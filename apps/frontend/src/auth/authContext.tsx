import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'https://vcoo-onboarding.vercel.app';

export interface Usuario {
  id: string;
  email: string;
  nombre: string;
  rol: 'cliente' | 'operador';
  avatar?: string;
  vcoo_id?: string;
}

export interface AuthState {
  usuario: Usuario | null;
  token: string | null;
  refreshToken: string | null;
  estaAutenticado: boolean;
  cargando: boolean;
  error: string | null;
}

export interface AuthContextType {
  auth: AuthState;
  iniciarSesion: (email: string, password: string) => Promise<void>;
  iniciarSesionCliente: (email: string, password: string) => Promise<void>;
  registrarCliente: (name: string, email: string, password: string, setupToken: string) => Promise<void>;
  cerrarSesion: () => void;
  actualizarToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthData {
  usuario: Usuario;
  token: string;
  refreshToken: string;
  marcaDeTiempo: number;
}

export const ProveedorDeAuth = ({ children }: { children: ReactNode }) => {
  // Estado inicial: cargando=true para evitar flash de Login mientras se restaura sesión
  const [auth, setAuth] = useState<AuthState>({
    usuario: null,
    token: null,
    refreshToken: null,
    estaAutenticado: false,
    cargando: true,
    error: null,
  });

  // Load auth from localStorage on init
  useEffect(() => {
    try {
      const datosDeAuth = localStorage.getItem('vcoo-auth');
      if (datosDeAuth) {
        const analizado: AuthData = JSON.parse(datosDeAuth);
        // Simple validation - check expiry (24h)
        if (Date.now() - analizado.marcaDeTiempo < 24 * 60 * 60 * 1000) {
          setAuth({
            usuario: analizado.usuario,
            token: analizado.token,
            refreshToken: analizado.refreshToken,
            estaAutenticado: !!analizado.token,
            cargando: false,
            error: null,
          });
        } else {
          localStorage.removeItem('vcoo-auth');
        }
      }
    } catch {
      localStorage.removeItem('vcoo-auth');
    }
  }, []);

  const guardarAuth = (token: string, usuario: Usuario) => {
    const marcaDeTiempo = Date.now();
    setAuth({
      usuario,
      token,
      refreshToken: token,
      estaAutenticado: true,
      cargando: false,
      error: null,
    });
    localStorage.setItem('vcoo-auth', JSON.stringify({
      usuario,
      token,
      refreshToken: token,
      marcaDeTiempo,
    }));
  };

  const iniciarSesion = async (email: string, password: string) => {
    setAuth(prev => ({ ...prev, cargando: true, error: null }));
    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        email,
        password,
      });

      const { token, user } = response.data;

      const usuario: Usuario = {
        id: user.email || email,
        email: user.email || email,
        nombre: user.name || email.split('@')[0],
        rol: user.role === 'operador' ? 'operador' : 'cliente',
        avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name || email.split('@')[0])}&background=533afd&color=fff`,
      };

      guardarAuth(token, usuario);
    } catch (error: unknown) {
      let mensaje = 'Credenciales inválidas';
      if (axios.isAxiosError(error) && error.response?.data?.detail) {
        mensaje = error.response.data.detail;
      }
      setAuth(prev => ({
        ...prev,
        cargando: false,
        error: mensaje,
      }));
      throw new Error(mensaje);
    }
  };

  const iniciarSesionCliente = async (email: string, password: string) => {
    setAuth(prev => ({ ...prev, cargando: true, error: null }));
    try {
      const response = await axios.post(`${API_URL}/auth/client/login`, {
        email,
        password,
      });

      const { token, client } = response.data;

      const usuario: Usuario = {
        id: client.id || client.email || email,
        email: client.email || email,
        nombre: client.name || email.split('@')[0],
        rol: 'cliente',
        vcoo_id: client.vcoo_id,
        avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(client.name || email.split('@')[0])}&background=533afd&color=fff`,
      };

      guardarAuth(token, usuario);
    } catch (error: unknown) {
      let mensaje = 'Credenciales inválidas';
      if (axios.isAxiosError(error) && error.response?.data?.detail) {
        mensaje = error.response.data.detail;
      }
      setAuth(prev => ({
        ...prev,
        cargando: false,
        error: mensaje,
      }));
      throw new Error(mensaje);
    }
  };

  const registrarCliente = async (name: string, email: string, password: string, setupToken: string) => {
    setAuth(prev => ({ ...prev, cargando: true, error: null }));
    try {
      const response = await axios.post(`${API_URL}/auth/client/register`, {
        name,
        email,
        password,
        token: setupToken,
      });

      const { token, client } = response.data;

      const usuario: Usuario = {
        id: client.id || client.email || email,
        email: client.email || email,
        nombre: client.name || name,
        rol: 'cliente',
        vcoo_id: client.vcoo_id,
        avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(client.name || name)}&background=533afd&color=fff`,
      };

      guardarAuth(token, usuario);
    } catch (error: unknown) {
      let mensaje = 'Error al registrar';
      if (axios.isAxiosError(error) && error.response?.data?.detail) {
        mensaje = error.response.data.detail;
      }
      setAuth(prev => ({
        ...prev,
        cargando: false,
        error: mensaje,
      }));
      throw new Error(mensaje);
    }
  };

  const cerrarSesion = () => {
    setAuth({
      usuario: null,
      token: null,
      refreshToken: null,
      estaAutenticado: false,
      cargando: false,
      error: null,
    });
    localStorage.removeItem('vcoo-auth');
  };

  const actualizarToken = async () => {
    if (auth.token) {
      try {
        const response = await axios.post(`${API_URL}/auth/refresh`, {
          refreshToken: auth.token,
        });
        const { token } = response.data;

        setAuth(prev => ({
          ...prev,
          token,
          refreshToken: token,
        }));

        const stored = JSON.parse(localStorage.getItem('vcoo-auth') || '{}');
        stored.token = token;
        stored.refreshToken = token;
        stored.marcaDeTiempo = Date.now();
        localStorage.setItem('vcoo-auth', JSON.stringify(stored));
      } catch {
        cerrarSesion();
      }
    }
  };

  return (
    <AuthContext.Provider value={{ auth, iniciarSesion, iniciarSesionCliente, registrarCliente, cerrarSesion, actualizarToken }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth debe usarse dentro de un ProveedorDeAuth');
  }
  return context;
};
