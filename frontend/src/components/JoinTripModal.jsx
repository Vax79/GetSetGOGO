import { useState } from 'react'

export default function JoinTripModal({ initialCode = '', displayName, onSaveDisplayName, onJoin, onClose, submitting, error }) {
  const [shareCode, setShareCode] = useState(initialCode)
  const [name, setName] = useState(displayName)
  const submit = async (event) => {
    event.preventDefault()
    const trimmedName = name.trim()
    const result = await onJoin({ share_code: shareCode.trim(), display_name: trimmedName })
    if (result) onSaveDisplayName(trimmedName)
  }

  return <div className="fixed inset-0 z-50 grid place-items-center bg-[#263230]/45 p-5" role="dialog" aria-modal="true" aria-label="Join shared trip"><form onSubmit={submit} className="w-full max-w-md rounded-[1.75rem] bg-[#fdfbf7] p-6 shadow-2xl sm:p-8"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold tracking-[.18em] text-[#e0604e]">JOIN A TRIP</p><h2 className="mt-2 font-serif text-3xl tracking-[-.04em] text-[#263230]">Bring your ideas along.</h2></div><button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-xl text-[#68716d] hover:bg-[#f0eee8]" aria-label="Close join dialog">×</button></div><p className="mt-3 text-sm leading-6 text-[#68716d]">Use the invitation code and the display name your travel group will recognise.</p><label className="mt-6 block text-xs font-bold tracking-[.12em] text-[#68716d]">TRIP CODE<input required value={shareCode} onChange={(event) => setShareCode(event.target.value.toUpperCase())} placeholder="ABCD-1234" className="mt-2 w-full rounded-xl border border-[#dedbd3] bg-white px-4 py-3 font-mono text-base tracking-[.12em] outline-none focus:border-[#6f867e]" /></label><label className="mt-4 block text-xs font-bold tracking-[.12em] text-[#68716d]">YOUR DISPLAY NAME<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Xavier" maxLength="80" className="mt-2 w-full rounded-xl border border-[#dedbd3] bg-white px-4 py-3 text-base outline-none focus:border-[#6f867e]" /></label>{error && <p className="mt-4 rounded-xl bg-[#fff0ed] px-3 py-2 text-sm text-[#9a4c3e]">{error}</p>}<button disabled={submitting} className="mt-6 w-full rounded-xl bg-[#263230] px-4 py-3 text-sm font-bold text-white disabled:opacity-60">{submitting ? 'Joining…' : 'Join shared trip'}</button></form></div>
}
