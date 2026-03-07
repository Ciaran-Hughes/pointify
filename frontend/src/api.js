/**
 * Authenticated fetch wrapper. Handles JWT access tokens and silent refresh.
 * SECURITY: Tokens stored in localStorage (acceptable for single-origin PWA).
 * All requests go through this wrapper — never use fetch() directly.
 */

const BASE = '/api/v1';

function getTokens() {
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  };
}

function setTokens(access, refresh) {
  if (access) localStorage.setItem('access_token', access);
  if (refresh) localStorage.setItem('refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

async function silentRefresh() {
  const { refresh } = getTokens();
  if (!refresh) throw new Error('No refresh token');
  const r = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!r.ok) {
    clearTokens();
    throw new Error('Session expired');
  }
  const data = await r.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}

async function request(path, options = {}, _retry = true) {
  const { access } = getTokens();
  const headers = {
    ...(options.headers || {}),
    ...(access ? { Authorization: `Bearer ${access}` } : {}),
  };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401 && _retry) {
    try {
      await silentRefresh();
      return request(path, options, false);
    } catch {
      clearTokens();
      window.dispatchEvent(new CustomEvent('auth:expired'));
      throw new Error('Session expired');
    }
  }

  return res;
}

async function json(path, options = {}) {
  const res = await request(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = body?.detail?.detail || body?.detail || 'Request failed';
    const err = new Error(msg);
    err.status = res.status;
    err.errorCode = body?.detail?.error_code;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  // Use plain fetch — login has no token to refresh, so the retry middleware
  // must not run. A 401 here means wrong credentials, not an expired session.
  login: async (username, password) => {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = body?.detail?.detail || body?.detail || 'Invalid username or password';
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return body;
  },

  // Use plain fetch so a 401 response (stale token) does NOT re-trigger auth:expired,
  // which would cause an infinite logout loop via AuthListener → logout() → 401 → auth:expired.
  logout: () => {
    const { access } = getTokens();
    return fetch(`${BASE}/auth/logout`, {
      method: 'POST',
      headers: access ? { Authorization: `Bearer ${access}` } : {},
    }).catch(() => {});
  },

  refresh: () => silentRefresh(),

  changePassword: (current_password, new_password) =>
    json('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),

  me: () => json('/auth/me'),

  updatePreferences: (data) =>
    json('/auth/me/preferences', { method: 'PATCH', body: JSON.stringify(data) }),
};

export function storeLoginResponse(data) {
  setTokens(data.access_token, data.refresh_token);
}

// ── Pages ─────────────────────────────────────────────────────────────────────

export const pages = {
  list: (page = 1, perPage = 20) => json(`/pages?page=${page}&per_page=${perPage}`),
  get: (id) => json(`/pages/${id}`),
  create: (name) => json('/pages', { method: 'POST', body: JSON.stringify({ name }) }),
  update: (id, name) => json(`/pages/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
  delete: (id) => json(`/pages/${id}`, { method: 'DELETE' }),
  days: (id) => json(`/pages/${id}/days`),
};

// ── Recordings ────────────────────────────────────────────────────────────────

export const recordings = {
  upload: (pageId, audioBlob, whisperModel = 'medium', whisperLanguage = 'en') => {
    const form = new FormData();
    form.append('file', audioBlob, 'recording.webm');
    return json(
      `/pages/${pageId}/recordings?whisper_model=${whisperModel}&whisper_language=${whisperLanguage}`,
      { method: 'POST', body: form },
    );
  },

  retranscribe: (recordingId) =>
    json(`/recordings/${recordingId}/retranscribe`, { method: 'POST' }),

  archive: (recordingId) =>
    json(`/recordings/${recordingId}`, { method: 'DELETE' }),

  archiveDay: (recordingId) =>
    json(`/recordings/${recordingId}/day`, { method: 'DELETE' }),
};

// ── Bullets ───────────────────────────────────────────────────────────────────

export const bullets = {
  add: (pageId, text, day) =>
    json(`/pages/${pageId}/bullets`, {
      method: 'POST',
      body: JSON.stringify({ text, day }),
    }),

  update: (bulletId, text) =>
    json(`/bullets/${bulletId}`, { method: 'PATCH', body: JSON.stringify({ text }) }),

  delete: (bulletId) => json(`/bullets/${bulletId}`, { method: 'DELETE' }),

  reorder: (pageId, orderedIds) =>
    json(`/pages/${pageId}/bullets/reorder`, {
      method: 'PATCH',
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),
};

// ── Admin ─────────────────────────────────────────────────────────────────────

export const admin = {
  listUsers: () => json('/admin/users'),
  getUser: (id) => json(`/admin/users/${id}`),
  createUser: (data) => json('/admin/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id, data) =>
    json(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  disableUser: (id) => json(`/admin/users/${id}/disable`, { method: 'POST' }),
  enableUser: (id) => json(`/admin/users/${id}/enable`, { method: 'POST' }),
  resetPassword: (id, new_password) =>
    json(`/admin/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password }),
    }),
  getSettings: () => json('/admin/settings'),
  updateSettings: (data) =>
    json('/admin/settings', { method: 'PATCH', body: JSON.stringify(data) }),
};

// ── Health ────────────────────────────────────────────────────────────────────

export const health = {
  check: () => json('/health'),
};
