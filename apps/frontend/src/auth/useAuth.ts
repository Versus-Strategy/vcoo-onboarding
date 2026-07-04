import { useAuth } from './authContext';

export const useAuthState = () => {
  const { auth } = useAuth();
  return auth;
};

export const useAuthActions = () => {
  const { iniciarSesion, cerrarSesion, actualizarToken } = useAuth();
  return { iniciarSesion, cerrarSesion, actualizarToken };
};
