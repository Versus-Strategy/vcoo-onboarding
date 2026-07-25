import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SetupWizard from './SetupWizard';

// ── Hoisted mock variables ──

const { mockApiClient, mockUseAuth, mockUseParams } = vi.hoisted(() => ({
  mockApiClient: { get: vi.fn(), post: vi.fn() },
  mockUseAuth: vi.fn(),
  mockUseParams: vi.fn(),
}));

vi.mock('@/api/apiClient', () => ({
  default: mockApiClient,
}));

vi.mock('@/auth/authContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => mockUseParams(),
  };
});

// ── Factory helpers ──

const defaultAuth = {
  estaAutenticado: false,
  cargando: false,
  token: null,
  usuario: null,
  refreshToken: null,
  error: null,
};
const authedAuth = { ...defaultAuth, estaAutenticado: true, token: 'test-token' };
const loadingAuth = { ...defaultAuth, cargando: true };

const defaultOnboarding = {
  vcoo_id: 'vcoo-1',
  name: 'Test VCOO',
  modules: ['core', 'office'],
  module_labels: {},
  providers: [],
  step: 'bootstrap',
  wizard_step: 0,
  status: 'active',
  completed: [],
  all_done: false,
  install_command: 'curl -sSL https://vcoo.ai/install.sh | bash',
  agent_online: false,
  progress: { total: 4, done: 0 },
  checks: {},
  models: {},
  errors: [],
  retry_count: {},
};

// ── Wrapper ──

function renderSetupWizard(options?: {
  params?: Record<string, string>;
  auth?: typeof defaultAuth;
}) {
  const params = { token: 'test-token', ...options?.params };
  mockUseParams.mockReturnValue(params);
  mockUseAuth.mockReturnValue({ auth: options?.auth ?? defaultAuth });
  return render(
    <MemoryRouter>
      <SetupWizard />
    </MemoryRouter>
  );
}

// ── Tests ──

