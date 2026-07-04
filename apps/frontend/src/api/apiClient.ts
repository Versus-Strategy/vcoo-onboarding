import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'https://vcoo-onboarding.vercel.app';

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

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

    // If 401 and haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const stored = localStorage.getItem('vcoo-auth');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed.refreshToken) {
            const { data } = await apiClient.post('/auth/refresh', {
              refreshToken: parsed.refreshToken,
            });

            // Update token in localStorage
            const newToken = data.accessToken || data.token || parsed.token;
            parsed.token = newToken;
            parsed.refreshToken = newToken;
            parsed.marcaDeTiempo = Date.now();
            localStorage.setItem('vcoo-auth', JSON.stringify(parsed));

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return apiClient(originalRequest);
          }
        }
      } catch {
        // If refresh fails, redirect to login
        localStorage.removeItem('vcoo-auth');
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
