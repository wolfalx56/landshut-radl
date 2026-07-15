<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import 'maplibre-gl/dist/maplibre-gl.css'
import * as pmtiles from 'pmtiles'
  import { fetchPOIs } from '../lib/api.js'

  export let userPos = null
  export let selectedTour = null
  export let showOverview = true
  export let activeTour = null
  export let tours = []
  export let centerOnUser = false

  const dispatch = createEventDispatcher()

  const LANDSHUT = [12.1525, 48.5369]
  const MAP_STYLE = '/maps/protomaps-light-style.json'

  // Regionswechsel: merken + Seite neu laden.
  // setStyle() bricht in Safari das WebGL-Rendering (Kacheln laden, aber
  // nichts wird gemalt) -> sauberer Neustart ist zuverlaessiger.
  export async function switchRegion(region) {
    if (!region) return
    // Manuelle Wahl hat Vorrang, sonst wirft die Auto-Wahl sie sofort zurueck.
    sessionStorage.setItem('regionManual', '1')
    saveRegion(region)
    location.reload()
  }

  function saveRegion(region) {
    localStorage.setItem('activeRegion', JSON.stringify({
      name: region.name, file: region.file, lat: region.lat, lon: region.lon,
      bbox: region.bbox, is_home: !!region.is_home,
    }))
  }

  function posInRegion(pos, r) {
    if (!pos || !r || !r.bbox) return false
    const [w, s, e, n] = r.bbox
    return pos.lon >= w && pos.lon <= e && pos.lat >= s && pos.lat <= n
  }

  // Beim Start: passt eine andere geladene Region besser zum Standort als die
  // aktive? Dann merken + neu laden (Karte muss mit der Datei gebaut werden).
  let autoChecked = false
  async function autoPickRegion(pos) {
    if (autoChecked || !pos) return
    autoChecked = true
    if (sessionStorage.getItem('regionManual') === '1') return
    try {
      const { regions } = await fetch('/api/regions').then(r => r.json())
      const match = regions.find(r => posInRegion(pos, r))
      dispatch('coverage', { covered: !!match })
      if (!match) return
      let current = null
      try { current = JSON.parse(localStorage.getItem('activeRegion') || 'null') } catch (e) {}
      if (current && current.file === match.file) return
      saveRegion(match)
      fetch(`/api/regions/${encodeURIComponent(match.name)}/touch`, { method: 'POST' })
      location.reload()
    } catch (e) {
      console.error('Auto-Regionswahl fehlgeschlagen', e)
    }
  }

  let mapContainer
  let map
  let userMarker = null
  let pois = []
  let destMarkers = []

  const POI_COLORS = {
    biergarten: '#f4a261',
    restaurant: '#e76f51',
    werkstatt: '#457b9d',
    wasser: '#48cae4',
    toilette: '#adb5bd',
  }

  onMount(() => {
    async function initMap() {
      if (!mapContainer || mapContainer.clientHeight === 0) {
        requestAnimationFrame(initMap)
        return
      }

      const protocol = new pmtiles.Protocol()
      maplibregl.addProtocol('pmtiles', protocol.tile)

      let saved = null
      try { saved = JSON.parse(localStorage.getItem('activeRegion') || 'null') } catch (e) {}

      // Style erst laden, dann Karte bauen (MapLibre kann kein Promise als style)
      const style = await fetch(MAP_STYLE).then(r => r.json())
      if (saved && saved.file) {
        style.sources.protomaps.url = `pmtiles:///maps/${saved.file}`
      }

      map = new maplibregl.Map({
        container: mapContainer,
        style: style,
        center: saved && saved.lat != null ? [saved.lon, saved.lat]
              : (userPos ? [userPos.lon, userPos.lat] : LANDSHUT),
        zoom: saved && saved.is_home === false ? 12 : 11,
      })

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
      map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right')

      map.on('load', () => {
        map.resize()
        addRouteLayer()
        initPOILayer()
      })

      map.on('error', (e) => {
        const err = e && e.error ? e.error : {}
        const msg = err.message || String(err)
        const url = err.url || (e && e.source && e.source.url) || (e && e.sourceId) || 'keine URL'
        const status = err.status || (err.response && err.response.status) || ''
        console.error('MAP ERROR:', msg, '| STATUS:', status, '| URL:', url, e)
      })
      setTimeout(() => map.resize(), 300)
      window.addEventListener('resize', () => map.resize())
      window.addEventListener('orientationchange', () => setTimeout(() => map.resize(), 300))

      const ro = new ResizeObserver(() => map.resize())
      ro.observe(mapContainer)
    }

    initMap()
  })

  onDestroy(() => map?.remove())

  function addRouteLayer() {
    map.addSource('route', { type: 'geojson', data: emptyGeoJSON() })

    // Schatten für bessere Sichtbarkeit
    map.addLayer({
      id: 'route-shadow',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#000', 'line-width': 7, 'line-opacity': 0.15 },
    })

    map.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#2d6a4f', 'line-width': 5 },
    })
  }

  function initPOILayer() {
    // Layer anlegen, aber leer — wird erst bei aktiver Tour befüllt
    map.addSource('pois', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
    map.addLayer({
      id: 'poi-circles',
      type: 'circle',
      source: 'pois',
      paint: {
        'circle-radius': 8,
        'circle-color': ['match', ['get', 'category'],
          'biergarten', POI_COLORS.biergarten,
          'restaurant', POI_COLORS.restaurant,
          'werkstatt', POI_COLORS.werkstatt,
          'wasser', POI_COLORS.wasser,
          POI_COLORS.toilette
        ],
        'circle-stroke-width': 2,
        'circle-stroke-color': '#fff',
      },
    })

    map.on('click', 'poi-circles', (e) => {
      const p = e.features[0].properties
      new maplibregl.Popup({ offset: 12 })
        .setLngLat(e.lngLat)
        .setHTML(`<strong>${p.icon} ${p.name}</strong>${p.opening_hours ? `<br>🕐 ${p.opening_hours}` : ''}`)
        .addTo(map)
    })
    map.on('mouseenter', 'poi-circles', () => map.getCanvas().style.cursor = 'pointer')
    map.on('mouseleave', 'poi-circles', () => map.getCanvas().style.cursor = '')
  }

  async function loadPOIsForTour(tour) {
    // Mittelpunkt der Route berechnen, Radius = halbe Routenlänge (max 15km)
    const coords = tour.geometry.coordinates
    const mid = coords[Math.floor(coords.length / 2)]
    const radiusM = Math.round(Math.min(tour.distance_km * 400, 15000))
    try {
      const data = await fetchPOIs(mid[1], mid[0], radiusM)
      renderPOIs(data.pois)
      } catch (e) { console.error('POI-Ladefehler:', e) } 
  }
  function clearPOIs() {
    if (map.getSource('pois')) {
      map.getSource('pois').setData({ type: 'FeatureCollection', features: [] })
    }
  }

  function renderPOIs(poisData) {
    const features = poisData.map(p => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: { ...p },
    }))
    if (map.getSource('pois')) {
      map.getSource('pois').setData({ type: 'FeatureCollection', features })
    }
  }

  // Reaktiv: Route anzeigen wenn Tour gewählt
  $: if (map && selectedTour) showRoute(selectedTour)
  $: if (map && !selectedTour) clearRoute()
  $: if (map && userPos) updateUserMarker(userPos)
  $: if (map && userPos) autoPickRegion(userPos)
  // POIs nur bei aktiver Tour (nach "Los!")
  $: if (map && activeTour) loadPOIsForTour(activeTour)
  $: if (map && !activeTour) clearPOIs()
  // Einmalig auf User-Position zentrieren (📍 oder nach "Los!")
  $: if (map && centerOnUser && userPos) {
    map.flyTo({ center: [userPos.lon, userPos.lat], zoom: 14 })
    dispatch('centeredOnUser')
  }
  // Ziel-Pins für die 3 Vorschläge
  $: if (map) updateDestMarkers(tours)

  function showRoute(tour) {
    if (!map.getSource('route')) return
    map.getSource('route').setData(tour.geometry)

    // Karte auf Route zoomen
    const coords = tour.geometry.coordinates
    const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]))
    map.fitBounds(bounds, { padding: 60, maxZoom: 15 })
  }

  function clearRoute() {
    if (map.getSource('route')) {
      map.getSource('route').setData(emptyGeoJSON())
    }
    // Kein flyTo hier: das Statement feuert auch beim Start (selectedTour ist
    // dann null) und wuerde die Karte aus der gewaehlten Region rauswerfen.
  }

  function updateUserMarker(pos) {
    if (userMarker) {
      userMarker.setLngLat([pos.lon, pos.lat])
    } else {
      const el = document.createElement('div')
      el.className = 'user-dot'
      userMarker = new maplibregl.Marker({ element: el })
        .setLngLat([pos.lon, pos.lat])
        .addTo(map)
    }
  }

  function updateDestMarkers(tourList) {
    // Alte Marker entfernen
    destMarkers.forEach(m => m.remove())
    destMarkers = []

    if (!tourList || tourList.length === 0) return

    tourList.forEach((tour, i) => {
      const el = document.createElement('div')
      el.className = 'dest-marker'
      el.textContent = i + 1

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([tour.destination_lon, tour.destination_lat])
        .setPopup(new maplibregl.Popup({ offset: 14 }).setHTML(
          `<strong>${tour.destination}</strong><br>
           <span style="color:#6c757d;font-size:12px">${tour.destination_type} · ${tour.distance_km} km · ~${tour.duration_min} min</span>
           ${tour.destination_website ? `<br><a href="${tour.destination_website}" target="_blank" style="color:#1971c2;font-size:12px">🌐 Website</a>` : ''}`
        ))
        .addTo(map)

      destMarkers.push(marker)
    })
  }

  function emptyGeoJSON() {
    return { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } }
  }
</script>

<div bind:this={mapContainer} class="map"></div>

<!-- GPS-Button -->
<button class="btn-gps" on:click={() => dispatch('locateMe')} title="Mein Standort">
  📍
</button>

<style>
  .map {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .btn-gps {
    position: absolute;
    bottom: calc(150px + env(safe-area-inset-bottom));
    right: 16px;
    z-index: 10;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: none;
    background: white;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    font-size: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  :global(.user-dot) {
    width: 16px;
    height: 16px;
    background: #1a73e8;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 8px rgba(26,115,232,0.5);
  }

  :global(.dest-marker) {
    width: 30px;
    height: 30px;
    background: #2d6a4f;
    color: white;
    border: 2px solid white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    cursor: pointer;
  }
</style>
