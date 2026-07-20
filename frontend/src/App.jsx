import { useCallback, useEffect, useMemo, useState } from 'react'

const emptyTripForm = { name: '', destination_city: '', destination_region: '', start_date: '', end_date: '' }

// Build the default manual-activity form for the selected trip.
function activityFormFor(trip) {
  return { name: '', category: '', address: '', estimated_cost: '', scheduled: true, scheduled_date: trip?.start_date || '', scheduled_time: '' }
}

// Format an ISO date in a compact, readable form for itinerary headings.
function formatDate(value) {
  return new Intl.DateTimeFormat('en', { weekday: 'long', month: 'short', day: 'numeric' }).format(new Date(`${value}T00:00:00`))
}

// Group a flat scheduled-activity list into itinerary days.
function groupByDate(activities) {
  return activities.reduce((groups, activity) => {
    const day = activity.scheduled_date
    groups[day] = [...(groups[day] || []), activity]
    return groups
  }, {})
}

// Render Google Places weekday descriptions from the activity's stored hours JSON.
function formatOperatingHours(value) {
  if (!value) return 'Not provided'
  try {
    const hours = JSON.parse(value)
    return hours.weekdayDescriptions?.join(' · ') || 'Not provided'
  } catch {
    return 'Not provided'
  }
}

// Format routed distance in a compact itinerary-friendly unit.
function formatDistance(meters) {
  if (typeof meters !== 'number') return 'Distance unavailable'
  return meters < 1000 ? `${meters} m away` : `${(meters / 1000).toFixed(1)} km away`
}

// Format Routes API seconds into a concise travel estimate.
function formatDuration(seconds) {
  if (typeof seconds !== 'number') return 'Travel time unavailable'
  return seconds < 60 ? '< 1 min' : `${Math.round(seconds / 60)} min travel`
}

