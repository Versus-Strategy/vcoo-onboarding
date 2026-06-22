const API_BASE = import.meta.env.VITE_API_URL || 'https://vcoo-onboarding.vercel.app';

let masterKey: string | null = null;

export function setMasterKey(key: string) {
  masterKey = key;
}
export function getMasterKey(): string | null {
  return masterKey;
}

async function api(path: string, options: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (masterKey) {
    headers['Authorization'] = `Bearer ${masterKey}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ────────────────────────────────────────────────
export const verifyAuth = (password: string): Promise<{ status: string }> =>
  api('/auth/verify', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });

// ── VCOOs ──────────────────────────────────────────────
export const createVCOO = (name?: string, modules?: string[]) =>
  api('/vcoo', {
    method: 'POST',
    body: JSON.stringify({ name: name || null, modules: modules || ['core'] }),
  });

export interface VCOOResult {
  id: string;
  name: string | null;
  status: string;
  created_at: string;
  agent: { id: string; status: string; last_seen: string } | null;
  active_token: string | null;
  token_expires_at: string | null;
  modules?: string[];
}

export const listVCOOs = (): Promise<VCOOResult[]> =>
  api('/vcoos');

export const getProvisionToken = (vcooId: string): Promise<{ token: string; install_command: string }> =>
  api(`/vcoo/${vcooId}/provision-token`);

export const regenerateToken = (vcooId: string): Promise<{ token: string; install_command: string }> =>
  api(`/vcoo/${vcooId}/regenerate-token`, { method: 'POST' });

export const completeVCOO = (vcooId: string): Promise<{ status: string }> =>
  api(`/vcoo/${vcooId}/complete`, { method: 'POST' });

export const reactivateVCOO = (vcooId: string): Promise<{ status: string; token: string; install_command: string }> =>
  api(`/vcoo/${vcooId}/reactivate`, { method: 'POST' });

export const deleteVCOO = (vcooId: string): Promise<{ status: string }> =>
  api(`/vcoo/${vcooId}`, { method: 'DELETE' });

export const getVCOOState = (vcooId: string): Promise<{
  id: string;
  name: string | null;
  status: string;
  agent: { id: string; status: string; last_seen: string } | null;
  active_token: string | null;
}> => api(`/vcoo/${vcooId}/state`);

export const enqueueCommand = (vcooId: string, command: string): Promise<{ cmd_id: string }> =>
  api(`/vcoo/${vcooId}/commands`, {
    method: 'POST',
    body: JSON.stringify({ command }),
  });

// ── Setup Wizard (SPEC v2) ──────────────────────────────

export interface SetupInfo {
  vcoo_id: string;
  name: string | null;
  modules: string[];
  step: string;
  status: string;
  completed: string[];
  errors: { step: string; error: string; timestamp?: string }[];
  retry_count: Record<string, number>;
  progress: { total: number; done: number };
  install_command: string;
  agent_online?: boolean;
}

export const getSetupInfo = (token: string): Promise<SetupInfo> =>
  api('/setup/' + token);

export const verifyStep = (token: string): Promise<{ status: string; cmd_id?: string; step?: string; command?: string; message?: string }> =>
  api('/setup/' + token + '/verify', { method: 'POST' });

export const getAuthUrl = (token: string, service: string): Promise<{ url: string; service: string }> =>
  api('/setup/' + token + '/auth-url?service=' + encodeURIComponent(service));

export const getHermesCommands = (token: string, service: string): Promise<{ commands: string[]; service: string }> =>
  api('/setup/' + token + '/hermes-commands?service=' + encodeURIComponent(service));

// ── Agent ──────────────────────────────────────────────
export const registerAgent = (token: string, info: Record<string, any> = {}) =>
  api('/register', {
    method: 'POST',
    body: JSON.stringify({ token, info }),
  });

export const completeSetup = (agentId: string): Promise<{ status: string }> =>
  api(`/agent/${agentId}/complete`, { method: 'POST' });

// ── Playbooks ──────────────────────────────────────────
export const listPlaybooks = (): Promise<{ playbooks: string[] }> =>
  api('/playbooks');

export const getPlaybook = (name: string): Promise<{ name: string; script: string }> =>
  api(`/playbooks/${name}`);

// ── Health ─────────────────────────────────────────────
export const healthCheck = (): Promise<{ status: string }> =>
  api('/health');
