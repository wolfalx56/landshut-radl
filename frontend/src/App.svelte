<script>
  import { onMount } from 'svelte'
  import MapView from './components/MapView.svelte'
  import RoutePanel from './components/RoutePanel.svelte'
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
  let showOverview = true // true = Gesamtansicht, false = Tour-Ansicht
  let activeTour = null  // Tour im Navigations-Modus

  let watchId = null
  let centerOnUser = false
  let gpsBlocked = false

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
    showOverview = false
  }

  function startTour(tour) {
    activeTour = tour
    panelOpen = false
    showOverview = false
    centerOnUser = true  // beim Los! einmalig auf Standort zentrieren
  }

  function backToOverview() {
    showOverview = true
    selectedTour = null
    activeTour = null
  }
</script>

<div class="app">
  <!-- Karte füllt den ganzen Hintergrund -->
  <MapView
    {userPos}
    {selectedTour}
    {showOverview}
    {activeTour}
    {tours}
    {centerOnUser}
    on:locateMe={locateUser}
    on:centeredOnUser={() => centerOnUser = false}
  />

  <!-- GPS-Hinweis wenn Standort nicht verfügbar -->
  {#if gpsBlocked && showOverview}
    <div class="gps-banner">
      📍 Kein GPS — Route startet von Landshut-Mitte
    </div>
  {/if}

  <!-- Wetter-Leiste oben — ausblenden wenn Panel offen -->
  {#if weather && !gpsBlocked && !panelOpen}
    <WeatherBar days={weather.days} />
  {/if}

  <!-- Aktive Tour: Info-Leiste + Zurück-Button -->
  {#if activeTour}
    <div class="tour-bar">
      <button class="btn-back-inline" on:click={backToOverview}>←</button>
      <div class="tour-bar-info">
        <span class="tour-bar-dest">{activeTour.destination}</span>
        <span class="tour-bar-meta">{activeTour.distance_km} km · ~{activeTour.duration_min} min</span>
      </div>
    </div>
  {:else if !showOverview}
    <button class="btn-back" on:click={backToOverview}>
      ← Übersicht
    </button>
  {/if}

  <!-- Floating Action Button: Tour generieren -->
  {#if showOverview && !panelOpen}
    <div class="fab-area">
      <button class="fab" on:click={() => (panelOpen = true)}>
        🚴 Tour planen
      </button>
    </div>
  {/if}

  <!-- Panel: Dauer wählen + Ergebnisse -->
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
</div>

<style>
  .app {
    position: relative;
    width: 100%;
    height: 100vh;
    height: 100dvh; /* iOS 15.4+: echter sichtbarer Bereich ohne Browser-Chrome */
    overflow: hidden;
  }

  .tour-bar {
    position: absolute;
    top: 12px;
    left: 12px;
    right: 12px;
    z-index: 20;
    background: white;
    border-radius: 16px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.18);
  }

  .btn-back-inline {
    background: #f1f3f5;
    border: none;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    font-size: 18px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .tour-bar-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .tour-bar-dest {
    font-size: 15px;
    font-weight: 700;
    color: #212529;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tour-bar-meta {
    font-size: 13px;
    color: #6c757d;
  }

  .btn-back {
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 20;
    background: white;
    border: none;
    border-radius: 24px;
    padding: 10px 18px;
    font-size: 15px;
    font-weight: 600;
    box-shadow: 0 2px 12px rgba(0,0,0,0.18);
    cursor: pointer;
  }

  .fab-area {
    position: absolute;
    bottom: calc(24px + env(safe-area-inset-bottom));
    left: 50%;
    transform: translateX(-50%);
    z-index: 20;
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
</style>
