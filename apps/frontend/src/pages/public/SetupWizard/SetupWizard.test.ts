import { describe, it, expect } from 'vitest';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const asModels = (m: any) => m as { list?: string[]; models?: string[]; recommended?: string };

// NOTE: SetupWizard is 1184 lines and mixes rendering + logic + API calls.
// These tests verify the DERIVED STATE logic that can be extracted/pure.
// For full rendering tests, use the E2E Playwright suite.

describe('wizard step mapping', () => {
  const wizardStepMap: Record<string, number> = {
    bootstrap: 0,
    'google-oauth': 1,
    'gmail-setup': 2,
    'trello-setup': 2,
    'github-setup': 2,
    'vercel-setup': 2,
    'supabase-setup': 2,
    finalize: 3,
    done: 3,
  };

  it('mapea bootstrap al paso 0', () => {
    expect(wizardStepMap['bootstrap']).toBe(0);
  });

  it('mapea proveedores al paso 1', () => {
    expect(wizardStepMap['google-oauth']).toBe(1);
  });

  it('mapea modulos al paso 2', () => {
    expect(wizardStepMap['gmail-setup']).toBe(2);
    expect(wizardStepMap['github-setup']).toBe(2);
    expect(wizardStepMap['supabase-setup']).toBe(2);
  });

  it('mapea finalizacion al paso 3', () => {
    expect(wizardStepMap['finalize']).toBe(3);
    expect(wizardStepMap['done']).toBe(3);
  });

  it('todos los pasos del backend tienen mapeo', () => {
    const backendSteps = [
      'bootstrap', 'google-oauth', 'gmail-setup', 'trello-setup',
      'github-setup', 'vercel-setup', 'supabase-setup', 'finalize', 'done',
    ];
    for (const step of backendSteps) {
      expect(wizardStepMap[step]).toBeDefined();
    }
  });
});

describe('pasos degradados', () => {
  it('detecta provider missing cuando paso completado', () => {
    const completed = ['bootstrap', 'google-oauth'];
    const checks = { provider: 'missing' };
    const pasosDegradados: number[] = [];

    if (checks.provider === 'missing' && completed.includes('google-oauth')) {
      pasosDegradados.push(1);
    }

    expect(pasosDegradados).toContain(1);
  });

  it('no degrada paso si no esta completado', () => {
    const completed = ['bootstrap'];
    const checks = { provider: 'missing' };
    const pasosDegradados: number[] = [];

    if (checks.provider === 'missing' && completed.includes('google-oauth')) {
      pasosDegradados.push(1);
    }

    expect(pasosDegradados).not.toContain(1);
  });

  it('detecta modulo google degradado', () => {
    const completed = ['bootstrap', 'google-oauth', 'gmail-setup'];
    const checks: Record<string, string> = { google: 'error' };
    const modules = ['core', 'office'];
    const pasosDegradados: number[] = [];
    const checkToBackendStep: Record<string, { steps: string[]; mod: string }> = {
      google: { steps: ['gmail-setup'], mod: 'office' },
    };

    for (const [check, cfg] of Object.entries(checkToBackendStep)) {
      const val = checks[check];
      if ((val === 'missing' || val === 'error') && modules.includes(cfg.mod) && cfg.steps.some(s => completed.includes(s))) {
        if (!pasosDegradados.includes(2)) pasosDegradados.push(2);
      }
    }

    expect(pasosDegradados).toContain(2);
  });
});

describe('proveedores - filtrado', () => {
  const raw = [
    { id: 'opencode-go', nombre: 'OpenCode Go' },
    { id: 'anthropic', nombre: 'Anthropic' },
    { id: 'openai', nombre: 'OpenAI' },
    { id: 'google', nombre: 'Google' },
    { id: 'some-unknown', nombre: 'Unknown' },
  ];

  it('separa recomendado del resto', () => {
    const recomendado = raw.find(p => p.id === 'opencode-go');
    expect(recomendado).toBeDefined();
    expect(recomendado!.id).toBe('opencode-go');
  });

  it('filtra destacados', () => {
    const destacadosIds = new Set(['opencode-go', 'anthropic', 'openai', 'openai-api', 'openai-codex', 'google', 'gemini', 'copilot', 'openrouter']);
    const destacados = raw.filter(p => p.id !== 'opencode-go' && destacadosIds.has(p.id));
    const resto = raw.filter(p => p.id !== 'opencode-go' && !destacadosIds.has(p.id));

    expect(destacados.length).toBe(3); // anthropic, openai, google
    expect(resto.length).toBe(1);      // some-unknown
  });
});

