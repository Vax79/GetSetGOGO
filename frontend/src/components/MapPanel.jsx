import { useEffect, useMemo, useRef, useState } from 'react'

let googleMapsPromise

function loadGoogleMaps() {
  if (window.google?.maps) return Promise.resolve(window.google.maps)
  if (googleMapsPromise) return googleMapsPromise
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!apiKey) return Promise.reject(new Error('Add VITE_GOOGLE_MAPS_API_KEY to .env and enable Maps JavaScript API.'))
  googleMapsPromise = new Promise((resolve, reject) => {
    const previousAuthFailure = window.gm_authFailure
    window.gm_authFailure = () => {
      window.gm_authFailure = previousAuthFailure
      reject(new Error('Google rejected the Maps key. Enable Maps JavaScript API and allow this site in the key’s referrer restrictions.'))
    }
    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=geometry`
    script.async = true
    script.onload = () => {
      if (window.google?.maps) resolve(window.google.maps)
      else reject(new Error('Google Maps did not initialise. Check the browser key and Maps JavaScript API setting.'))
    }
    script.onerror = () => reject(new Error('Google Maps could not load. Check the browser key and its referrer restrictions.'))
    document.head.appendChild(script)
  })
  return googleMapsPromise
}

export default function MapPanel({ activities, routeSegments = [], selectedActivity, onSelectActivity }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const overlaysRef = useRef([])
  const [mapError, setMapError] = useState('')
  const [emptyNoticeDismissed, setEmptyNoticeDismissed] = useState(false)
  const mappedActivities = useMemo(() => activities.filter((activity) => Number.isFinite(Number(activity.latitude)) && Number.isFinite(Number(activity.longitude))).sort((first, second) => (first.sort_order || 0) - (second.sort_order || 0)), [activities])

  useEffect(() => { setEmptyNoticeDismissed(false) }, [mappedActivities])

  useEffect(() => {
    let cancelled = false
    loadGoogleMaps().then((maps) => {
      if (cancelled || !containerRef.current) return
      setMapError('')
      if (!mapRef.current) mapRef.current = new maps.Map(containerRef.current, { center: { lat: 1.3521, lng: 103.8198 }, zoom: 12, disableDefaultUI: true, zoomControl: true })
      overlaysRef.current.forEach((overlay) => overlay.setMap(null))
      overlaysRef.current = []
      const map = mapRef.current
      const activityPositions = new Map()
      const bounds = new maps.LatLngBounds()
      mappedActivities.forEach((activity, index) => {
        const position = { lat: Number(activity.latitude), lng: Number(activity.longitude) }
        activityPositions.set(activity.id, position)
        bounds.extend(position)
        const marker = new maps.Marker({ map, position, label: { text: String(index + 1), color: '#ffffff', fontWeight: '700' }, title: activity.name, zIndex: selectedActivity?.id === activity.id ? 10 : undefined })
        marker.addListener('click', () => onSelectActivity(activity))
        overlaysRef.current.push(marker)
      })
      routeSegments.forEach((segment) => {
        if (!activityPositions.has(segment.from_activity_id) || !activityPositions.has(segment.to_activity_id)) return
        const path = maps.geometry?.encoding?.decodePath(segment.encoded_polyline)
        if (!path?.length) return
        const polyline = new maps.Polyline({ map, path, strokeColor: '#e0604e', strokeOpacity: 0.82, strokeWeight: 4 })
        overlaysRef.current.push(polyline)
      })
      const selectedPosition = activityPositions.get(selectedActivity?.id)
      if (selectedPosition) { map.panTo(selectedPosition); map.setZoom(Math.max(map.getZoom() || 13, 14)) } else if (mappedActivities.length === 1) { map.setCenter(activityPositions.get(mappedActivities[0].id)); map.setZoom(14) } else if (mappedActivities.length > 1) map.fitBounds(bounds, 48)
    }).catch((error) => { if (!cancelled) setMapError(error.message) })
    return () => { cancelled = true }
  }, [mappedActivities, onSelectActivity, routeSegments, selectedActivity])

  const selected = mappedActivities.find((activity) => activity.id === selectedActivity?.id)
  return <section className="overflow-hidden rounded-3xl border border-[#dedbd3] bg-[#dbe9e4] p-3 shadow-[0_12px_35px_rgba(38,50,48,.06)]"><div className="relative h-[520px]"><div ref={containerRef} className="h-full overflow-hidden rounded-[1.3rem]" aria-label="Google map of the current itinerary day" /><div className="absolute left-2 top-2 rounded-xl bg-white/95 px-3 py-2 text-xs font-bold tracking-[.14em] text-[#52635e] shadow-sm">{mappedActivities.length} DAY STOPS</div>{mapError && <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 rounded-2xl bg-white p-5 text-center shadow-lg"><p className="font-semibold text-[#263230]">Google Maps needs configuration</p><p className="mt-2 text-sm text-[#68716d]">{mapError}</p></div>}{!mapError && mappedActivities.length === 0 && !emptyNoticeDismissed && <div className="absolute inset-x-10 top-1/2 -translate-y-1/2 rounded-2xl bg-white/95 p-5 text-center shadow-lg"><button type="button" onClick={() => setEmptyNoticeDismissed(true)} aria-label="Dismiss no mapped spots message" className="absolute right-3 top-2 grid h-7 w-7 place-items-center rounded-full text-lg text-[#68716d] hover:bg-[#f0eee8]">×</button><p className="font-semibold text-[#263230]">No mapped spots for this day</p><p className="mt-1 text-sm text-[#68716d]">Activities with Google Places coordinates will appear here when scheduled.</p></div>}</div><div className="mt-3 rounded-2xl bg-[#fdfbf7]/95 p-4 shadow-sm">{selected ? <><p className="text-xs font-bold tracking-[.14em] text-[#e0604e]">SELECTED STOP</p><p className="mt-1 font-semibold text-[#263230]">{selected.name}</p><p className="mt-1 truncate text-sm text-[#6d7974]">{selected.address || 'Address unavailable'}</p></> : <><p className="font-semibold text-[#263230]">Follow today’s route</p><p className="mt-1 text-sm text-[#6d7974]">Select a pin or an activity card to connect the itinerary to the map.</p></>}</div></section>
}
