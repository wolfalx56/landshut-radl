<script>
  import { createEventDispatcher, onMount } from 'svelte'

  export let userPos = null
  export let activeRegion = null

  const dispatch = createEventDispatcher()

  let regions = []
  let maxRegions = 4
  let loading = true
  let error = null
  let newName = ''
  let busy = false
  let progress = ''
  let confirmData = null

  onMount(load)

  async function load() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/regions')
      if (!r.ok) throw new Error('Laden fehlgeschlagen')
      const d = await r.json()
      regions = d.regions
      maxRegions = d.max_regions
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  async function download(confirm = false) {
    if (!newName.trim()) { error = 'Bitte Namen eingeben'; return }
    if (!userPos) { error = 'Kein GPS — Standort unbekannt'; return }
    busy = true; error = null; progress = 'Starte…'
    try {
      const body = { name: newName.trim(), lat: userPos.lat, lon: userPos.lon }
      if (confirm) body.confirm_evict = true
      const r = await fetch('/api/regions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (d.needs_confirm) { confirmData = d.evict_candidate; busy = false; progress = ''; return }
      if (!d.job_id) throw new Error(d.detail || 'Fehler beim Start')
      progress = 'Lädt Karte… (ca. 30 s)'
      await poll(d.job_id)
    } catch (e) {
      error = e.message; busy = false; progress = ''
    }
  }

  async function poll(jobId) {
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const r = await fetch(`/api/regions/status/${jobId}`)
      const d = await r.json()
      if (d.status === 'done') {
        progress = 'Fertig!'
        newName = ''
        confirmData = null
        await load()
        busy = false
        setTimeout(() => progress = '', 1500)
        return
      }
      if (d.status === 'error') {
        error = d.detail || 'Extract fehlgeschlagen'
        busy = false; progress = ''
        return
      }
    }
    error = 'Zeitüberschreitung'; busy = false; progress = ''
  }

  async function pick(region) {
    await fetch(`/api/regions/${encodeURIComponent(region.name)}/touch`, { method: 'POST' })
    dispatch('select', region)
  }

  function inRegion(r) {
    if (!userPos || !r.bbox) return false
    const [w, s, e, n] = r.bbox
    return userPos.lon >= w && userPos.lon <= e && userPos.lat >= s && userPos.lat <= n
  }

  $: covered = regions.some(inRegion)
</script>

<div class="panel">
  <div class="panel-header">
    <span class="panel-title">Karten-Regionen</span>
    <button class="close-btn" on:click={() => dispatch('close')}>✕</button>
  </div>

  {#if userPos && !covered && !loading}
    <div class="hint">
      📍 Für deinen Standort ist keine Karte geladen.
    </div>
  {/if}

  {#if loading}
    <p class="msg">Lade…</p>
  {:else}
    <div class="list">
      {#each regions as r}
        <button class="region" class:active={activeRegion === r.name} on:click={() => pick(r)}>
          <span class="r-name">
            {r.is_home ? '🏠' : '🗺️'} {r.name}
            {#if inRegion(r)}<span class="here">• hier</span>{/if}
          </span>
          <span class="r-size">{r.size_mb} MB</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if confirmData}
    <div class="confirm">
      <p>Speicher voll ({maxRegions} Regionen).</p>
      <p><strong>„{confirmData.name}"</strong> löschen und neue laden?</p>
      <div class="confirm-btns">
        <button class="btn-cancel" on:click={() => confirmData = null}>Abbrechen</button>
        <button class="btn-ok" on:click={() => download(true)}>Löschen & laden</button>
      </div>
    </div>
  {:else}
    <div class="add">
      <input
        placeholder="Name der Region"
        bind:value={newName}
        disabled={busy}
      />
      <button class="btn-load" on:click={() => download(false)} disabled={busy || !userPos}>
        {busy ? '…' : '+ Hier laden'}
      </button>
    </div>
  {/if}

  {#if progress}<p class="msg progress">{progress}</p>{/if}
  {#if error}<p class="msg err">{error}</p>{/if}
</div>

<style>
  .panel {
    position: absolute; bottom: 0; left: 0; right: 0;
    background: #fff; border-radius: 16px 16px 0 0;
    padding: 16px; box-shadow: 0 -2px 16px rgba(0,0,0,.15);
    z-index: 20; max-height: 70vh; overflow-y: auto;
  }
  .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .panel-title { font-size: 18px; font-weight: 600; }
  .close-btn { background: none; border: none; font-size: 20px; cursor: pointer; color: #666; }
  .hint { background: #fff4e0; border: 1px solid #ffd591; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 14px; }
  .list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
  .region {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px; border: 1px solid #e0e0e0; border-radius: 10px;
    background: #fafafa; cursor: pointer; font-size: 15px; text-align: left;
  }
  .region.active { border-color: #2d5a3d; background: #eef5f0; font-weight: 600; }
  .here { color: #2d5a3d; font-size: 13px; }
  .r-size { color: #888; font-size: 13px; }
  .add { display: flex; gap: 8px; }
  .add input { flex: 1; padding: 11px; border: 1px solid #ddd; border-radius: 10px; font-size: 15px; }
  .btn-load { padding: 11px 16px; background: #2d5a3d; color: #fff; border: none; border-radius: 10px; font-size: 15px; cursor: pointer; }
  .btn-load:disabled { opacity: .5; }
  .confirm { background: #fff4f0; border: 1px solid #ffccbc; border-radius: 10px; padding: 12px; }
  .confirm p { margin: 0 0 6px; font-size: 14px; }
  .confirm-btns { display: flex; gap: 8px; margin-top: 10px; }
  .btn-cancel { flex: 1; padding: 10px; border: 1px solid #ddd; background: #fff; border-radius: 8px; cursor: pointer; }
  .btn-ok { flex: 1; padding: 10px; background: #c0392b; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
  .msg { font-size: 14px; margin: 10px 0 0; }
  .progress { color: #2d5a3d; }
  .err { color: #c0392b; }
</style>
