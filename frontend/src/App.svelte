<script>
  import { onMount } from 'svelte'
  import MapView from './components/MapView.svelte'
  import RoutePanel from './components/RoutePanel.svelte'
  import RegionPanel from './components/RegionPanel.svelte'
  import WeatherBar from './components/WeatherBar.svelte'
  import { fetchTours, fetchWeather } from './lib/api.js'

  const LANDSHUT = { lat: 48.5369, lon: 12.1525 }

  let userPos = null
  let tours = []
  let selectedTour = null
  let weather = null
  let loading = false
  let error = null
  let panelOpen = false
  let showOverview = true
  let activeTour = null

  let watchId = null
  let centerOnUser = false
  let regionPanelOpen = false
  let activeRegion = 'Landshut'
  let mapView
  let gpsBlocked = false
  let regionCovered = true   // bis die Auto-Wahl geprueft hat: kein Banner

  onMount(() => {
    startTracking()
    loadWeather(LANDSHUT.lat, LANDSHUT.lon)
    return () => { if (watchId) navigator.geolocation.clearWatch(watchId) }
  })

  function startTracking() {
    if (!navigator.geolocation) {
      userPos = LANDSHUT
      gpsBlocked = true
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userPos = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        gpsBlocked = false
        loadWeather(userPos.lat, userPos.lon)
      },
      () => {
        userPos = LANDSHUT
        gpsBlocked = true
      },
      { timeout: 8000 }
    )
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        userPos = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        gpsBlocked = false
      },
      () => { gpsBlocked = true },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    )
  }

  function locateUser() {
    centerOnUser = true
  }

  async function loadWeather(lat, lon) {
    try {
      weather = await fetchWeather(lat, lon)
    } catch {}
  }

  async function generateTours(durationMin) {
    const pos = userPos || LANDSHUT
    loading = true
    error = null
    tours = []
    selectedTour = null
    panelOpen = true
    try {
      const data = await fetchTours(pos.lat, pos.lon, durationMin)
      tours = data.tours
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function selectTour(tour) {
    selectedTour = tour
  }

  async function startTour(tour) {
    console.log('>>> startTour AUFGERUFEN', tour)
    try {
      const pos = userPos || LANDSHUT
      const response = await fetch('/api/tours/recording/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tour_id: tour.id || tour.destination,
          mode: 'bike',
          start_lat: pos.lat,
          start_lon: pos.lon
        })
      })

      if (!response.ok) throw new Error('Recording start failed')
      const data = await response.json()

      activeTour = tour
      panelOpen = false
      showOverview = false
      centerOnUser = true
    } catch (error) {
      console.error('Start error:', error)
      alert('Tour konnte nicht gestartet werden: ' + error.message)
    }
  }

  function backToOverview() {
    showOverview = true
    selectedTour = null
    activeTour = null
  }
</script>

<div class="app">
  <MapView
    bind:this={mapView}
    {userPos}
    {selectedTour}
    {showOverview}
    {activeTour}
    {tours}
    {centerOnUser}
    on:coverage={(e) => (regionCovered = e.detail.covered)}
    on:locateMe={locateUser}
    on:centeredOnUser={() => centerOnUser = false}
  />

  {#if gpsBlocked && showOverview}
    <div class="gps-banner">
      📍 Kein GPS — Route startet von Landshut-Mitte
    </div>
  {/if}

  {#if !regionCovered && !gpsBlocked && showOverview && !regionPanelOpen}
    <div class="region-banner">
      <span>📍 Keine Karte für deinen Standort</span>
      <button class="region-banner-btn" on:click={() => (regionPanelOpen = true)}>
        Region laden
      </button>
    </div>
  {/if}

  {#if showOverview && !panelOpen && !regionPanelOpen}
    <div class="fab-area">
      <button class="fab" on:click={() => (panelOpen = true)}>
        🚴 Tour planen
      </button>
    </div>
    <button class="region-fab" on:click={() => (regionPanelOpen = true)} title="Karten-Regionen">
      🗺️
    </button>
  {/if}

  {#if regionPanelOpen}
    <RegionPanel
      {userPos}
      {activeRegion}
      on:select={(e) => { activeRegion = e.detail.name; mapView?.switchRegion(e.detail); regionPanelOpen = false }}
      on:close={() => (regionPanelOpen = false)}
    />
  {/if}

  {#if panelOpen}
    <RoutePanel
      {tours}
      {loading}
      {error}
      on:generate={(e) => generateTours(e.detail)}
      on:select={(e) => selectTour(e.detail)}
      on:start={(e) => startTour(e.detail)}
      on:close={() => { panelOpen = false; tours = []; selectedTour = null }}
    />
  {/if}

  {#if activeTour}
    <div class="recording-panel">
      <span class="rec-dot">🔴</span>
      <span class="rec-text">{activeTour.destination}</span>
      <button class="stop-btn" on:click={() => { activeTour = null; panelOpen = true; showOverview = true }}>
        Beenden
      </button>
    </div>
  {/if}
</div>

<style>
  .region-fab {
    position: absolute; right: 12px; bottom: 92px;
    width: 48px; height: 48px; border-radius: 50%;
    background: #fff; border: 1px solid #ddd; font-size: 22px;
    box-shadow: 0 2px 8px rgba(0,0,0,.2); cursor: pointer; z-index: 15;
  }
  .app {
    width: 100%;
    height: 100dvh;
    position: relative;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  .region-banner {
    position: absolute; top: 12px; left: 12px; right: 12px;
    background: #fff4e0; border: 1px solid #ffd591; border-radius: 10px;
    padding: 10px 12px; font-size: 14px; z-index: 16;
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,.12);
  }
  .region-banner-btn {
    background: #2d5a3d; color: #fff; border: none; border-radius: 8px;
    padding: 7px 12px; font-size: 14px; cursor: pointer; white-space: nowrap;
  }
  .gps-banner {
    position: absolute;
    top: 12px;
    left: 12px;
    right: 12px;
    z-index: 20;
    background: rgba(255, 243, 205, 0.95);
    border: 1px solid #ffc107;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
    color: #664d03;
    text-align: center;
    backdrop-filter: blur(8px);
  }

  .fab-area {
    position: absolute;
    bottom: calc(20px + env(safe-area-inset-bottom));
    left: 50%;
    transform: translateX(-50%);
    z-index: 25;
  }

  .fab {
    background: #2d6a4f;
    color: white;
    border: none;
    border-radius: 32px;
    padding: 16px 32px;
    font-size: 17px;
    font-weight: 700;
    box-shadow: 0 4px 20px rgba(45,106,79,0.45);
    cursor: pointer;
    white-space: nowrap;
  }

  .fab:active {
    transform: scale(0.97);
  }

  .recording-panel {
    position: fixed;
    bottom: calc(20px + env(safe-area-inset-bottom));
    right: 20px;
    z-index: 50;
    background: #c92a2a;
    color: white;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 4px 12px rgba(201, 42, 42, 0.3);
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .rec-dot {
    font-size: 16px;
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .rec-text {
    font-weight: 600;
    font-size: 13px;
    min-width: 120px;
  }

  .stop-btn {
    background: white;
    color: #c92a2a;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12px;
    white-space: nowrap;
  }

  .stop-btn:active {
    background: #f1f3f5;
  }
</style>
