import { useEffect, useMemo, useState } from 'react'
import ActivityModal from '../components/ActivityModal'
import ItineraryTimeline from '../components/ItineraryTimeline'
import MapPanel from '../components/MapPanel'
import PlacesView from '../components/PlacesView'
import TikTokInbox from '../components/TikTokInbox'
import TripHeader from '../components/TripHeader'
import TripSidebar from '../components/TripSidebar'
import TripEditModal from '../components/TripEditModal'
import DeleteActivityModal from '../components/DeleteActivityModal'
import { activityApi, collaborationApi, tripApi } from '../services/api'
import { tripDates } from '../utils/formatters'

export default function TripWorkspacePage({ workspace, displayName, onShare, onGoHome }) {
  const [activeView, setActiveView] = useState('itinerary')
  const [activeDay, setActiveDay] = useState('')
  const [editingActivity, setEditingActivity] = useState(null)
  const [composerOpen, setComposerOpen] = useState(false)
  const [selectedActivity, setSelectedActivity] = useState(null)
  const [tripEditorOpen, setTripEditorOpen] = useState(false)
  const [deletingActivity, setDeletingActivity] = useState(null)
  const [routeSegments, setRouteSegments] = useState([])
  const [members, setMembers] = useState([])
  const { selectedTrip: trip, itinerary, activityPool, itineraryDays } = workspace
  const mappedActivities = useMemo(() => [...itinerary, ...activityPool], [itinerary, activityPool])
  const allTripDays = useMemo(() => tripDates(trip.start_date, trip.end_date), [trip.end_date, trip.start_date])
  const activeDayActivities = useMemo(() => itineraryDays[activeDay] || [], [activeDay, itineraryDays])
  const routeSignature = activeDayActivities.map((activity) => `${activity.id}:${activity.sort_order}:${activity.latitude || ''}:${activity.longitude || ''}`).join('|')

  useEffect(() => { setActiveDay(trip.start_date) }, [trip.id, trip.start_date])
  useEffect(() => {
    let cancelled = false
    collaborationApi.members(trip.id).then((items) => { if (!cancelled) setMembers(items) }).catch(() => { if (!cancelled) setMembers([]) })
    return () => { cancelled = true }
  }, [trip.id])
  useEffect(() => {
    const routeable = activeDayActivities.length > 1 && activeDayActivities.length <= 27 && activeDayActivities.every((activity) => Number.isFinite(Number(activity.latitude)) && Number.isFinite(Number(activity.longitude)))
    if (!routeable) { setRouteSegments([]); return undefined }
    let cancelled = false
    activityApi.routeSegments(trip.id, activeDay).then((segments) => { if (!cancelled) setRouteSegments(segments) }).catch(() => { if (!cancelled) setRouteSegments([]) })
    return () => { cancelled = true }
  }, [activeDay, activeDayActivities, routeSignature, trip.id])

  const openEditor = (activity) => { setEditingActivity(activity); setComposerOpen(true) }
  const save = async (activity) => activity.id ? workspace.updateActivity(activity) : workspace.createActivity(activity)
  const selectActivity = (activity) => { setSelectedActivity(activity) }
  const newActivity = () => { setEditingActivity(null); setComposerOpen(true) }
  const requestDelete = (activity) => setDeletingActivity(activity)
  const exportTrip = async () => {
    try { await tripApi.exportPdf(trip.id) } catch (error) { workspace.clearError(); window.alert(error.message) }
  }
  const confirmDelete = async () => {
    if (!deletingActivity) return
    const deleted = await workspace.deleteActivity(deletingActivity)
    if (deleted) setDeletingActivity(null)
  }

  return <main className="min-h-screen bg-[#f6f3ed] text-[#263230]">
    <TripHeader trip={trip} members={members} trips={workspace.trips} selectedTripId={workspace.selectedTripId} onSelectTrip={workspace.selectTrip} onNewActivity={newActivity} onShare={onShare} onEditTrip={() => setTripEditorOpen(true)} onGoHome={onGoHome} onExport={exportTrip} />
    {workspace.error && <div className="mx-auto max-w-[1600px] px-5 pt-4"><div className="flex items-start justify-between gap-4 rounded-xl bg-[#fff0ed] px-4 py-3 text-sm text-[#9a4c3e]"><p>{workspace.error}</p><button type="button" onClick={workspace.clearError}>×</button></div></div>}
    <div className="mx-auto grid max-w-[1600px] lg:grid-cols-[260px_minmax(0,1fr)]">
      <TripSidebar itineraryDays={itineraryDays} visibleDays={allTripDays} activeView={activeView} setActiveView={setActiveView} activeDay={activeDay} setActiveDay={setActiveDay} onNewActivity={newActivity} />
      <div className={activeView === 'map' ? 'min-w-0 p-5 sm:p-8' : 'min-w-0'}>
        {activeView === 'itinerary' && <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_390px]"><ItineraryTimeline tripId={trip.id} displayName={displayName} itineraryDays={itineraryDays} visibleDays={allTripDays} activeDay={activeDay} setActiveDay={setActiveDay} onNewActivity={newActivity} onEdit={openEditor} onDelete={requestDelete} onReorder={workspace.reorderActivities} placementNotice={workspace.placementNotice} onDismissPlacement={workspace.clearPlacementNotice} onSelectActivity={selectActivity} selectedActivity={selectedActivity} routeSegments={routeSegments} /><div className="hidden py-10 pr-8 xl:block"><div className="sticky top-6"><MapPanel activities={activeDayActivities} routeSegments={routeSegments} selectedActivity={selectedActivity} onSelectActivity={setSelectedActivity} /></div></div></div>}
        {activeView === 'places' && <PlacesView activities={mappedActivities} onEdit={openEditor} onDelete={requestDelete} onSelectActivity={selectActivity} selectedActivity={selectedActivity} />}
        {activeView === 'tiktok' && <TikTokInbox tiktok={workspace.tiktok} setTikTokLink={workspace.setTikTokLink} onMetadata={workspace.retrieveMetadata} onTranscript={workspace.retrieveTranscript} onApprove={workspace.approveCandidate} onReject={workspace.rejectCandidate} />}
        {activeView === 'map' && <div className="mx-auto max-w-6xl"><p className="text-xs font-bold tracking-[.18em] text-[#e0604e]">MAP VIEW</p><h2 className="mt-2 font-serif text-4xl tracking-[-.04em]">See the shape of your day.</h2><p className="mt-2 text-sm text-[#7d8782]">Pins and saved route paths follow the currently selected itinerary day.</p><div className="mt-7"><MapPanel activities={activeDayActivities} routeSegments={routeSegments} selectedActivity={selectedActivity} onSelectActivity={setSelectedActivity} /></div></div>}
      </div>
    </div>
    {composerOpen && <ActivityModal key={editingActivity?.id || `new-${activeDay}`} trip={trip} activity={editingActivity} defaultScheduledDate={activeDay} onClose={() => setComposerOpen(false)} onSave={save} onSearchPlaces={workspace.searchPlaces} submitting={workspace.submitting} />}
    {tripEditorOpen && <TripEditModal trip={trip} onClose={() => setTripEditorOpen(false)} onSave={workspace.updateTrip} submitting={workspace.submitting} />}
    <DeleteActivityModal activity={deletingActivity} onCancel={() => setDeletingActivity(null)} onConfirm={confirmDelete} deleting={workspace.submitting} />
  </main>
}