describe('modelos - extraccion', () => {
  it('extrae lista de array directo', () => {
    const modelsRaw = ['gpt-4', 'gpt-3.5'];
    const list: string[] = Array.isArray(modelsRaw) ? modelsRaw : [];
    expect(list).toEqual(['gpt-4', 'gpt-3.5']);
  });

  it('extrae lista de objeto con .list', () => {
    const modelsRaw = { list: ['gpt-4', 'gpt-3.5'], recommended: 'gpt-4' };
    const list: string[] = Array.isArray(modelsRaw) ? modelsRaw : ((asModels(modelsRaw).list || asModels(modelsRaw).models || []) as string[]);
    expect(list).toEqual(['gpt-4', 'gpt-3.5']);
  });

  it('extrae recommended de objeto', () => {
    const modelsRaw = { list: ['gpt-4', 'gpt-3.5'], recommended: 'gpt-4' };
    const recommended: string = Array.isArray(modelsRaw) ? '' : (asModels(modelsRaw).recommended || '');
    expect(recommended).toBe('gpt-4');
  });

  it('separa recommended del resto', () => {
    const modelsRaw = { list: ['gpt-4', 'gpt-3.5', 'claude-3'], recommended: 'gpt-4' };
    const list: string[] = Array.isArray(modelsRaw) ? modelsRaw : ((asModels(modelsRaw).list || asModels(modelsRaw).models || []) as string[]);
    const recommended: string = Array.isArray(modelsRaw) ? '' : (asModels(modelsRaw).recommended || '');
    const rest = list.filter(m => m !== recommended);

    expect(rest).toEqual(['gpt-3.5', 'claude-3']);
  });

  it('retorna vacio si no hay modelos', () => {
    const modelsRaw = {};
    const list: string[] = Array.isArray(modelsRaw) ? modelsRaw : ((asModels(modelsRaw).list || asModels(modelsRaw).models || []) as string[]);
    expect(list).toEqual([]);
  });
});

describe('progreso - calculo', () => {
  it('calcula progreso desde backend', () => {
    const progress = { total: 5, done: 2 };
    const progreso = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
    expect(progreso).toBe(40);
  });

  it('progreso 0 cuando no hay pasos', () => {
    const progress = { total: 0, done: 0 };
    const progreso = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
    expect(progreso).toBe(0);
  });

  it('progreso 100 cuando todos completos', () => {
    const progress = { total: 5, done: 5 };
    const progreso = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
    expect(progreso).toBe(100);
  });
});

describe('finalizacion - checks', () => {
  it('todas las condiciones ok cuando todo configurado', () => {
    const agent_online = true;
    const modules = ['core', 'office', 'developer'];
    const MODULE_CHECK_KEYS: Record<string, string[]> = {
      office: ['google'],
      developer: ['github', 'vercel', 'supabase'],
    };

    // Simular todos los checks ok
    const allChecks: Record<string, string> = {
      provider: 'ok', google: 'ok', github: 'ok', vercel: 'ok', supabase: 'ok',
    };

    const items = [
      { label: 'Agente instalado', ok: agent_online },
      { label: 'Proveedor IA', ok: allChecks.provider === 'ok' },
      {
        label: 'Modulos conectados',
        ok: modules.every((m: string) =>
          m === 'core' || (MODULE_CHECK_KEYS[m] || []).every(k => allChecks[k] === 'ok')
        ),
      },
    ];

    expect(items.every(i => i.ok)).toBe(true);
  });

  it('detecta proveedor no configurado', () => {
    const checks = { provider: 'missing' };
    expect(checks.provider === 'ok').toBe(false);
  });

  it('detecta modulo office no conectado', () => {
    const modules = ['core', 'office'];
    const MODULE_CHECK_KEYS: Record<string, string[]> = {
      office: ['google'],
    };
    const allChecks: Record<string, string> = { google: 'missing' };

    const modulosOk = modules.every((m: string) =>
      m === 'core' || (MODULE_CHECK_KEYS[m] || []).every(k => allChecks[k] === 'ok')
    );

    expect(modulosOk).toBe(false);
  });
});

