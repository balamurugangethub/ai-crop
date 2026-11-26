const TOKEN_KEY = 'cropdoctor.token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(code, status, body) {
    super(code)
    this.code = code
    this.status = status
    this.body = body
  }
}

export async function api(path, { method = 'GET', body, form, signal } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) payload = form
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch(path, { method, headers, body: payload, signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError('network', 0)
  }
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    // diagnose returns 422 with a structured body for rejected photos
    if (res.status === 422 && data?.status === 'rejected') return data
    const code = typeof data?.detail === 'string' ? data.detail : 'generic'
    if (res.status === 401) setToken(null)
    throw new ApiError(code, res.status, data)
  }
  return data
}

export function imageUrl(path) {
  return `${path}?token=${encodeURIComponent(getToken() || '')}`
}
