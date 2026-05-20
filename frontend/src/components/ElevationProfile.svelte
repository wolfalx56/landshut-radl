<script>
  export let routeGeometry = null

  // Einfaches Höhenprofil aus GeoJSON-Koordinaten
  // OSRM liefert [lon, lat] oder [lon, lat, elevation] — wir zeigen relative Steigung
  $: points = routeGeometry?.coordinates ?? []
  $: hasElevation = points.length > 0 && points[0].length === 3

  $: elevations = hasElevation
    ? points.map(c => c[2])
    : []

  $: minEl = elevations.length ? Math.min(...elevations) : 0
  $: maxEl = elevations.length ? Math.max(...elevations) : 0
  $: range = maxEl - minEl || 1

  const W = 300
  const H = 60

  $: svgPath = (() => {
    if (!elevations.length) return ''
    return elevations.map((el, i) => {
      const x = (i / (elevations.length - 1)) * W
      const y = H - ((el - minEl) / range) * H
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    }).join(' ')
  })()
</script>

{#if hasElevation && svgPath}
  <div class="elevation-wrap">
    <div class="el-labels">
      <span>{maxEl.toFixed(0)} m</span>
      <span>{minEl.toFixed(0)} m</span>
    </div>
    <svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="el-svg">
      <defs>
        <linearGradient id="elGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#2d6a4f" stop-opacity="0.4" />
          <stop offset="100%" stop-color="#2d6a4f" stop-opacity="0.05" />
        </linearGradient>
      </defs>
      <path d="{svgPath} L{W},{H} L0,{H} Z" fill="url(#elGrad)" />
      <path d={svgPath} fill="none" stroke="#2d6a4f" stroke-width="2" />
    </svg>
  </div>
{:else if points.length > 0}
  <!-- OSRM liefert keine Höhe — einfacher Hinweis -->
  <p class="no-elevation">Höhenprofil nach Auswahl verfügbar</p>
{/if}

<style>
  .elevation-wrap {
    margin-top: 10px;
    display: flex;
    gap: 6px;
    align-items: stretch;
  }

  .el-labels {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-size: 10px;
    color: #868e96;
    min-width: 32px;
    text-align: right;
  }

  .el-svg {
    flex: 1;
    height: 60px;
    border-radius: 6px;
    overflow: hidden;
  }

  .no-elevation {
    margin-top: 8px;
    font-size: 12px;
    color: #adb5bd;
  }
</style>
