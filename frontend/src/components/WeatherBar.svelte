<script>
  export let days = []

  const WEEKDAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']

  function dayLabel(dateStr) {
    const d = new Date(dateStr)
    return WEEKDAYS[d.getDay()]
  }
</script>

<div class="weather-bar">
  {#each days as day}
    <div class="day" class:good={day.good_for_cycling}>
      <span class="weekday">{dayLabel(day.date)}</span>
      <span class="icon">{day.icon}</span>
      <span class="temp">{day.temp_max}°</span>
      {#if day.precipitation_mm > 0.5}
        <span class="rain">{day.precipitation_mm.toFixed(0)}mm</span>
      {/if}
    </div>
  {/each}
</div>

<style>
  .weather-bar {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    display: flex;
    gap: 6px;
    background: rgba(255,255,255,0.92);
    border-radius: 16px;
    padding: 8px 14px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.12);
    backdrop-filter: blur(8px);
  }

  .day {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 4px 10px;
    border-radius: 10px;
    min-width: 44px;
  }

  .day.good {
    background: #f0faf4;
  }

  .weekday { font-size: 11px; font-weight: 600; color: #868e96; }
  .icon { font-size: 20px; }
  .temp { font-size: 13px; font-weight: 700; color: #212529; }
  .rain { font-size: 10px; color: #1971c2; }
</style>
