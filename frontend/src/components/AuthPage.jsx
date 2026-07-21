import { useState } from 'react'

export default function AuthPage({ onAuthenticate }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setMessage('')
    try {
      await onAuthenticate(mode, mode === 'register' ? { username, password, display_name: displayName } : { username, password })
    } catch (error) { setMessage(error.message || 'Could not sign in.') }
    setSubmitting(false)
  }

  const registering = mode === 'register'
  return <main className="grid min-h-screen place-items-center bg-[#f6f3ed] p-5 text-[#263230]"><section className="w-full max-w-md rounded-[2rem] border border-[#e4e0d8] bg-white p-7 shadow-[0_20px_60px_rgba(38,50,48,.10)] sm:p-9"><div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#263230] font-serif text-2xl text-[#f6b5a7]">J</div><p className="mt-7 text-xs font-bold tracking-[.2em] text-[#e0604e]">JETSETGO</p><h1 className="mt-3 font-serif text-4xl tracking-[-.05em]">Your trips, safely yours.</h1><p className="mt-3 text-sm leading-6 text-[#68716d]">Use your username and password to access your plans across devices.</p><form className="mt-7 space-y-4" onSubmit={submit}><label className="block text-sm font-bold">Username<input required className="mt-1.5 w-full rounded-xl border border-[#dedbd3] px-3 py-3 font-normal" value={username} onChange={(event) => setUsername(event.target.value)} minLength="3" maxLength="32" pattern="[A-Za-z0-9_]+" placeholder="e.g. jetsetter" autoComplete="username" /></label>{registering && <label className="block text-sm font-bold">Display name<input required className="mt-1.5 w-full rounded-xl border border-[#dedbd3] px-3 py-3 font-normal" value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength="80" placeholder="Use your previous name to claim migrated trips" /></label>}<label className="block text-sm font-bold">Password<input required type="password" className="mt-1.5 w-full rounded-xl border border-[#dedbd3] px-3 py-3 font-normal" value={password} onChange={(event) => setPassword(event.target.value)} minLength={registering ? 10 : 1} maxLength="128" autoComplete={registering ? 'new-password' : 'current-password'} /></label><button disabled={submitting} className="w-full rounded-xl bg-[#263230] px-4 py-3 font-bold text-white disabled:opacity-60">{submitting ? 'Working…' : registering ? 'Create account' : 'Sign in'}</button></form><button type="button" className="mt-5 w-full text-sm font-semibold text-[#52635e] underline underline-offset-4" onClick={() => { setMode(registering ? 'login' : 'register'); setMessage('') }}>{registering ? 'Already have an account? Sign in' : 'New here? Create an account'}</button>{message && <p className="mt-4 rounded-xl bg-[#fff0ed] px-3 py-2.5 text-sm text-[#9a4c3e]" role="status">{message}</p>}</section></main>
}
