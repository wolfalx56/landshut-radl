<script>
  import { createEventDispatcher } from 'svelte'
  import ElevationProfile from './ElevationProfile.svelte'

  export let tours = []
  export let loading = false
  export let error = null

  const dispatch = createEventDispatcher()

  const DURATIONS = [
    { label: '30 min', value: 30, emoji: '⚡' },
    { label: '1 Stunde', value: 60, emoji: '🌿' },
    { label: '2 Stunden', value: 120, emoji: '🌄' },
    { label: '3+ Stunden', value: 200, emoji: '🏔️' },
  ]

  let selectedDuration = null
  let previewTour = null

  function generate(duration) {
    selectedDuration = duration
    previewTour = null
    dispatch('generate', duration)
  }
</script>

<div class="panel">
  <div class="panel-header">
    <span class="panel-title">Tour planen</span>
    <button class="close-btn" on:click={() => dispatch('close')}>✕</button>
  </div>

  <!-- Dauer wählen -->
  <div class="duration-grid">
    {#each DURATIONS as d}
      <button
        class="duration-btn"
        class:active={selectedDuration === d.value}
        on:click={() => generate(d.value)}
      >
        <span class="d-emoji">{d.emoji}</span>
        <span class="d-label">{d.label}</span>
      </button>
    {/each}
  </div>

  <!-- Lade-Zustand -->
  {#if loading}
    <div class="status">
      <div class="spinner"></div>
      <p>Suche passende Ziele…</p>
    </div>
  {/if}

  <!-- Fehler -->
  {#if error}
    <div class="error-box">⚠️ {error}</div>
  {/if}

  <!-- Tour-Karten -->
  {#if tours.length > 0}
    <div class="tour-list">
      {#each tours as tour}
        <div
          class="tour-card"
          class:selected={previewTour === tour}
          on:click={() => { previewTour = tour; dispatch('select', tour) }}
        >
          <div class="tour-header">
            <span class="tour-dest">{tour.destination}</span>
            <span class="tour-type-badge">{tour.destination_type}</span>
          </div>
          {#if tour.destination_description}
            <p class="tour-description">{tour.destination_description}</p>
          {/if}
          <div class="tour-meta">
            <span>📍 {tour.distance_km} km</span>
            <span>⏱️ ~{tour.duration_min} min</span>
            {#if tour.destination_website}
              <a
                class="tour-website"
                href={tour.destination_website}
                target="_blank"
                rel="noopener"
                on:click|stopPropagation
              >🌐 Website</a>
            {/if}
          </div>
          {#if previewTour === tour}
            <ElevationProfile routeGeometry={tour.geometry} />
            <button class="start-btn" on:click|stopPropagation={() => dispatch('start', tour)}>
              Los! →
            </button>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .panel {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 30;
    background: white;
    border-radius: 20px 20px 0 0;
    box-shadow: 0 -4px 24px rgba(0,0,0,0.15);
    padding: 12px 16px;
    max-height: 52dvh;
    overflow-y: auto;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .panel-title {
    font-size: 18px;
    font-weight: 700;
  }

  .close-btn {
    background: #f1f3f5;
    border: none;
    border-radius: 50%;
    width: 32px;
    height: 32px;
    font-size: 14px;
    cursor: pointer;
  }

  .duration-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 16px;
  }

  .duration-btn {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border: 2px solid #e9ecef;
    border-radius: 14px;
    background: white;
    cursor: pointer;
    transition: all 0.15s;
  }

  .duration-btn.active {
    border-color: #2d6a4f;
    background: #f0faf4;
  }

  .d-emoji { font-size: 20px; }
  .d-label { font-size: 14px; font-weight: 600; color: #495057; }

  .status {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px;
    gap: 12px;
    color: #6c757d;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e9ecef;
    border-top-color: #2d6a4f;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .error-box {
    background: #fff5f5;
    border: 1px solid #ffc9c9;
    border-radius: 10px;
    padding: 12px 16px;
    color: #c92a2a;
    font-size: 14px;
    margin-bottom: 12px;
  }

  .tour-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .tour-card {
    width: 100%;
    text-align: left;
    background: white;
    border: 2px solid #e9ecef;
    border-radius: 14px;
    padding: 14px;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .tour-card.selected {
    border-color: #2d6a4f;
    background: #f0faf4;
  }

  .tour-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .tour-dest {
    font-size: 15px;
    font-weight: 700;
    color: #212529;
  }

  .tour-type-badge {
    font-size: 11px;
    background: #e9ecef;
    color: #495057;
    border-radius: 20px;
    padding: 2px 8px;
  }

  .tour-description {
    font-size: 12px;
    color: #495057;
    margin: 4px 0 6px;
    line-height: 1.4;
  }

  .tour-meta {
    display: flex;
    gap: 12px;
    font-size: 13px;
    color: #6c757d;
    align-items: center;
    flex-wrap: wrap;
  }

  .tour-website {
    color: #1971c2;
    text-decoration: none;
    font-size: 13px;
  }

  .tour-website:hover {
    text-decoration: underline;
  }

  .start-btn {
    margin-top: 12px;
    width: 100%;
    background: #2d6a4f;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 14px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
  }

  .start-btn:active {
    background: #1b4332;
  }
</style>
