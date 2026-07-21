import { useEffect, useRef, useState } from 'react'
import { collaborationApi } from '../services/api'

export default function VoteDeck({ tripId, displayName }) {
  const [candidates, setCandidates] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [dragX, setDragX] = useState(0)
  const pointerStart = useRef(null)
  const candidate = candidates[0]

  useEffect(() => {
    if (!tripId || !displayName) { setCandidates([]); setLoading(false); return }
    let cancelled = false
    setLoading(true)
    collaborationApi.ensureMember(tripId, displayName).then(() => collaborationApi.voteCandidates(tripId, displayName)).then((items) => { if (!cancelled) { setCandidates(items); setError('') } }).catch((requestError) => { if (!cancelled) setError(requestError.message) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [displayName, tripId])

  const vote = async (value) => {
    if (!candidate) return
    try {
      await collaborationApi.vote(candidate.id, displayName, value)
      setCandidates((current) => current.slice(1))
    } catch (requestError) { setError(requestError.message) } finally { setDragX(0) }
  }
  const pointerDown = (event) => { pointerStart.current = event.clientX; event.currentTarget.setPointerCapture?.(event.pointerId) }
  const pointerMove = (event) => { if (pointerStart.current !== null) setDragX(event.clientX - pointerStart.current) }
  const pointerUp = () => { const value = dragX > 90 ? 1 : dragX < -90 ? -1 : 0; pointerStart.current = null; if (value) vote(value); else setDragX(0) }

  return <section className="rounded-3xl border border-[#dedbd3] bg-[#fdfbf7] p-5 shadow-[0_10px_30px_rgba(38,50,48,.04)]"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold tracking-[.16em] text-[#e0604e]">GROUP PULSE</p><h3 className="mt-1 font-serif text-2xl tracking-[-.03em] text-[#263230]">What is the group excited about?</h3></div><span className="rounded-full bg-[#e7eee9] px-3 py-1 text-xs font-semibold text-[#49635d]">Visual only</span></div><p className="mt-2 text-sm leading-6 text-[#6d7974]">Swipe right to upvote or left to pass. Votes never change approval, placement, or your itinerary.</p>{!displayName && <p className="mt-4 rounded-xl bg-[#fff8e7] p-3 text-sm text-[#796225]">Add a display name on the home screen before voting with your group.</p>}{loading && displayName && <p className="mt-5 text-sm text-[#68716d]">Loading group picks…</p>}{error && <p className="mt-4 rounded-xl bg-[#fff0ed] p-3 text-sm text-[#9a4c3e]">{error}</p>}{candidate && <div className="mt-5 overflow-hidden rounded-2xl border border-[#e2ddd4] bg-white"><div onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} className="cursor-grab touch-pan-y select-none p-5 active:cursor-grabbing" style={{ transform: `translateX(${dragX}px) rotate(${dragX / 22}deg)`, transition: pointerStart.current === null ? 'transform 160ms ease' : 'none' }}><div className="flex items-center justify-between gap-3"><span className="rounded-full bg-[#eae3f2] px-3 py-1 text-xs font-bold text-[#6f5b8d]">{candidate.category}</span><span className="text-sm font-semibold text-[#52635e]">{candidate.vote_score > 0 ? '+' : ''}{candidate.vote_score} votes</span></div><h4 className="mt-5 font-serif text-3xl tracking-[-.04em] text-[#263230]">{candidate.name}</h4><p className="mt-2 text-sm text-[#6d7974]">{candidate.address || 'Location to be confirmed'}</p><div className="mt-5 flex items-center justify-between text-xs font-semibold text-[#89938e]"><span>{candidate.submitted_by ? `Added by ${candidate.submitted_by}` : 'Shared pool'}</span><span>{candidate.scheduled ? 'On itinerary' : 'In the pool'}</span></div></div><div className="grid grid-cols-2 border-t border-[#ece8e0]"><button type="button" onClick={() => vote(-1)} className="px-4 py-3 text-sm font-bold text-[#9a4c3e] hover:bg-[#fff3ee]">← Pass</button><button type="button" onClick={() => vote(1)} className="border-l border-[#ece8e0] px-4 py-3 text-sm font-bold text-[#35574e] hover:bg-[#edf5f0]">Upvote →</button></div></div>}{!loading && displayName && !candidate && !error && <div className="mt-5 rounded-2xl bg-[#edf5f0] p-4 text-sm text-[#35574e]">You have voted on every current group pick. New shared places will appear here automatically.</div>}</section>
}
