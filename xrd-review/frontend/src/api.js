const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${path} -> ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  listReferences: () => request('/api/references'),
  analyze: (payload) =>
    request('/api/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  synthetic: (payload) =>
    request('/api/synthetic', { method: 'POST', body: JSON.stringify(payload) }),
}
