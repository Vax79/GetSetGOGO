import { useEffect, useState } from 'react'
import { authApi, setAccessToken } from '../services/api'

const storageKey = 'jetsetgo-session-token'

function storedToken() {
  try { return localStorage.getItem(storageKey) || '' } catch { return '' }
}

export function useAuthSession() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = storedToken()
    if (!token) { setLoading(false); return }
    setAccessToken(token)
    authApi.me().then((user) => setSession({ access_token: token, user })).catch(() => {
      setAccessToken('')
      try { localStorage.removeItem(storageKey) } catch { /* Keep the cleared in-memory session when storage is unavailable. */ }
    }).finally(() => setLoading(false))
  }, [])

  const authenticate = async (mode, payload) => {
    const nextSession = mode === 'register' ? await authApi.register(payload) : await authApi.login(payload)
    setAccessToken(nextSession.access_token)
    try { localStorage.setItem(storageKey, nextSession.access_token) } catch { /* The session remains available until this page is closed. */ }
    setSession(nextSession)
  }
  const signOut = async () => {
    try { await authApi.logout() } finally {
      setAccessToken('')
      try { localStorage.removeItem(storageKey) } catch { /* The in-memory session is still cleared below. */ }
      setSession(null)
    }
  }

  return { session, loading, authenticate, signOut }
}
