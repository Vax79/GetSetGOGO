import { useEffect, useState } from 'react'
import { collaborationApi } from '../services/api'

export default function ShareTripModal({ trip, onClose }) {
  const [shareCode, setShareCode] = useState('')
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const shareUrl = shareCode ? `${window.location.origin}${window.location.pathname}?join=${encodeURIComponent(shareCode)}` : ''

  useEffect(() => {
    let cancelled = false
    collaborationApi.share(trip.id).then(({ share_code: code }) => { if (!cancelled) setShareCode(code) }).catch((requestError) => { if (!cancelled) setError(requestError.message) })
    return () => { cancelled = true }
  }, [trip.id])

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
    } catch {
      setError('Copy the invitation link from the field below.')
    }
  }

  return <div className="fixed inset-0 z-50 grid place-items-center bg-[#263230]/45 p-5" role="dialog" aria-modal="true" aria-label="Share trip"><section className="w-full max-w-lg rounded-[1.75rem] bg-[#fdfbf7] p-6 shadow-2xl sm:p-8"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold tracking-[.18em] text-[#e0604e]">SHARE TRIP</p><h2 className="mt-2 font-serif text-3xl tracking-[-.04em] text-[#263230]">Plan it together.</h2></div><button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-xl text-[#68716d] hover:bg-[#f0eee8]" aria-label="Close share dialog">×</button></div><p className="mt-3 text-sm leading-6 text-[#68716d]">Anyone with this invitation can join the shared pool with a display name, submit ideas, and leave a visual vote.</p>{error && <p className="mt-5 rounded-xl bg-[#fff0ed] px-3 py-2 text-sm text-[#9a4c3e]">{error}</p>}{shareCode ? <><div className="mt-6 rounded-2xl bg-[#263230] px-5 py-5 text-center text-white"><p className="text-[10px] font-bold tracking-[.2em] text-[#f6b5a7]">TRIP CODE</p><p className="mt-2 font-mono text-3xl font-bold tracking-[.18em]">{shareCode}</p></div><label className="mt-5 block text-xs font-bold tracking-[.12em] text-[#68716d]">INVITATION LINK<input readOnly value={shareUrl} onFocus={(event) => event.target.select()} className="mt-2 w-full rounded-xl border border-[#dedbd3] bg-white px-3 py-3 text-sm font-normal tracking-normal text-[#52635e]" /></label><button type="button" onClick={copyInvite} className="mt-4 w-full rounded-xl bg-[#e0604e] px-4 py-3 text-sm font-bold text-white hover:bg-[#c65343]">{copied ? 'Copied invitation' : 'Copy invitation link'}</button><p className="mt-4 text-xs leading-5 text-[#89938e]">Trip codes are intentionally lightweight—share them only with people you want to collaborate with.</p></> : !error && <div className="mt-6 rounded-2xl bg-[#f0eee8] p-5 text-sm text-[#68716d]">Preparing your invitation…</div>}</section></div>
}
