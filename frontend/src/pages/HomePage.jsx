import { useState } from 'react'
import { formatDate } from '../utils/formatters'

const cardThemes = [
  ['bg-[#dbe9e4]', 'text-[#49635d]', '●'],
  ['bg-[#f4d9cf]', 'text-[#9a4c3e]', '◆'],
  ['bg-[#e9e5db]', 'text-[#655f4f]', '✦'],
  ['bg-[#eae3f2]', 'text-[#6f5b8d]', '◒'],
]

function tripLength(trip) {
  const start = new Date(`${trip.start_date}T00:00:00`)
  const end = new Date(`${trip.end_date}T00:00:00`)
  return Math.max(1, Math.round((end - start) / 86400000) + 1)
}

function TripCard({ trip, index, onOpen }) {
  const [background, accent, symbol] = cardThemes[index % cardThemes.length]
  const destination = [trip.destination_city, trip.destination_region].filter(Boolean).join(', ') || 'Destination to be decided'
  const days = tripLength(trip)
  return <button type="button" onClick={() => onOpen(trip.id)} className="group flex min-h-52 flex-col rounded-[1.6rem] border border-[#e4e0d8] bg-white p-5 text-left shadow-[0_10px_30px_rgba(38,50,48,.04)] transition hover:-translate-y-1 hover:border-[#b9c6c0] hover:shadow-[0_16px_38px_rgba(38,50,48,.10)]"><div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${background} ${accent} text-lg`}>{symbol}</div><div className="mt-auto"><p className="text-xs font-bold tracking-[.14em] text-[#89938e]">{formatDate(trip.start_date, { month: 'short', day: 'numeric', year: 'numeric' })}</p><h3 className="mt-2 font-serif text-2xl leading-tight tracking-[-.03em] text-[#263230]">{trip.name}</h3><p className="mt-1 text-sm text-[#6f7974]">{destination}</p><div className="mt-4 flex items-center justify-between border-t border-[#eeeae3] pt-3 text-xs font-semibold text-[#68716d]"><span>{days} {days === 1 ? 'day' : 'days'}</span><span className="opacity-0 transition group-hover:opacity-100">Open trip →</span></div></div></button>
}

export default function HomePage({ trips, displayName, userEmail, saveDisplayName, onOpenTrip, onCreateTrip, onJoinTrip, onSignOut }) {
  const [draftName, setDraftName] = useState(displayName)
  const [editingName, setEditingName] = useState(!displayName)
  const submitName = (event) => { event.preventDefault(); saveDisplayName(draftName); setEditingName(false) }
  const greeting = displayName ? `Welcome back, ${displayName}.` : 'Make every trip feel considered.'

  return <main className="min-h-screen bg-[#f6f3ed] px-5 py-7 text-[#263230] sm:px-10 sm:py-10"><div className="mx-auto max-w-7xl"><header className="flex flex-wrap items-center justify-between gap-4"><div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-2xl bg-[#263230] font-serif text-xl text-[#f6b5a7]">J</div><p className="text-xs font-bold tracking-[.22em] text-[#e0604e]">JETSETGO</p></div><div className="flex items-center gap-2"><button type="button" className="rounded-xl border border-[#dedbd3] bg-white px-4 py-2.5 text-sm font-bold text-[#52635e] transition hover:bg-[#f0eee8]" onClick={onJoinTrip}>Join trip</button><button type="button" className="rounded-xl bg-[#263230] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#374744]" onClick={onCreateTrip}>+ New trip</button><button type="button" className="rounded-xl px-3 py-2.5 text-sm font-semibold text-[#68716d] transition hover:bg-[#ebe8e1]" onClick={onSignOut}>Sign out</button></div></header>
    <section className="mt-12 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_360px] lg:items-end"><div><p className="text-xs font-bold tracking-[.18em] text-[#e0604e]">YOUR TRAVEL NOTEBOOK</p><h1 className="mt-4 max-w-3xl font-serif text-5xl leading-[.98] tracking-[-.05em] sm:text-6xl">{greeting}</h1><p className="mt-5 max-w-xl text-base leading-7 text-[#68716d]">Keep the places, routes, and little discoveries that turn a plan into a trip you’ll remember.</p></div><section className="rounded-[1.6rem] bg-[#263230] p-5 text-white shadow-[0_20px_50px_rgba(38,50,48,.14)]"><p className="text-[10px] font-bold tracking-[.2em] text-[#f6b5a7]">YOUR PROFILE</p>{editingName ? <form className="mt-3 flex gap-2" onSubmit={submitName}><input className="min-w-0 border-[#d8d3ca] bg-[#fffdf9] !text-[#263230] placeholder:!text-[#7b8580] focus:border-[#f19b87]" value={draftName} onChange={(event) => setDraftName(event.target.value)} placeholder="Enter your name" maxLength="80" autoFocus /><button className="shrink-0 rounded-xl bg-[#f19b87] px-3 text-sm font-bold text-[#263230]">Save</button></form> : <div className="mt-3 flex items-center justify-between gap-4"><div><p className="font-serif text-2xl">{displayName}</p><p className="mt-1 text-sm text-[#c6d0cb]">{userEmail || 'Email linked to your secure account.'}</p></div><button type="button" onClick={() => setEditingName(true)} className="rounded-lg border border-white/20 px-3 py-2 text-sm font-semibold hover:bg-white/10">Edit</button></div>}<p className="mt-4 text-xs leading-5 text-[#b7c4bf]">This profile is linked to your secure account.</p></section></section>
    <section className="mt-14"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold tracking-[.18em] text-[#71817b]">TRIPS</p><h2 className="mt-2 font-serif text-3xl tracking-[-.04em]">Your plans, all in one place.</h2></div><p className="rounded-full bg-[#e7eee9] px-3 py-1.5 text-sm font-semibold text-[#49635d]">{trips.length} {trips.length === 1 ? 'trip' : 'trips'}</p></div>{trips.length ? <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{trips.map((trip, index) => <TripCard trip={trip} index={index} onOpen={onOpenTrip} key={trip.id} />)}</div> : <div className="mt-6 grid min-h-72 place-items-center rounded-[1.8rem] border border-dashed border-[#c7ceca] bg-[#fbfaf7] p-8 text-center"><div><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#e7eee9] text-xl">✦</div><h3 className="mt-4 font-serif text-2xl">A blank page is a good place to start.</h3><p className="mt-2 max-w-sm text-sm leading-6 text-[#7d8782]">Create your first trip to begin collecting places and shaping your itinerary.</p><button type="button" onClick={onCreateTrip} className="mt-5 rounded-xl bg-[#263230] px-4 py-3 text-sm font-bold text-white">Create a trip</button></div></div>}</section></div></main>
}
