const BASE = '/api'

export async function fetchTours(lat, lon, durationMin) {
  const res = await fetch(`${BASE}/tours?lat=${lat}&lon=${lon}&duration_min=${durationMin}`)
  if (!res.ok) throw new Error('Tour-Generierung fehlgeschlagen')
  return res.json()
}

export async function fetchPOIs(lat, lon, radiusM = 8000) {
  const res = await fetch(`${BASE}/pois?lat=${lat}&lon=${lon}&radius_m=${Math.round(radiusM)}`) 
  if (!res.ok) throw new Error('POI-Abfrage fehlgeschlagen')
  return res.json()
}

export async function fetchWeather(lat, lon) {
  const res = await fetch(`${BASE}/weather?lat=${lat}&lon=${lon}`)
  if (!res.ok) throw new Error('Wetterabfrage fehlgeschlagen')
  return res.json()
}