describe('SetupWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('muestra spinner de verificacion en carga inicial', () => {
    mockUseAuth.mockReturnValue({ auth: { ...defaultAuth, cargando: true } });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('muestra AuthForm cuando no esta autenticado', async () => {
    renderSetupWizard();
    await waitFor(() => {
      expect(screen.getByText('Crear tu cuenta')).toBeInTheDocument();
    });
  });

  it('permite cambiar a iniciar sesion en AuthForm', async () => {
    renderSetupWizard();
    const { userEvent } = await import('@testing-library/user-event');
    const link = await screen.findByText('¿Ya tienes cuenta? Inicia sesión');
    await userEvent.click(link);
    expect(screen.getByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument();
  });

  it('inicia wizard cuando hay sesion guardada en localStorage', async () => {
    localStorage.setItem('vcoo-auth', JSON.stringify({
      token: 'stored-token',
      usuario: { id: '1', email: 'a@b.com', nombre: 'Test', rol: 'cliente' },
      marcaDeTiempo: Date.now(),
    }));
    mockApiClient.get.mockResolvedValue({ data: defaultOnboarding });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Instalar el Agente VCOO')).toBeInTheDocument();
    });
    expect(mockApiClient.get).toHaveBeenCalledWith('/setup/test-token');
  });

  it('llama a la API al montar el wizard', async () => {
    localStorage.setItem('vcoo-auth', JSON.stringify({
      token: 'stored-token',
      usuario: { id: '1', email: 'a@b.com', nombre: 'Test', rol: 'cliente' },
      marcaDeTiempo: Date.now(),
    }));
    mockApiClient.get.mockResolvedValue({ data: defaultOnboarding });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith('/setup/test-token');
    });
  });

  it('maneja requires_registration retornando null', async () => {
    mockApiClient.get.mockResolvedValue({ data: { requires_registration: true } });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    const { container } = render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(container.innerHTML).toBe('');
    });
  });

  it('muestra loading mientras carga onboarding', async () => {
    mockApiClient.get.mockImplementation(() => new Promise(() => {}));
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    expect(await screen.findByText('Cargando configuración...')).toBeInTheDocument();
  });

  it('muestra error cuando falla la carga del onboarding', async () => {
    mockApiClient.get.mockRejectedValue(new Error('Network Error'));
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getAllByText('Error de conexión').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('Reintentar')).toBeInTheDocument();
  });

  it('muestra error de conexion', async () => {
    mockApiClient.get.mockRejectedValue({
      response: { status: 403, data: { detail: 'Acceso denegado' } },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getAllByText('Error de conexión').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('Reintentar')).toBeInTheDocument();
  });

  it('renderiza paso de instalacion como paso actual 0', async () => {
    mockApiClient.get.mockResolvedValue({ data: defaultOnboarding });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Instalar el Agente VCOO')).toBeInTheDocument();
    });
  });

  it('muestra el comando de instalacion', async () => {
    const cmd = 'curl -sSL https://vcoo.ai/install.sh | bash';
    mockApiClient.get.mockResolvedValue({
      data: { ...defaultOnboarding, install_command: cmd },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(cmd)).toBeInTheDocument();
    });
  });

  it('muestra el progreso en el StepIndicator', async () => {
    const progress = { total: 4, done: 2 };
    mockApiClient.get.mockResolvedValue({
      data: { ...defaultOnboarding, progress, wizard_step: 1 },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Progreso de Configuración')).toBeInTheDocument();
      expect(screen.getByText('50% completo')).toBeInTheDocument();
    });
  });

  it('renderiza tarjeta de bienvenida con el nombre del VCOO', async () => {
    mockApiClient.get.mockResolvedValue({ data: defaultOnboarding });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Configuración de Test VCOO/)).toBeInTheDocument();
    });
  });

  it('renderiza paso de proveedor cuando wizard_step=1', async () => {
    mockApiClient.get.mockResolvedValue({
      data: {
        ...defaultOnboarding,
        wizard_step: 1,
        providers: [{ id: 'openai', nombre: 'OpenAI', descripcion: 'Desc' }],
      },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Selecciona tu proveedor de IA')).toBeInTheDocument();
    });
  });

  it('renderiza paso de modulos cuando wizard_step=2', async () => {
    mockApiClient.get.mockResolvedValue({
      data: { ...defaultOnboarding, wizard_step: 2 },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Configurar módulos')).toBeInTheDocument();
    });
  });

  it('renderiza paso de finalizacion cuando wizard_step=3', async () => {
    mockApiClient.get.mockResolvedValue({
      data: {
        ...defaultOnboarding,
        wizard_step: 3,
        agent_online: true,
        checks: {
          provider: 'ok',
          google: 'ok',
          github: 'ok',
          vercel: 'ok',
          supabase: 'ok',
          whatsapp: 'ok',
        },
        modules: ['core', 'office', 'developer'],
        completed: ['bootstrap', 'google-oauth', 'gmail-setup', 'github-setup', 'vercel-setup', 'supabase-setup'],
      },
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Todo listo')).toBeInTheDocument();
    });
  });

  it('maneja error 401 mostrando error de conexion', async () => {
    mockApiClient.get.mockRejectedValue({
      response: { status: 401 },
      isAxiosError: true,
    });
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    mockUseParams.mockReturnValue({ token: 'test-token' });
    render(
      <MemoryRouter>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getAllByText('Error de conexión').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('Reintentar')).toBeInTheDocument();
  });

  it('extrae token de pathname cuando no hay params', async () => {
    mockUseParams.mockReturnValue({});
    mockUseAuth.mockReturnValue({ auth: authedAuth });
    const { unmount } = render(
      <MemoryRouter initialEntries={['/setup/path-token-123']}>
        <SetupWizard />
      </MemoryRouter>
    );
    unmount();
    mockApiClient.get.mockResolvedValue({ data: defaultOnboarding });
    mockUseParams.mockReturnValue({ token: 'path-token-123' });
    render(
      <MemoryRouter initialEntries={['/setup/path-token-123']}>
        <SetupWizard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith('/setup/path-token-123');
    });
  });
});
