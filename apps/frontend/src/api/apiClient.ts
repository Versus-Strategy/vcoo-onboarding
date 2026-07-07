import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export { API_URL };

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

let refrescando = false;
let colaRefresh: Array<(token: string) => void> = [];

// Request interceptor to add auth token
apiClient.interceptors.request.use((config) => {
  try {
    const stored = localStorage.getItem('vcoo-auth');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.token) {
        config.headers.Authorization = `Bearer ${parsed.token}`;
      }
    }
  } catch {
    // Ignore parse errors
  }
  return config;
});

// Response interceptor for token refresh and error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Rate limiting — no reintentar
    if (error.response?.status === 429) {
      return Promise.reject(error);
    }

    // If 401 and haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      if (refrescando) {
        // Si ya hay un refresh en curso, encolar esta petición
        return new Promise((resolve) => {
          colaRefresh.push((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            resolve(apiClient(originalRequest));
          });
        });
      }

      refrescando = true;
      try {
        const stored = localStorage.getItem('vcoo-auth');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed.refreshToken) {
            const { data } = await apiClient.post('/auth/refresh', {
              refreshToken: parsed.refreshToken,
            });

            const newToken = data.accessToken || data.token || parsed.token;
            parsed.token = newToken;
            parsed.refreshToken = newToken;
            parsed.marcaDeTiempo = Date.now();
            localStorage.setItem('vcoo-auth', JSON.stringify(parsed));

            // Notificar a peticiones en cola
            colaRefresh.forEach(cb => cb(newToken));
            colaRefresh = [];

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            refrescando = false;
            return apiClient(originalRequest);
          }
        }
      } catch {
        // If refresh fails, redirect to login
        localStorage.removeItem('vcoo-auth');
        window.location.href = '/login';
        return Promise.reject(error);
      } finally {
        refrescando = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
