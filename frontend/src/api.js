const BASE = ''

async function jsonFetch(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch (_) { /* ignore */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json()
}

export const api = {
  health: () => jsonFetch('/api/health'),
  constants: () => jsonFetch('/api/constants'),
  listReferences: () => jsonFetch('/api/references'),
  getReference: (code) => jsonFetch(`/api/references/${encodeURIComponent(code)}`),
  analyze: (body) => jsonFetch('/api/analyze', { method: 'POST', body: JSON.stringify(body) }),
  generateDemo: (c) => jsonFetch('/api/demos/generate', {
    method: 'POST', body: JSON.stringify({ case: c }),
  }),
  savePeakList: (body) => jsonFetch('/api/references/peaklist', {
    method: 'POST', body: JSON.stringify(body),
  }),
  saveCubic: (body) => jsonFetch('/api/references/cubic', {
    method: 'POST', body: JSON.stringify(body),
  }),
  deleteReference: (code) => jsonFetch(`/api/references/${encodeURIComponent(code)}`, {
    method: 'DELETE',
  }),
}