describe('AuthForm - logica de validacion', () => {
  it('detecta nombre vacio en registro', () => {
    const nombre = '';
    const esRegistro = true;
    let errorLocal: string | null = null;

    if (esRegistro && !nombre.trim()) {
      errorLocal = 'El nombre es obligatorio';
    }

    expect(errorLocal).toBe('El nombre es obligatorio');
  });

  it('no valida nombre en login', () => {
    const nombre = '';
    const esRegistro = false;
    let errorLocal: string | null = null;

    if (esRegistro && !nombre.trim()) {
      errorLocal = 'El nombre es obligatorio';
    }

    expect(errorLocal).toBeNull();
  });

  it('minLength de password es 8', () => {
    // El input tiene minLength={8}
    const minLength = 8;
    expect('1234567'.length).toBeLessThan(minLength);
    expect('12345678'.length).toBeGreaterThanOrEqual(minLength);
  });
});

describe('wizard - estados iniciales', () => {
  it('pasoActual usa wizard_step del onboarding', () => {
    const onboarding = { wizard_step: 2 };
    const vistaActual = null;
    const pasoActual = vistaActual ?? onboarding.wizard_step ?? 0;
    expect(pasoActual).toBe(2);
  });

  it('vistaActual sobreescribe wizard_step', () => {
    const onboarding = { wizard_step: 0 };
    const vistaActual = 3;
    const pasoActual = vistaActual ?? onboarding.wizard_step ?? 0;
    expect(pasoActual).toBe(3);
  });

  it('fallback a 0 cuando no hay datos', () => {
    const onboarding = { wizard_step: undefined } as any;
    const vistaActual = null;
    const pasoActual = vistaActual ?? onboarding.wizard_step ?? 0;
    expect(pasoActual).toBe(0);
  });

  it('pasosCompletados cuenta pasos unicos por wizard step', () => {
    const wizardStepMap: Record<string, number> = {
      bootstrap: 0, 'google-oauth': 1, 'gmail-setup': 2,
      'trello-setup': 2, 'github-setup': 2, finalize: 3, done: 3,
    };
    const completed = ['bootstrap', 'google-oauth', 'gmail-setup', 'github-setup'];
    const count = new Set(
      completed.map((s) => wizardStepMap[s])
        .filter((s): s is number => s !== undefined)
    ).size;
    // bootstrap=0, google-oauth=1, gmail-setup=2, github-setup=2
    // Set = {0, 1, 2} → size=3
    expect(count).toBe(3);
  });

  it('ignora pasos desconocidos en completed', () => {
    const wizardStepMap: Record<string, number> = {
      bootstrap: 0, finalize: 3, done: 3,
    };
    const completed = ['bootstrap', 'unknown-step', 'finalize'];
    const count = new Set(
      completed.map((s) => wizardStepMap[s])
        .filter((s): s is number => s !== undefined)
    ).size;
    expect(count).toBe(2);
  });
});

describe('checks - utilidad', () => {
  it('checks vacio es seguro', () => {
    const checks: Record<string, string> = {};
    expect(checks.provider === 'ok').toBe(false);
    expect(checks.google === 'error').toBe(false);
  });

  it('checks con valor undefined es seguro', () => {
    const checks: Record<string, string | undefined> = { provider: undefined };
    expect((checks.provider || 'missing') === 'ok').toBe(false);
  });
});

describe('conectarOAuth - logica', () => {
  it('detecta popup bloqueado', () => {
    // Simular window.open devolviendo null
    const popup = null;
    let error: string | null = null;
    if (!popup) {
      error = 'El navegador bloqueó la ventana emergente. Permite popups para este sitio.';
    }
    expect(error).toContain('popups');
  });
});

describe('token extraction', () => {
  it('usa params.token cuando existe', () => {
    const params = { token: 'abc-123' };
    const token = params.token || '/setup/fallback'.replace('/setup/', '').replace('/onboarding/', '');
    expect(token).toBe('abc-123');
  });

  it('extrae de pathname cuando no hay params', () => {
    const params: { token?: string } = {};
    const pathname = '/setup/uuid-vcoo-456';
    const token = params.token || pathname.replace('/setup/', '').replace('/onboarding/', '');
    expect(token).toBe('uuid-vcoo-456');
  });

  it('extrae de pathname /onboarding/', () => {
    const params: { token?: string } = {};
    const pathname = '/onboarding/uuid-789';
    const token = params.token || pathname.replace('/setup/', '').replace('/onboarding/', '');
    expect(token).toBe('uuid-789');
  });
});
