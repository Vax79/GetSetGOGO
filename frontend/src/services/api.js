const jsonHeaders = { 'Content-Type': 'application/json' }
let accessToken = ''
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function apiUrl(path) {
  return `${apiBaseUrl}${path}`
}

export function setAccessToken(token) {
  accessToken = token || ''
}

async function request(path, options = {}) {
  const headers = { ...options.headers, ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) }
  const response = await fetch(apiUrl(path), { ...options, headers })
  const payload = response.status === 204 ? null : await response.text()
  let data = payload
  try { data = payload ? JSON.parse(payload) : null } catch { /* Preserve plain-text proxy/server errors for the caller. */ }
  if (!response.ok) throw new Error(data?.detail || (typeof data === 'string' && data.trim()) || 'Something went wrong. Please try again.')
  return data
}

export const tripApi = {
  list: () => request('/api/trips'),
  create: (payload) => request('/api/trips', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) }),
  update: (tripId, payload) => request(`/api/trips/${tripId}`, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(payload) }),
  exportPdf: async (tripId) => {
    const response = await fetch(apiUrl(`/api/trips/${tripId}/export/pdf`), { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
    if (!response.ok) {
      const data = await response.json().catch(() => null)
      throw new Error(data?.detail || 'Could not export the itinerary.')
    }
    const file = await response.blob()
    const objectUrl = URL.createObjectURL(file)
    const anchor = window.document.createElement('a')
    anchor.href = objectUrl
    anchor.download = 'jetsetgo-itinerary.pdf'
    anchor.click()
    URL.revokeObjectURL(objectUrl)
  },
}

export const collaborationApi = {
  share: (tripId) => request(`/api/trips/${tripId}/share`),
  members: (tripId) => request(`/api/trips/${tripId}/members`),
  join: (payload) => request('/api/trips/join', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) }),
  ensureMember: (tripId, displayName) => request(`/api/trips/${tripId}/members`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ display_name: displayName }) }),
  voteCandidates: (tripId, displayName) => request(`/api/trips/${tripId}/vote-candidates?display_name=${encodeURIComponent(displayName)}`),
  vote: (activityId, displayName, voteValue) => request(`/api/activities/${activityId}/vote`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ display_name: displayName, vote_value: voteValue }) }),
}

export const profileApi = {
  update: (displayName) => request('/api/users/me', { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify({ display_name: displayName }) }),
}

export const authApi = {
  register: (payload) => request('/api/auth/register', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) }),
  login: (payload) => request('/api/auth/login', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) }),
  me: () => request('/api/auth/me'),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
}

export const activityApi = {
  list: (tripId, scheduled) => request(`/api/trips/${tripId}/activities?scheduled=${scheduled}`),
  create: (tripId, payload) => request(`/api/trips/${tripId}/activities`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/api/activities/${id}`, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(payload) }),
  remove: (id) => request(`/api/activities/${id}`, { method: 'DELETE' }),
  reorder: (tripId, date, activityIds) => request(`/api/trips/${tripId}/itinerary/${date}/order`, { method: 'PUT', headers: jsonHeaders, body: JSON.stringify({ activity_ids: activityIds }) }),
  routeSegments: (tripId, date) => request(`/api/trips/${tripId}/itinerary/${date}/routes`),
  placeSearch: (tripId, query) => request(`/api/trips/${tripId}/place-search?query=${encodeURIComponent(query)}`),
}

export const tiktokApi = {
  metadata: (tripId, sourceUrl) => request(`/api/trips/${tripId}/video-metadata`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ source_url: sourceUrl }) }),
  transcript: (tripId, sourceUrl) => request(`/api/trips/${tripId}/video-metadata/transcript`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ source_url: sourceUrl }) }),
  extract: (tripId, metadata, transcript) => request(`/api/trips/${tripId}/activity-extractions`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ source_url: metadata.source_url, caption: metadata.caption, transcript: transcript?.detected ? transcript.text : null }) }),
  approve: (tripId, candidate) => request(`/api/trips/${tripId}/activity-extractions/approve`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(candidate) }),
}
