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

// ── VCOOs ──────────────────────────────────────────────
export const createVCOO = () =>
  api('/vcoo', { method: 'POST' });

export const listVCOOs = (): Promise<
  Array<{
    id: string;
    created_at: string;
    agent: { id: string; status: string; last_seen: string } | null;
  }>
> => api('/vcoos');

export const getProvisionToken = (vcooId: string): Promise<{ token: string; install_command: string }> =>
  api(`/vcoo/${vcooId}/provision-token`);

export const getVCOOState = (vcooId: string): Promise<{
  id: string;
  agent: { id: string; status: string; last_seen: string } | null;
}> => api(`/vcoo/${vcooId}/state`);

export const enqueueCommand = (vcooId: string, command: string): Promise<{ cmd_id: string }> =>
  api(`/vcoo/${vcooId}/commands`, {
    method: 'POST',
    body: JSON.stringify({ command }),
  });

// ── Agent ──────────────────────────────────────────────
export const registerAgent = (token: string, info: Record<string, any> = {}) =>
  api('/register', {
    method: 'POST',
    body: JSON.stringify({ token, info }),
  });

// ── Playbooks ──────────────────────────────────────────
export const listPlaybooks = (): Promise<{ playbooks: string[] }> =>
  api('/playbooks');

export const getPlaybook = (name: string): Promise<{ name: string; script: string }> =>
  api(`/playbooks/${name}`);

// ── Health ─────────────────────────────────────────────
export const healthCheck = (): Promise<{ status: string }> =>
  api('/health');
