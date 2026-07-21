export const emptyTripForm = { name: '', destination_city: '', destination_region: '', start_date: '', end_date: '' }

export function activityFormFor(trip, activity = null, defaultScheduledDate = '') {
  return {
    name: activity?.name || '',
    category: activity?.categories?.join(', ') || activity?.category || '',
    address: activity?.address || '',
    estimated_cost: activity?.estimated_cost || '',
    latitude: activity?.latitude || null,
    longitude: activity?.longitude || null,
    operating_hours: activity?.operating_hours || null,
    scheduled: activity?.scheduled ?? true,
    scheduled_date: activity?.scheduled_date || defaultScheduledDate || trip?.start_date || '',
    scheduled_time: activity?.scheduled_time || '',
  }
}

export function tripDates(startDate, endDate) {
  const dates = []
  if (!startDate || !endDate) return dates
  const cursor = new Date(`${startDate}T00:00:00`)
  const finalDate = new Date(`${endDate}T00:00:00`)
  while (cursor <= finalDate) {
    const year = cursor.getFullYear()
    const month = String(cursor.getMonth() + 1).padStart(2, '0')
    const day = String(cursor.getDate()).padStart(2, '0')
    dates.push(`${year}-${month}-${day}`)
    cursor.setDate(cursor.getDate() + 1)
  }
  return dates
}

export function formatDate(value, options = { weekday: 'long', month: 'short', day: 'numeric' }) {
  return new Intl.DateTimeFormat('en', options).format(new Date(`${value}T00:00:00`))
}

export function formatShortDate(value) {
  return formatDate(value, { weekday: 'short', month: 'short', day: 'numeric' })
}

export function groupByDate(activities) {
  return activities.reduce((groups, activity) => {
    const day = activity.scheduled_date
    groups[day] = [...(groups[day] || []), activity]
    return groups
  }, {})
}

export function formatOperatingHours(value) {
  if (!value) return 'Hours not available'
  try {
    const hours = typeof value === 'string' ? JSON.parse(value) : value
    return hours.weekdayDescriptions?.join(' · ') || 'Hours not available'
  } catch {
    return 'Hours not available'
  }
}

export function formatDistance(meters) {
  if (typeof meters !== 'number') return 'Distance unavailable'
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`
}

export function formatDuration(seconds) {
  if (typeof seconds !== 'number') return 'Travel time unavailable'
  return seconds < 60 ? '< 1 min' : `${Math.round(seconds / 60)} min`
}

export function formatActivityTime(value) {
  if (!value) return ''
  const [hours = '', minutes = ''] = String(value).split(':')
  return hours && minutes ? `${hours}:${minutes}` : String(value)
}

export function formatEstimatedCost(value) {
  const cost = String(value || '').trim()
  if (!cost || /^(free|no cost)$/i.test(cost) || /^[$€£¥₹₩₫₽₺₴₦₱]/u.test(cost)) return cost
  const usdAmount = cost.match(/^USD\s*(.+)$/i)
  return `$${usdAmount ? usdAmount[1] : cost}`
}

export function parseCost(value) {
  if (!value) return 0
  const parsed = Number(String(value).replace(/[^0-9.]/g, ''))
  return Number.isFinite(parsed) ? parsed : 0
}
