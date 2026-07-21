import { useState } from 'react'

const storageKey = 'jetsetgo-display-name'

function readName() {
  try { return localStorage.getItem(storageKey) || '' } catch { return '' }
}

export function useDisplayName() {
  const [displayName, setDisplayName] = useState(readName)
  const saveDisplayName = (value) => {
    const nextName = value.trim().slice(0, 80)
    setDisplayName(nextName)
    try { localStorage.setItem(storageKey, nextName) } catch { /* Keep the current-session value when storage is unavailable. */ }
  }
  const clearDisplayName = () => {
    setDisplayName('')
    try { localStorage.removeItem(storageKey) } catch { /* Keep the cleared in-memory value when storage is unavailable. */ }
  }
  return { displayName, saveDisplayName, clearDisplayName }
}
