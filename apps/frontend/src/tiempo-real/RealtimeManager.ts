import { usarAlmacen } from '../store/almacen';
import apiClient from '../api/apiClient';

interface UpdateData {
  agenteInstalado?: boolean;
  proveedorConectado?: boolean;
  modulosConfigurados?: string[];
}

class RealtimeManager {
  private ws: WebSocket | null = null;
  private pollingInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private baseReconnectDelay: number = 1000; // 1s
  private isPollingFallback: boolean = false;
  private readonly heartbeatInterval: number = 30000; // 30s
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  connect() {
    if (this.canUseWebSocket()) {
      this.initWebSocket();
    } else {
      this.initPollingFallback();
    }
  }

  disconnect() {
    this.stopHeartbeat();

    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.reconnectAttempts = 0;
    this.isPollingFallback = false;
  }

  private canUseWebSocket(): boolean {
    // In production, check feature flag from backend
    // Currently return false to use polling due to Vercel limitations
    return false;
  }

  private initWebSocket() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'wss://api.vcoo.example.com/ws';
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = this.handleWsOpen;
    this.ws.onmessage = this.handleWsMessage;
    this.ws.onerror = this.handleWsError;
    this.ws.onclose = this.handleWsClose;

    this.startHeartbeat();
  }

  private initPollingFallback() {
    this.isPollingFallback = true;
    this.fetchUpdates(); // Immediate initial call

    // Poll with jitter (15s ± 5s)
    this.pollingInterval = setInterval(() => {
      this.fetchUpdates();
    }, 15000 + Math.random() * 10000);
  }

  private handleWsOpen = () => {
    console.log('WebSocket connected');
    this.reconnectAttempts = 0;

    usarAlmacen.setState((state) => ({
      api: {
        ...state.api,
        websocket: {
          ...state.api.websocket,
          conectado: true,
          intentosDeReconexion: 0,
        },
      },
    }));
  };

  private handleWsMessage = (event: MessageEvent) => {
    try {
      const data: UpdateData = JSON.parse(event.data);
      this.processUpdates(data);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  private handleWsError = (_error: Event) => {
    console.error('WebSocket error');
    this.handleWsClose();
  };

  private handleWsClose = () => {
    console.log('WebSocket disconnected');

    usarAlmacen.setState((state) => ({
      api: {
        ...state.api,
        websocket: {
          ...state.api.websocket,
          conectado: false,
        },
      },
    }));

    // Attempt reconnection if not maxed out and not already polling
    if (this.reconnectAttempts < this.maxReconnectAttempts && !this.isPollingFallback) {
      this.reconnectAttempts++;
      const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts); // exponential backoff

      setTimeout(() => {
        this.initWebSocket();
      }, delay);
    } else if (!this.isPollingFallback) {
      // Fallback to polling
      this.initPollingFallback();
    }
  };

  private startHeartbeat() {
    if (this.heartbeatTimer) return;

    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private sendHeartbeat() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'heartbeat' }));
    }
  }

  private async fetchUpdates() {
    // Avoid concurrent polls
    const currentState = usarAlmacen.getState();
    if (currentState.api.estaRealizandoEncuesta) return;

    usarAlmacen.setState((state) => ({
      api: { ...state.api, estaRealizandoEncuesta: true },
    }));

    try {
      const rol = currentState.app.rol;
      let endpoint = '';

      if (rol === 'cliente') {
        const userId = currentState.auth.usuario?.id;
        if (userId) {
          endpoint = `/estado-agente/${userId}`;
        }
      } else if (rol === 'operador') {
        endpoint = '/operador/clientes/actualizaciones';
      }

      if (endpoint) {
        const { data } = await apiClient.get<UpdateData>(endpoint);
        this.processUpdates(data);
      }
    } catch (error) {
      console.error('Error fetching updates:', error);
    } finally {
      usarAlmacen.setState((state) => ({
        api: { ...state.api, estaRealizandoEncuesta: false },
      }));
    }
  }

  private processUpdates(data: UpdateData) {
    const state = usarAlmacen.getState();

    // Client-specific updates
    if (state.app.rol === 'cliente') {
      if (data.agenteInstalado !== undefined && state.cliente) {
        usarAlmacen.setState({
          cliente: {
            ...state.cliente,
            estadoDeInstalacion: {
              ...state.cliente.estadoDeInstalacion,
              agenteInstalado: data.agenteInstalado,
            },
          },
        });

        // If agent just installed, advance onboarding
        if (data.agenteInstalado && state.cliente.pasoDeIncorporacion === 0) {
          usarAlmacen.setState({
            cliente: {
              ...usarAlmacen.getState().cliente!,
              pasoDeIncorporacion: 1,
            },
          });
        }
      }
    }
  }
}

export default RealtimeManager;
