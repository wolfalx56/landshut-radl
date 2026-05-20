<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import maplibregl from 'maplibre-gl'
  import { fetchPOIs } from '../lib/api.js'

  export let userPos = null
  export let selectedTour = null
  export let showOverview = true
  export let activeTour = null
  export let tours = []
  export let centerOnUser = false

  const dispatch = createEventDispatcher()

  const LANDSHUT = [12.1525, 48.5369]
  const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

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
    map = new maplibregl.Map({
      container: mapContainer,
      style: MAP_STYLE,
      center: LANDSHUT,
      zoom: 11,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right')

    map.on('load', () => {
      addRouteLayer()
      initPOILayer()
    })
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
    const radiusM = Math.min(tour.distance_km * 400, 15000)
    try {
      const data = await fetchPOIs(mid[1], mid[0], radiusM)
      renderPOIs(data.pois)
    } catch {}
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
    map.flyTo({ center: userPos ? [userPos.lon, userPos.lat] : LANDSHUT, zoom: 11 })
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
