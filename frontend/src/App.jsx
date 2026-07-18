import { useCallback, useEffect, useMemo, useState } from 'react'

const emptyTripForm = { name: '', destination_city: '', destination_region: '', start_date: '', end_date: '' }

// Build the default manual-activity form for the selected trip.
function activityFormFor(trip) {
  return { name: '', category: '', address: '', scheduled: true, scheduled_date: trip?.start_date || '', scheduled_time: '' }
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
            <aside className="rounded-3xl border border-slate-700 bg-slate-900 p-6"><p className="text-sm font-semibold text-sky-300">ADD ACTIVITY</p><h2 className="mt-2 text-xl font-bold">Add it manually</h2><p className="mt-2 text-sm text-slate-400">Place, activity name, and category are required.</p><form className="mt-6 grid gap-4" onSubmit={submitActivity}><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="name" value={activityForm.name} onChange={updateForm(setActivityForm)} required placeholder="Activity name" /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="address" value={activityForm.address} onChange={updateForm(setActivityForm)} required placeholder="Place or address" /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="category" value={activityForm.category} onChange={updateForm(setActivityForm)} required placeholder="Category, e.g. food" /><label className="flex gap-2 text-sm"><input type="checkbox" name="scheduled" checked={activityForm.scheduled} onChange={updateForm(setActivityForm)} /> Add to itinerary now</label>{activityForm.scheduled && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="scheduled_date" value={activityForm.scheduled_date} onChange={updateForm(setActivityForm)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="time" name="scheduled_time" value={activityForm.scheduled_time} onChange={updateForm(setActivityForm)} /></div>}<button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60" disabled={submitting}>{submitting ? 'Saving…' : 'Add activity'}</button></form></aside>
            <div className="grid gap-7"><section className="rounded-3xl border border-slate-700 bg-slate-900 p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-sky-300">ITINERARY</p><h2 className="mt-2 text-xl font-bold">{selectedTrip.name}</h2></div><span className="text-sm text-slate-400">Drag cards to reorder a day</span></div>{Object.keys(itineraryDays).length === 0 ? <p className="mt-6 rounded-2xl border border-dashed border-slate-600 p-5 text-slate-400">Your itinerary is empty. Add your first activity to get started.</p> : <div className="mt-6 grid gap-6">{Object.entries(itineraryDays).map(([day, activities]) => <div key={day}><h3 className="mb-3 font-semibold text-sky-200">{formatDate(day)}</h3><div className="grid gap-3">{activities.map((activity) => <article draggable className="cursor-grab rounded-2xl border border-slate-700 bg-slate-800 p-4 active:cursor-grabbing" key={activity.id} onDragStart={() => setDraggedId(activity.id)} onDragOver={(event) => event.preventDefault()} onDrop={() => dropOnActivity(day, activity.id)}><div className="flex gap-4"><span className="text-sm text-sky-300">{activity.scheduled_time || 'Any time'}</span><div className="min-w-0 flex-1"><p className="font-semibold">{activity.name}</p><p className="mt-1 text-sm text-slate-400">{activity.category} · {activity.address}</p></div><button className="text-sm text-sky-300" type="button" onClick={() => setEditingActivity(activity)}>Edit</button><button className="text-sm text-rose-300" type="button" onClick={() => deleteActivity(activity)}>Delete</button></div></article>)}</div></div>)}</div>}</section>
              <section className="rounded-3xl border border-slate-700 bg-slate-900 p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold text-sky-300">ACTIVITY POOL</p><h2 className="mt-2 text-xl font-bold">Saved for later</h2></div><select className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}><option value="">All categories</option>{categories.map((category) => <option value={category} key={category}>{category}</option>)}</select></div>{activityPool.length === 0 ? <p className="mt-5 text-sm text-slate-400">No unscheduled activities.</p> : <ul className="mt-5 grid gap-3">{activityPool.map((activity) => <li className="flex items-center gap-3 rounded-xl bg-slate-800 p-4" key={activity.id}><div className="min-w-0 flex-1"><p className="font-semibold">{activity.name}</p><p className="text-sm text-slate-400">{activity.category} · {activity.address}</p></div><button className="text-sm text-sky-300" type="button" onClick={() => setEditingActivity(activity)}>Edit</button><button className="text-sm text-rose-300" type="button" onClick={() => deleteActivity(activity)}>Delete</button></li>)}</ul>}</section></div>
          </section>
        )}
        {editingActivity && <div className="fixed inset-0 grid place-items-center bg-slate-950/80 p-6"><form className="w-full max-w-lg rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-2xl" onSubmit={saveActivity}><div className="flex items-center justify-between"><h2 className="text-xl font-bold">Edit activity</h2><button className="text-slate-400" type="button" onClick={() => setEditingActivity(null)}>Close</button></div><div className="mt-5 grid gap-4"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="name" value={editingActivity.name} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="address" value={editingActivity.address || ''} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" name="category" value={editingActivity.category} onChange={updateForm(setEditingActivity)} required /><label className="flex gap-2 text-sm"><input type="checkbox" name="scheduled" checked={editingActivity.scheduled} onChange={updateForm(setEditingActivity)} /> Keep on itinerary</label>{editingActivity.scheduled && <div className="grid gap-3 sm:grid-cols-2"><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="date" name="scheduled_date" value={editingActivity.scheduled_date || selectedTrip.start_date} onChange={updateForm(setEditingActivity)} required /><input className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-3" type="time" name="scheduled_time" value={editingActivity.scheduled_time || ''} onChange={updateForm(setEditingActivity)} /></div>}<button className="rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950" disabled={submitting}>{submitting ? 'Saving…' : 'Save changes'}</button></div></form></div>}
      </div>
    </main>
  )
}

export default App
