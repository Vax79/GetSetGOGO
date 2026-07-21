import { useCallback, useEffect, useMemo, useState } from 'react'
import { activityApi, collaborationApi, setAccessToken, tiktokApi, tripApi } from '../services/api'
import { groupByDate } from '../utils/formatters'

export function useTripWorkspace(displayName = '', enabled = true, accessToken = '') {
  const [trips, setTrips] = useState([])
  const [selectedTripId, setSelectedTripId] = useState(null)
  const [itinerary, setItinerary] = useState([])
  const [activityPool, setActivityPool] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [placementNotice, setPlacementNotice] = useState(null)
  const [tiktok, setTiktok] = useState({ link: '', metadata: null, transcript: null, extraction: null, metadataLoading: false, transcriptLoading: false, extractionLoading: false, savingCandidate: null })

  const selectedTrip = trips.find((trip) => trip.id === selectedTripId) || null
  const itineraryDays = useMemo(() => groupByDate(itinerary), [itinerary])

  const loadActivities = useCallback(async (tripId) => {
    if (!tripId) return
    try {
      const [scheduled, unscheduled] = await Promise.all([activityApi.list(tripId, true), activityApi.list(tripId, false)])
      setItinerary(scheduled)
      setActivityPool(unscheduled)
    } catch (requestError) {
      setError(requestError.message || 'Could not load the itinerary.')
    }
  }, [])

  const loadTrips = useCallback(async () => {
    setLoading(true)
    try {
      const data = await tripApi.list()
      setTrips(data)
      setSelectedTripId((current) => current || data[0]?.id || null)
    } catch {
      setError('The API is unavailable. Start the FastAPI server on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Register the Supabase token before any request effect can load private trips.
  useEffect(() => { setAccessToken(accessToken) }, [accessToken])
  useEffect(() => { if (enabled && accessToken) loadTrips() }, [accessToken, enabled, loadTrips])
  useEffect(() => { loadActivities(selectedTripId) }, [selectedTripId, loadActivities])

  const run = async (work) => {
    setError('')
    setSubmitting(true)
    try {
      return await work()
    } catch (requestError) {
      setError(requestError.message)
      return null
    } finally {
      setSubmitting(false)
    }
  }

  const createTrip = (payload) => run(async () => {
    const trip = await tripApi.create(payload)
    setTrips((current) => [trip, ...current])
    setSelectedTripId(trip.id)
    return trip
  })

  const updateTrip = (payload) => run(async () => {
    if (!selectedTrip) return null
    const trip = await tripApi.update(selectedTrip.id, payload)
    setTrips((current) => current.map((item) => item.id === trip.id ? trip : item))
    return trip
  })

  const createActivity = (form) => run(async () => {
    const payload = { ...form, submitted_by_name: displayName || null, scheduled_date: form.scheduled ? form.scheduled_date : null, scheduled_time: form.scheduled_time || null }
    delete payload.scheduled
    await activityApi.create(selectedTrip.id, payload)
    await loadActivities(selectedTrip.id)
    return true
  })

  const updateActivity = (activity) => run(async () => {
    const { id, ...payload } = activity
    payload.scheduled_date = payload.scheduled ? payload.scheduled_date : null
    payload.scheduled_time = payload.scheduled_time || null
    await activityApi.update(id, payload)
    await loadActivities(selectedTrip.id)
    return true
  })

  const deleteActivity = async (activity) => {
    await run(async () => {
      await activityApi.remove(activity.id)
      await loadActivities(selectedTrip.id)
      return true
    })
  }

  const searchPlaces = async (query) => {
    if (!selectedTrip || !query.trim()) return []
    return activityApi.placeSearch(selectedTrip.id, query.trim())
  }

  const reorderActivities = async (date, reordered) => {
    const previous = itinerary
    setItinerary((current) => current.map((activity) => (activity.scheduled_date === date ? reordered.find((item) => item.id === activity.id) : activity)))
    try {
      await activityApi.reorder(selectedTrip.id, date, reordered.map((activity) => activity.id))
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setItinerary(previous)
      setError(requestError.message)
    }
  }

  const setTikTokLink = (link) => setTiktok((current) => ({ ...current, link, metadata: null, transcript: null, extraction: null }))
  async function extractTikTokActivities(metadata = tiktok.metadata, transcript = tiktok.transcript) {
    if (!metadata?.detected || !metadata.caption) return
    setTiktok((current) => ({ ...current, extractionLoading: true, extraction: null }))
    try {
      const extraction = await tiktokApi.extract(selectedTrip.id, metadata, transcript)
      setTiktok((current) => ({ ...current, extraction }))
    } catch (requestError) {
      setTiktok((current) => ({ ...current, extraction: { activities: [], message: requestError.message } }))
    } finally {
      setTiktok((current) => ({ ...current, extractionLoading: false }))
    }
  }
  const retrieveMetadata = async () => {
    if (!tiktok.link.trim()) return
    setTiktok((current) => ({ ...current, metadataLoading: true, metadata: null }))
    try {
      const metadata = await tiktokApi.metadata(selectedTrip.id, tiktok.link.trim())
      setTiktok((current) => ({ ...current, metadata, transcript: null, extraction: null }))
      if (metadata.detected && metadata.caption) await extractTikTokActivities(metadata, null)
    } catch (requestError) {
      setTiktok((current) => ({ ...current, metadata: { detected: false, message: requestError.message } }))
    } finally {
      setTiktok((current) => ({ ...current, metadataLoading: false }))
    }
  }
  const retrieveTranscript = async () => {
    setTiktok((current) => ({ ...current, transcriptLoading: true, transcript: null }))
    try {
      const transcript = await tiktokApi.transcript(selectedTrip.id, tiktok.link.trim())
      setTiktok((current) => ({ ...current, transcript }))
      if (transcript.detected && tiktok.metadata?.detected) await extractTikTokActivities(tiktok.metadata, transcript)
    } catch (requestError) {
      setTiktok((current) => ({ ...current, transcript: { detected: false, message: requestError.message } }))
    } finally {
      setTiktok((current) => ({ ...current, transcriptLoading: false }))
    }
  }
  const approveCandidate = async (candidate) => {
    setTiktok((current) => ({ ...current, savingCandidate: candidate.activity_name }))
    try {
      const data = await tiktokApi.approve(selectedTrip.id, { ...candidate, submitted_by_name: displayName || null })
      setPlacementNotice(data.placement || null)
      setTiktok((current) => ({ ...current, extraction: { ...current.extraction, activities: current.extraction.activities.filter((item) => item.activity_name !== candidate.activity_name) } }))
      await loadActivities(selectedTrip.id)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setTiktok((current) => ({ ...current, savingCandidate: null }))
    }
  }
  const rejectCandidate = (candidate) => setTiktok((current) => ({ ...current, extraction: { ...current.extraction, activities: current.extraction.activities.filter((item) => `${item.activity_name}-${item.poi_name}` !== `${candidate.activity_name}-${candidate.poi_name}`) } }))

  const joinTrip = (payload) => run(async () => {
    const result = await collaborationApi.join(payload)
    setTrips((current) => current.some((trip) => trip.id === result.trip.id) ? current : [result.trip, ...current])
    setSelectedTripId(result.trip.id)
    await loadActivities(result.trip.id)
    return result
  })

  return { trips, selectedTrip, selectedTripId, selectTrip: setSelectedTripId, itinerary, activityPool, itineraryDays, loading, submitting, error, clearError: () => setError(''), placementNotice, clearPlacementNotice: () => setPlacementNotice(null), createTrip, updateTrip, createActivity, updateActivity, deleteActivity, searchPlaces, reorderActivities, joinTrip, tiktok, setTikTokLink, retrieveMetadata, retrieveTranscript, approveCandidate, rejectCandidate }
}
