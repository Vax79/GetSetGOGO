import { formatShortDate } from '../utils/formatters'

const links = [
  ['itinerary', 'Itinerary', '⌁'],
  ['places', 'Places to visit', '⌾'],
  ['tiktok', 'TikTok inbox', '◉'],
  ['map', 'Map', '⌖'],
]

export default function TripSidebar({ itineraryDays, visibleDays, activeView, setActiveView, activeDay, setActiveDay, onNewActivity }) {
  return <aside className="border-r border-[#dedbd3] bg-[#fdfbf7] p-4 lg:min-h-[calc(100vh-142px)] lg:py-7">
    <nav className="grid gap-1">{links.map(([id, label, icon]) => <button key={id} type="button" onClick={() => setActiveView(id)} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-semibold transition ${activeView === id ? 'bg-[#263230] text-white shadow-sm' : 'text-[#5d6965] hover:bg-[#eeece6]'}`}><span className="w-4 text-center text-base">{icon}</span>{label}{id === 'tiktok' && <span className="ml-auto rounded-full bg-[#f4d9cf] px-2 py-0.5 text-[10px] text-[#9a4c3e]">AI</span>}</button>)}</nav>
    <div className="mt-8"><div className="mb-3 flex items-center justify-between px-3"><p className="text-[10px] font-bold tracking-[.18em] text-[#969d99]">ITINERARY</p><button onClick={onNewActivity} className="text-base text-[#e0604e]" type="button" aria-label="Add activity">+</button></div><div className="grid gap-1">{visibleDays.map((date) => <button key={date} type="button" onClick={() => { setActiveDay(date); setActiveView('itinerary') }} className={`flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${activeDay === date && activeView === 'itinerary' ? 'bg-[#e7eee9] text-[#263230]' : 'text-[#68716d] hover:bg-[#eeece6]'}`}><span>{formatShortDate(date)}</span><span className="text-xs text-[#969d99]">{(itineraryDays[date] || []).length}</span></button>)}</div></div>
    <div className="mt-8 rounded-2xl bg-[#e7eee9] p-4"><p className="text-xs font-bold text-[#49635d]">PLAN WITH EASE</p><p className="mt-2 text-sm leading-5 text-[#52635e]">Save interesting places first, then arrange them when the day takes shape.</p></div>
  </aside>
}
