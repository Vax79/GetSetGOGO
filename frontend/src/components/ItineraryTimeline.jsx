import { useEffect, useState } from 'react'
import ActivityCard from './ActivityCard'
import VoteDeck from './VoteDeck'
import { formatDate, formatDistance, formatDuration } from '../utils/formatters'

export default function ItineraryTimeline({ tripId, displayName, itineraryDays, visibleDays, activeDay, setActiveDay, onNewActivity, onEdit, onDelete, onReorder, placementNotice, onDismissPlacement, onSelectActivity, selectedActivity, routeSegments = [] }) {
  const days = visibleDays
  const [draggedId, setDraggedId] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)
  const selectedDate = days.includes(activeDay) ? activeDay : days[0]
  const activities = selectedDate ? itineraryDays[selectedDate] || [] : []
  const routesByDestination = new Map(routeSegments.map((segment) => [segment.to_activity_id, segment]))
  useEffect(() => { if (selectedDate && selectedDate !== activeDay) setActiveDay(selectedDate) }, [selectedDate, activeDay, setActiveDay])
  const dropOn = (targetId) => {
    if (!draggedId || draggedId === targetId) return
    const fromIndex = activities.findIndex((item) => item.id === draggedId)
    const toIndex = activities.findIndex((item) => item.id === targetId)
    if (fromIndex < 0 || toIndex < 0) return
    const reordered = [...activities]
    const [moved] = reordered.splice(fromIndex, 1)
    reordered.splice(toIndex, 0, moved)
    onReorder(selectedDate, reordered)
    setDraggedId(null); setDragOverId(null)
  }

  return <section className="mx-auto max-w-4xl px-5 py-7 sm:px-8 sm:py-10"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold tracking-[.18em] text-[#e0604e]">DAILY ITINERARY</p><h2 className="mt-2 font-serif text-4xl tracking-[-.04em] text-[#263230]">Plan one good day at a time.</h2></div><span className="rounded-full bg-[#e7eee9] px-3 py-1.5 text-xs font-semibold text-[#49635d]">Drag cards to reorder</span></div>
    {placementNotice && <div className={`mt-6 flex items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-sm ${placementNotice.scheduled ? 'border-[#b7d2c7] bg-[#edf5f0] text-[#35574e]' : 'border-[#edcf89] bg-[#fff8e7] text-[#796225]'}`}><div><b>Placement update</b><p className="mt-1">{placementNotice.message}</p>{placementNotice.distance_meters != null && <p className="mt-1 text-xs">{formatDistance(placementNotice.distance_meters)} · {formatDuration(placementNotice.travel_duration_seconds)}</p>}</div><button type="button" onClick={onDismissPlacement}>×</button></div>}
    {days.length > 0 && <div className="mt-7 flex flex-wrap gap-2">{days.map((day, index) => <button key={day} type="button" onClick={() => setActiveDay(day)} className={`min-w-28 rounded-2xl border px-4 py-3 text-left transition ${selectedDate === day ? 'border-[#263230] bg-[#263230] text-white' : 'border-[#dedbd3] bg-white text-[#68716d] hover:border-[#9da9a3]'}`}><span className="block text-[10px] font-bold tracking-[.15em] opacity-70">DAY {index + 1}</span><span className="mt-1 block text-sm font-semibold">{formatDate(day, { weekday: 'short', month: 'short', day: 'numeric' })}</span></button>)}</div>}
    {selectedDate ? <><div className="mt-7 flex items-end justify-between"><div><p className="text-sm font-semibold text-[#68716d]">{formatDate(selectedDate)}</p><p className="mt-1 text-sm text-[#969d99]">{activities.length ? 'Travel estimates show the driving time between each stop.' : 'An open day—start with a place you love.'}</p></div>{!activities.length && <button type="button" onClick={onNewActivity} className="rounded-xl bg-[#263230] px-4 py-2.5 text-sm font-bold text-white hover:bg-[#374744]">+ Add a place</button>}</div><div className="mt-6"><VoteDeck tripId={tripId} displayName={displayName} /></div><div className={`mt-7 grid gap-3 ${activities.length ? '' : 'min-h-[360px] place-items-stretch'}`}>{activities.length ? activities.map((activity, index) => { const route = routesByDestination.get(activity.id); return <div key={activity.id}>{index > 0 && <div className="ml-6 flex h-9 items-center gap-3 text-xs text-[#89938e]"><span className="h-full border-l border-dashed border-[#c7ceca]" /><span>{route ? `Drive ${formatDuration(route.duration_seconds)}${route.distance_meters != null ? ` · ${formatDistance(route.distance_meters)}` : ''}` : 'Next stop'}</span></div>}<ActivityCard activity={activity} index={index} draggable dragState={dragOverId === activity.id} onDragStart={() => setDraggedId(activity.id)} onDragEnd={() => { setDraggedId(null); setDragOverId(null) }} onDragEnter={() => setDragOverId(activity.id)} onDrop={() => dropOn(activity.id)} onEdit={onEdit} onDelete={onDelete} onSelect={() => onSelectActivity(activity)} selected={selectedActivity?.id === activity.id} /></div> }) : <section className="grid min-h-[360px] place-items-center rounded-3xl border border-dashed border-[#c7ceca] bg-[#fbfaf7] p-10 text-center"><div><p className="font-serif text-2xl">This day is still open.</p><p className="mt-2 max-w-sm text-sm leading-6 text-[#7d8782]">Add a place when you’re ready and it will appear here in your day’s timeline.</p><button type="button" onClick={onNewActivity} className="mt-5 rounded-xl border border-[#263230] px-4 py-2.5 text-sm font-bold text-[#263230] hover:bg-[#e7eee9]">+ Add the first place</button></div></section>}</div></> : <div className="mt-7 min-h-[360px] rounded-3xl border border-dashed border-[#c7ceca] bg-[#fbfaf7] p-10 text-center"><p className="font-serif text-2xl">Your itinerary is waiting.</p><p className="mt-2 text-sm text-[#7d8782]">Add a place manually, or review a TikTok to create the first stop.</p></div>}
  </section>
}
