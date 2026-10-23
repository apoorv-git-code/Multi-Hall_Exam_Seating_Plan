// Thin fetch client for server.py. Every function throws an Error with a readable message.
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, options = {}) {
  let res
  try {
    // Same-origin deployments send the session cookie automatically; a separate API origin needs 'include'.
    res = await fetch(`${BASE}${path}`, { credentials: BASE ? 'include' : 'same-origin', ...options })
  } catch {
    throw new Error('Cannot reach the API server. Is "uvicorn server:app" running on port 8000?')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string'
        ? body.detail
        : (body.detail || []).map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ') || detail
    } catch { /* body was not JSON */ }
    throw new Error(detail)
  }
  return res
}

const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  algorithms: async () => (await request('/api/algorithms')).json(),
  generate: async (params) => (await request('/api/dataset/generate', json(params))).json(),
  sample: async () => (await request('/api/dataset/sample', { method: 'POST' })).json(),
  loadJson: async (dataset) => (await request('/api/dataset/load', json(dataset))).json(),
  upload: async (studentsFile, hallsFile) => {
    const form = new FormData()
    form.append('students_file', studentsFile)
    form.append('halls_file', hallsFile)
    return (await request('/api/dataset/upload', { method: 'POST', body: form })).json()
  },
  currentDataset: async () => (await request('/api/dataset')).json(),
  health: async () => (await request('/api/health')).json(),
  resetSession: async () => { await request('/api/session', { method: 'DELETE' }) },
  allocate: async (params) => (await request('/api/allocate', json(params))).json(),
  benchmark: async (params) => (await request('/api/benchmark', json(params))).json(),
}

/** Download an export through fetch so server errors can be shown instead of navigating away. */
export async function downloadExport(format, plot) {
  const qs = plot ? `?plot=${encodeURIComponent(plot)}` : ''
  const res = await request(`/api/export/${format}${qs}`)
  const disposition = res.headers.get('Content-Disposition') || ''
  const name = (/filename="?([^";]+)"?/.exec(disposition) || [])[1] || `export.${format}`
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return name
}