// Display the practical details and AI enrichment saved with an activity.
function ActivitySupportingDetails({ activity }) {
  const enrichment = activity.enrichment_data
  const sections = [
    ['Food & consumption', enrichment?.food_and_consumption],
    ['Visiting information', enrichment?.practical_visiting_information],
    ['Vibe & highlights', enrichment?.vibe_context_highlights],
  ]
  return <div className="mt-3 grid gap-2 text-sm text-slate-300"><p>{activity.category} · {activity.address || 'Location not provided'}</p>{activity.estimated_cost && <p><span className="font-medium text-slate-100">Estimated cost:</span> {activity.estimated_cost}</p>}<p><span className="font-medium text-slate-100">Hours:</span> {formatOperatingHours(activity.operating_hours)}</p>{activity.latitude && activity.longitude && <p><span className="font-medium text-slate-100">Coordinates:</span> {activity.latitude}, {activity.longitude}</p>}{activity.source_url && <a className="w-fit text-sky-300 underline" href={activity.source_url} target="_blank" rel="noreferrer">View source video</a>}{sections.map(([label, section]) => section?.summary && <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-3" key={label}><p className="font-medium text-sky-200">{label}</p><p className="mt-1">{section.summary}</p></div>)}</div>
}

// Render the trip setup and manual-itinerary management experience.
function App() {
  const [trips, setTrips] = useState([])
  const [selectedTripId, setSelectedTripId] = useState(null)
  const [tripForm, setTripForm] = useState(emptyTripForm)
  const [activityForm, setActivityForm] = useState(activityFormFor(null))
  const [itinerary, setItinerary] = useState([])
  const [activityPool, setActivityPool] = useState([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [editingActivity, setEditingActivity] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [draggedId, setDraggedId] = useState(null)
  const [tiktokLink, setTiktokLink] = useState('')
  const [metadataPreview, setMetadataPreview] = useState(null)
  const [metadataLoading, setMetadataLoading] = useState(false)
  const [transcriptPreview, setTranscriptPreview] = useState(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [extractionPreview, setExtractionPreview] = useState(null)
  const [extractionLoading, setExtractionLoading] = useState(false)
  const [savingCandidate, setSavingCandidate] = useState(null)
  const [placementNotice, setPlacementNotice] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)

  const selectedTrip = trips.find((trip) => trip.id === selectedTripId) || null
  const itineraryDays = useMemo(() => groupByDate(itinerary), [itinerary])
  const categories = useMemo(() => [...new Set(activityPool.map((activity) => activity.category))].sort(), [activityPool])

  // Load all trips and choose the newest one when no current selection exists.
  const loadTrips = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/trips')
      if (!response.ok) throw new Error('Could not load trips.')
      const data = await response.json()
      setTrips(data)
      setSelectedTripId((current) => current || data[0]?.id || null)
    } catch {
      setError('The API is unavailable. Start the FastAPI server on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  // Load the scheduled itinerary and unscheduled activity pool for one trip.
  const loadActivities = useCallback(async (tripId) => {
    if (!tripId) return
    try {
      const [itineraryResponse, poolResponse] = await Promise.all([
        fetch(`/api/trips/${tripId}/activities?scheduled=true`),
        fetch(`/api/trips/${tripId}/activities?scheduled=false${categoryFilter ? `&category=${encodeURIComponent(categoryFilter)}` : ''}`),
      ])
      if (!itineraryResponse.ok || !poolResponse.ok) throw new Error('Could not load activities.')
      setItinerary(await itineraryResponse.json())
      setActivityPool(await poolResponse.json())
    } catch {
      setError('Could not load the itinerary. Please try again.')
    }
  }, [categoryFilter])

  // Fetch initial trips when the application is opened.
  useEffect(() => {
    loadTrips()
  }, [])

  // Refresh activity views when the active trip or pool filter changes.
  useEffect(() => {
    loadActivities(selectedTripId)
  }, [selectedTripId, loadActivities])

  // Keep a valid default itinerary date when the selected trip changes.
  useEffect(() => {
    if (selectedTrip) setActivityForm((current) => ({ ...current, scheduled_date: current.scheduled_date || selectedTrip.start_date }))
  }, [selectedTrip])

  // Update a form field without losing other values in that form.
  const updateForm = (setForm) => (event) => {
    const { name, value, type, checked } = event.target
    setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }))
  }

  // Persist a new trip and immediately select it for manual planning.
  const submitTrip = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const response = await fetch('/api/trips', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(tripForm) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not create the trip.')
      setTrips((current) => [data, ...current])
      setSelectedTripId(data.id)
      setTripForm(emptyTripForm)
      setActivityForm(activityFormFor(data))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Create a manual activity, optionally placing it in the selected trip's itinerary.
  const submitActivity = async (event) => {
    event.preventDefault()
    if (!selectedTrip) return
    setError('')
    setSubmitting(true)
    const payload = { ...activityForm, scheduled_date: activityForm.scheduled ? activityForm.scheduled_date : null, scheduled_time: activityForm.scheduled_time || null }
    delete payload.scheduled
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/activities`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not add the activity.')
      setActivityForm(activityFormFor(selectedTrip))
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Request a non-persisted TikTok caption and author preview for the active trip.
  const retrieveTikTokMetadata = async (event) => {
    event.preventDefault()
    if (!selectedTrip || !tiktokLink.trim()) return
    setMetadataLoading(true)
    setMetadataPreview(null)
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/video-metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: tiktokLink.trim() }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not check this TikTok link.')
      setMetadataPreview(data)
      setTranscriptPreview(null)
      setExtractionPreview(null)
    } catch (requestError) {
      setMetadataPreview({ detected: false, message: requestError.message })
    } finally {
      setMetadataLoading(false)
    }
  }

  // Request the complete ScrapeBadger speech-to-text transcript for the attached TikTok link.
  const retrieveTikTokTranscript = async () => {
    if (!selectedTrip || !tiktokLink.trim()) return
    setTranscriptLoading(true)
    setTranscriptPreview(null)
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/video-metadata/transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: tiktokLink.trim() }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not retrieve this video transcript.')
      setTranscriptPreview(data)
    } catch (requestError) {
      setTranscriptPreview({ detected: false, message: requestError.message })
    } finally {
      setTranscriptLoading(false)
    }
  }

  // Use attached TikTok context to generate reviewable Gemini activity/POI candidates.
  const extractTikTokActivities = async () => {
    if (!selectedTrip || !tiktokLink.trim()) return
    setExtractionLoading(true)
    setExtractionPreview(null)
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/activity-extractions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: tiktokLink.trim(), include_transcript: true }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not extract activities.')
      setExtractionPreview(data)
    } catch (requestError) {
      setExtractionPreview({ activities: [], message: requestError.message })
    } finally {
      setExtractionLoading(false)
    }
  }

  // Approve a reviewed candidate as an activity, then refresh the pool.
  const approveExtractedCandidate = async (candidate) => {
    if (!selectedTrip) return
    setSavingCandidate(candidate.activity_name)
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/activity-extractions/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(candidate),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not save this activity.')
      setExtractionPreview((current) => ({ ...current, activities: current.activities.filter((item) => item.activity_name !== candidate.activity_name) }))
      setPlacementNotice(data.placement || null)
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSavingCandidate(null)
    }
  }

  // Reject a non-persisted candidate by removing it from the current review set.
  const rejectExtractedCandidate = (candidate) => {
    setExtractionPreview((current) => ({ ...current, activities: current.activities.filter((item) => `${item.activity_name}-${item.poi_name}` !== `${candidate.activity_name}-${candidate.poi_name}`) }))
  }

  // Save edits to an activity's details and its optional itinerary placement.
  const saveActivity = async (event) => {
    event.preventDefault()
    if (!editingActivity) return
    setSubmitting(true)
    const { id, ...payload } = editingActivity
    payload.scheduled_time = payload.scheduled_time || null
    payload.scheduled_date = payload.scheduled ? payload.scheduled_date : null
    try {
      const response = await fetch(`/api/activities/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not update the activity.')
      setEditingActivity(null)
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Remove an activity from the trip after an explicit browser confirmation.
  const deleteActivity = async (activity) => {
    if (!window.confirm(`Delete “${activity.name}”?`)) return
    try {
      const response = await fetch(`/api/activities/${activity.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Could not delete the activity.')
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  // Persist a new order when an activity is dropped on another item in the same day.
  const dropOnActivity = async (scheduledDate, targetId) => {
    if (!draggedId || draggedId === targetId) return
    const dayActivities = itineraryDays[scheduledDate] || []
    const fromIndex = dayActivities.findIndex((activity) => activity.id === draggedId)
    const targetIndex = dayActivities.findIndex((activity) => activity.id === targetId)
    if (fromIndex < 0 || targetIndex < 0) return
    const reordered = [...dayActivities]
    const [moved] = reordered.splice(fromIndex, 1)
    reordered.splice(targetIndex, 0, moved)
    setItinerary((current) => current.map((activity) => (activity.scheduled_date === scheduledDate ? reordered.find((item) => item.id === activity.id) : activity)))
    setDraggedId(null)
    setDragOverId(null)
    try {
      const response = await fetch(`/api/trips/${selectedTrip.id}/itinerary/${scheduledDate}/order`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ activity_ids: reordered.map((activity) => activity.id) }) })
      if (!response.ok) throw new Error('Could not save the new order.')
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
      await loadActivities(selectedTrip.id)
    }
  }

  if (loading) return <main className="min-h-screen bg-slate-950 p-10 text-slate-300">Loading JetSetGo…</main>

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col gap-4 border-b border-slate-800 pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="text-sm font-semibold tracking-[0.2em] text-sky-300">JETSETGO</p><h1 className="mt-2 text-4xl font-bold tracking-tight">Plan it your way.</h1></div>
          {trips.length > 0 && <label className="grid gap-1 text-sm text-slate-400">Active trip<select className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100" value={selectedTripId || ''} onChange={(event) => setSelectedTripId(Number(event.target.value))}>{trips.map((trip) => <option value={trip.id} key={trip.id}>{trip.name}</option>)}</select></label>}
        </header>
        {error && <p className="mb-6 rounded-xl border border-rose-800 bg-rose-950/50 px-4 py-3 text-sm text-rose-200">{error}</p>}

        {!selectedTrip ? (
          <section className="mx-auto max-w-xl rounded-3xl border border-slate-700 bg-slate-900 p-8 shadow-2xl"><p className="text-sm font-semibold text-sky-300">CREATE A TRIP</p><h2 className="mt-2 text-2xl font-bold">Start with a destination.</h2><form className="mt-7 grid gap-4" onSubmit={submitTrip}><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="name" value={tripForm.name} onChange={updateForm(setTripForm)} required placeholder="Trip name" /><div className="grid gap-4 sm:grid-cols-2"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="destination_city" value={tripForm.destination_city} onChange={updateForm(setTripForm)} placeholder="City" /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="destination_region" value={tripForm.destination_region} onChange={updateForm(setTripForm)} placeholder="Region" /></div><div className="grid gap-4 sm:grid-cols-2"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="start_date" value={tripForm.start_date} onChange={updateForm(setTripForm)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="end_date" value={tripForm.end_date} onChange={updateForm(setTripForm)} required /></div><button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950" disabled={submitting}>{submitting ? 'Creating…' : 'Create trip'}</button></form></section>
        ) : (
          <section className="grid gap-7 xl:grid-cols-[350px_1fr]">
            <aside className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
              <p className="text-sm font-semibold text-sky-300">ADD ACTIVITY</p>
              <h2 className="mt-2 text-xl font-bold">Add it manually</h2>
              <p className="mt-2 text-sm text-slate-400">Place, activity name, and category are required.</p>
              <form className="mt-6 grid gap-4" onSubmit={submitActivity}>
                <input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="name" value={activityForm.name} onChange={updateForm(setActivityForm)} required placeholder="Activity name" />
                <input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="address" value={activityForm.address} onChange={updateForm(setActivityForm)} required placeholder="Place or address" />
                <input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="category" value={activityForm.category} onChange={updateForm(setActivityForm)} required placeholder="Category, e.g. food" />
                <input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="estimated_cost" value={activityForm.estimated_cost} onChange={updateForm(setActivityForm)} placeholder="Estimated cost, optional" />
                <label className="flex gap-2 text-sm"><input type="checkbox" name="scheduled" checked={activityForm.scheduled} onChange={updateForm(setActivityForm)} /> Add to itinerary now</label>
                {activityForm.scheduled && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="scheduled_date" value={activityForm.scheduled_date} onChange={updateForm(setActivityForm)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="time" name="scheduled_time" value={activityForm.scheduled_time} onChange={updateForm(setActivityForm)} /></div>}
                <button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60" disabled={submitting}>{submitting ? 'Saving…' : 'Add activity'}</button>
              </form>
              <div className="mt-8 border-t border-slate-700 pt-6">
                <p className="text-sm font-semibold text-sky-300">TIKTOK LINK</p>
                <p className="mt-2 text-sm text-slate-400">Attach a TikTok, then review Gemini's activity and POI candidates before saving.</p>
                <form className="mt-4 grid gap-3" onSubmit={retrieveTikTokMetadata}>
                  <input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="url" value={tiktokLink} onChange={(event) => setTiktokLink(event.target.value)} required placeholder="https://www.tiktok.com/@creator/video/123..." />
                  <button className="rounded-xl border border-sky-400 px-4 py-3 font-semibold text-sky-300 disabled:opacity-60" disabled={metadataLoading}>{metadataLoading ? 'Checking TikTok…' : 'Attach TikTok link'}</button>
                </form>
                {metadataPreview && <div className={`mt-4 rounded-xl border p-4 text-sm ${metadataPreview.detected ? 'border-emerald-800 bg-emerald-950/30' : 'border-amber-800 bg-amber-950/30'}`}>
                  <p className="font-semibold">{metadataPreview.detected ? 'Metadata detected' : 'Nothing detected'}</p><p className="mt-1 text-slate-300">{metadataPreview.message}</p>
                  {metadataPreview.detected && <><p className="mt-3 leading-6 text-slate-200">{metadataPreview.caption}</p><button className="mt-4 rounded-lg border border-sky-400 px-3 py-2 font-semibold text-sky-300 disabled:opacity-60" type="button" onClick={retrieveTikTokTranscript} disabled={transcriptLoading}>{transcriptLoading ? 'Retrieving transcript…' : 'Retrieve full transcript'}</button><button className="ml-2 mt-4 rounded-lg bg-sky-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-60" type="button" onClick={extractTikTokActivities} disabled={extractionLoading}>{extractionLoading ? 'Extracting…' : 'Extract activities'}</button></>}
                  {transcriptPreview && <div className="mt-4 border-t border-emerald-800 pt-4"><p className="font-semibold">{transcriptPreview.detected ? 'Speech-to-text transcript' : 'Transcript unavailable'}</p><p className="mt-1 text-slate-300">{transcriptPreview.message}</p>{transcriptPreview.detected && <p className="mt-3 max-h-32 overflow-y-auto whitespace-pre-wrap leading-6 text-slate-200">{transcriptPreview.text}</p>}</div>}
                </div>}
                {extractionPreview && <div className="mt-4 rounded-xl border border-violet-800 bg-violet-950/30 p-4 text-sm">
                  <p className="font-semibold">Review extracted activities</p>
                  <p className="mt-1 text-slate-300">{extractionPreview.message}</p>
                  {extractionPreview.activities?.length === 0 && <p className="mt-3 text-slate-400">No new activities are awaiting review.</p>}
                  {extractionPreview.activities?.map((candidate) => <article className="mt-4 rounded-xl border border-violet-800 bg-slate-900/60 p-4" key={`${candidate.activity_name}-${candidate.poi_name}`}>
                    <p className="text-base font-semibold">{candidate.activity_name}</p>
                    <dl className="mt-3 grid gap-2 text-slate-300">
                      <div><dt className="inline font-medium text-slate-100">Category: </dt><dd className="inline">{candidate.category}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Estimated cost: </dt><dd className="inline">{candidate.estimated_cost || 'Not provided'}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Place: </dt><dd className="inline">{candidate.poi_name}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Address: </dt><dd className="inline">{candidate.poi_address || 'Not provided'}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Coordinates: </dt><dd className="inline">{candidate.latitude && candidate.longitude ? `${candidate.latitude}, ${candidate.longitude}` : 'Not resolved'}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Visiting hours: </dt><dd className="inline">{formatOperatingHours(candidate.operating_hours)}</dd></div>
                      <div><dt className="inline font-medium text-slate-100">Source: </dt><dd className="inline"><a className="text-sky-300 underline" href={candidate.source_url} target="_blank" rel="noreferrer">TikTok video</a></dd></div>
                    </dl>
                    <p className={`mt-3 ${candidate.geocoded ? 'text-emerald-300' : 'text-amber-300'}`}>{candidate.geocoded ? 'Google Places location and visiting hours found.' : candidate.geocoding_message || 'Google Places could not resolve this location.'}</p>
                    <div className="mt-4 flex gap-3"><button className="rounded-lg bg-emerald-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-60" type="button" onClick={() => approveExtractedCandidate(candidate)} disabled={savingCandidate === candidate.activity_name}>{savingCandidate === candidate.activity_name ? 'Approving…' : 'Approve activity'}</button><button className="rounded-lg border border-rose-400 px-3 py-2 font-semibold text-rose-200" type="button" onClick={() => rejectExtractedCandidate(candidate)}>Reject</button></div>
                  </article>)}
                </div>}
              </div>
            </aside>
            <div className="grid gap-7">
              {placementNotice && <section className={`rounded-2xl border p-4 text-sm ${placementNotice.scheduled ? 'border-emerald-800 bg-emerald-950/30 text-emerald-100' : 'border-amber-800 bg-amber-950/30 text-amber-100'}`}><p className="font-semibold">Placement result</p><p className="mt-1">{placementNotice.message}</p>{placementNotice.distance_meters != null && <p className="mt-2">{formatDistance(placementNotice.distance_meters)} · {formatDuration(placementNotice.travel_duration_seconds)}</p>}</section>}
              <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-sm font-semibold tracking-wide text-sky-300">ITINERARY</p><h2 className="mt-2 text-xl font-bold">{selectedTrip.name}</h2></div><span className="rounded-full border border-slate-600 px-3 py-1 text-sm text-slate-300">Drag a card onto another to swap its position</span></div>
                {Object.keys(itineraryDays).length === 0 ? <p className="mt-6 rounded-2xl border border-dashed border-slate-600 p-5 text-slate-400">Your itinerary is empty. Approve a geocoded activity to create the first event.</p> : <div className="mt-6 grid gap-7">{Object.entries(itineraryDays).map(([day, activities]) => <div key={day}><h3 className="mb-3 font-semibold text-sky-200">{formatDate(day)}</h3><div className="grid gap-4">{activities.map((activity, index) => <article draggable className={`cursor-grab rounded-2xl border bg-slate-800 p-5 shadow-lg transition ${dragOverId === activity.id ? 'border-sky-300 ring-2 ring-sky-400/50' : 'border-slate-700'} active:cursor-grabbing`} key={activity.id} onDragStart={() => setDraggedId(activity.id)} onDragEnd={() => { setDraggedId(null); setDragOverId(null) }} onDragOver={(event) => event.preventDefault()} onDragEnter={() => setDragOverId(activity.id)} onDrop={() => dropOnActivity(day, activity.id)}><div className="flex items-start gap-4"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-sky-400/15 text-sm font-bold text-sky-200">{index + 1}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{activity.name}</p><span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300">{activity.scheduled_time || 'Any time'}</span></div><ActivitySupportingDetails activity={activity} /></div><div className="flex shrink-0 gap-3"><button className="text-sm text-sky-300" type="button" onClick={() => setEditingActivity(activity)}>Edit</button><button className="text-sm text-rose-300" type="button" onClick={() => deleteActivity(activity)}>Delete</button></div></div></article>)}</div></div>)}</div>}
              </section>
              <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold tracking-wide text-sky-300">ACTIVITY POOL</p><h2 className="mt-2 text-xl font-bold">Saved for later</h2></div><select className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}><option value="">All categories</option>{categories.map((category) => <option value={category} key={category}>{category}</option>)}</select></div>{activityPool.length === 0 ? <p className="mt-5 text-sm text-slate-400">No unscheduled activities.</p> : <ul className="mt-5 grid gap-4">{activityPool.map((activity) => <li className="rounded-2xl border border-slate-700 bg-slate-800 p-5" key={activity.id}><div className="flex items-start gap-4"><div className="min-w-0 flex-1"><p className="font-semibold">{activity.name}</p><ActivitySupportingDetails activity={activity} /></div><div className="flex shrink-0 gap-3"><button className="text-sm text-sky-300" type="button" onClick={() => setEditingActivity(activity)}>Edit</button><button className="text-sm text-rose-300" type="button" onClick={() => deleteActivity(activity)}>Delete</button></div></div></li>)}</ul>}</section>
            </div>
          </section>
        )}
        {editingActivity && <div className="fixed inset-0 grid place-items-center bg-slate-950/80 p-6"><form className="w-full max-w-lg rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-2xl" onSubmit={saveActivity}><div className="flex items-center justify-between"><h2 className="text-xl font-bold">Edit activity</h2><button className="text-slate-400" type="button" onClick={() => setEditingActivity(null)}>Close</button></div><div className="mt-5 grid gap-4"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="name" value={editingActivity.name} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="address" value={editingActivity.address || ''} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="category" value={editingActivity.category} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="estimated_cost" value={editingActivity.estimated_cost || ''} onChange={updateForm(setEditingActivity)} placeholder="Estimated cost" /><label className="flex gap-2 text-sm"><input type="checkbox" name="scheduled" checked={editingActivity.scheduled} onChange={updateForm(setEditingActivity)} /> Keep on itinerary</label>{editingActivity.scheduled && <div className="grid gap-3 sm:grid-cols-2"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="scheduled_date" value={editingActivity.scheduled_date || selectedTrip.start_date} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="time" name="scheduled_time" value={editingActivity.scheduled_time || ''} onChange={updateForm(setEditingActivity)} /></div>}<button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950" disabled={submitting}>{submitting ? 'Saving…' : 'Save changes'}</button></div></form></div>}
      </div>
    </main>
  )
}

export default App
