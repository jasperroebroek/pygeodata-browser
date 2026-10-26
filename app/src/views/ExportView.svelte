<script lang="ts">
  import { app, setSelectedEntries } from '../lib/stores.svelte';
  import { api } from '../lib/api';
  import type { TableRow } from '../lib/api';
  import { exportApi } from '../lib/apiExport';
  import ExportTable from '../components/export/ExportTable.svelte';

  // One entry renders ~47 rows (~15 KB) on the real project; fetching the
  // preview for the whole visible set would be a ~160 MB payload.
  const PREVIEW_FETCH_CAP = 250;
  const RENDER_CHUNK = 50;

  let fallbackIds = $state<string[] | null>(null);
  let rows = $state<TableRow[]>([]);
  let tableError = $state<string | null>(null);
  let loadingTable = $state(false);
  let excluded = $state<Set<string>>(new Set());
  let renderLimit = $state(RENDER_CHUNK);
  let hoverId = $state<string | null>(null);

  let exporting = $state(false);
  let showProgress = $state(false);
  let progressPct = $state(0);
  let progressLabel = $state('');
  let exportError = $state<string | null>(null);
  let warnings = $state<string[]>([]);

  // The cart (Select mode in the entries view) takes priority; without one we
  // fall back to the entries currently visible there.
  const cartActive = $derived(app.selectedEntries.length > 0);
  const baseIds = $derived(
    cartActive
      ? app.selectedEntries
      : (app.payload?.visible_entry_ids?.length ? app.payload.visible_entry_ids : (fallbackIds ?? [])),
  );
  const exportIds = $derived(new Set(baseIds.filter((id) => !excluded.has(id))));
  const count = $derived(exportIds.size);
  const countLabel = $derived(
    cartActive
      ? `${count} selected entr${count === 1 ? 'y' : 'ies'}`
      : `${count} entr${count === 1 ? 'y' : 'ies'}`,
  );
  const selectedEntry = $derived(app.selectedEntry);
  const showCartHint = $derived(!app.selectMode && app.selectedEntries.length === 0);

  const previewRows = $derived.by(() => {
    const out: TableRow[] = [];
    let seen = 0;
    for (const r of rows) {
      if (seen >= renderLimit) break;
      out.push(r);
      if (r.row_type === 'header') seen++;
    }
    return out;
  });

  // Read-only import of the shared stores: when the payload is still null
  // (fresh load), fetch a dashboard snapshot ourselves.
  $effect(() => {
    // With nothing selected the shell requests include_rows:false (fast counts),
    // so fetch the full visible set ourselves — once.
    if (app.payload && (app.payload.visible_entry_ids?.length || cartActive)) return;
    if (fallbackIds !== null) return;
    let cancelled = false;
    api
      .dashboard({ include_rows: true })
      .then((p) => {
        if (!cancelled && Array.isArray(p.visible_entry_ids)) fallbackIds = p.visible_entry_ids;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  });

  // Per-row exclusions belong to the current base set; start fresh when the
  // source flips between the cart and the visible entries.
  let lastSource = '';
  $effect(() => {
    const source = cartActive ? 'cart' : 'visible';
    if (source === lastSource) return;
    lastSource = source;
    excluded = new Set();
  });

  let lastTableKey = '';

  $effect(() => {
    const key = baseIds.join(',');
    if (key === lastTableKey) return;
    lastTableKey = key;
    let cancelled = false;
    loadingTable = true;
    tableError = null;
    exportApi
      .table(baseIds.slice(0, PREVIEW_FETCH_CAP))
      .then((res) => {
        if (cancelled) return;
        rows = res.table_rows ?? [];
        renderLimit = RENDER_CHUNK;
      })
      .catch((err) => {
        if (!cancelled) tableError = String(err);
      })
      .finally(() => {
        if (!cancelled) loadingTable = false;
      });
  });

  function toggleEntry(recordId: string) {
    const next = new Set(excluded);
    if (next.has(recordId)) next.delete(recordId);
    else next.add(recordId);
    excluded = next;
  }

  function triggerDownload(url: string, name: string) {
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
  }

  function downloadSingle(recordId: string) {
    triggerDownload(exportApi.singleUrl(recordId), recordId);
  }

  function onScroll(e: Event) {
    const el = e.currentTarget as HTMLElement;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 300 && renderLimit < rows.length) {
      renderLimit += RENDER_CHUNK * 2;
    }
  }

  function sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async function startExport() {
    if (exporting || count === 0) return;
    exporting = true;
    exportError = null;
    warnings = [];
    showProgress = true;
    progressPct = 0;
    progressLabel = 'Starting…';
    try {
      const res = await exportApi.start([...exportIds], true);
      warnings = res.warnings ?? [];

      while (true) {
        await sleep(500);
        const status = await exportApi.status(res.job_id);
        if (status.error) throw new Error(status.error);
        if (status.status === 'error') throw new Error('export job failed');
        if (status.warnings?.length) warnings = status.warnings;
        progressPct = status.total > 0 ? Math.round((status.done / status.total) * 100) : 0;
        progressLabel = `${status.done} / ${status.total} files`;
        if (status.status === 'complete') break;
      }

      progressPct = 100;
      progressLabel = 'Done — downloading…';
      triggerDownload(exportApi.downloadUrl(res.job_id), 'pygeodata_export.tar');
      await sleep(2000);
    } catch (err) {
      exportError = `Export failed: ${err instanceof Error ? err.message : String(err)}`;
    } finally {
      showProgress = false;
      exporting = false;
    }
  }
</script>

<section class="export-wrap">
  <div class="export-card">
    <div class="export-hd">
      <span class="export-title">Export</span>
      <span class="export-count" class:cart={cartActive}>{countLabel}</span>
      {#if cartActive}
        <button class="clear-btn" onclick={() => setSelectedEntries([])} title="Clear selected entries">
          Clear
        </button>
      {/if}
      {#if showProgress}
        <div class="progress">
          <div class="track">
            <div class="fill" style:width="{progressPct}%"></div>
          </div>
          <span class="progress-label">{progressLabel}</span>
        </div>
      {/if}
      <span class="spacer"></span>
      <button
        class="btn"
        disabled={!selectedEntry || exporting}
        title={selectedEntry ?? 'Select an entry in the entries view'}
        onclick={() => selectedEntry && downloadSingle(selectedEntry)}
      >
        Download selected entry
      </button>
      <button class="btn btn--primary" disabled={count === 0 || exporting} onclick={startExport}>
        Download .tar
      </button>
    </div>

    {#if warnings.length}
      <div class="warnings">
        <div class="warnings-title">
          <span class="dot dot--warning"></span>
          {warnings.length} warning{warnings.length === 1 ? '' : 's'} — these entries were skipped:
        </div>
        <ul>
          {#each warnings as w}
            <li>{w}</li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if exportError}
      <div class="error">{exportError}</div>
    {/if}

    {#if showCartHint}
      <div class="cart-note">
        <span class="dot dot--info"></span>
        Enable Select in the entries view to export a specific subset.
      </div>
    {/if}

    <div class="export-body">
      {#if baseIds.length === 0}
        <div class="empty">
          {#if cartActive}
            No entries selected.
          {:else}
            No visible entries. Select classes in the entries view first — the export will include
            the entries currently visible there.
          {/if}
        </div>
      {:else if count === 0}
        <div class="empty">
          {#if cartActive}
            All selected entries have been removed from this export.
          {:else}
            All visible entries have been removed from this export.
          {/if}
        </div>
      {:else}
        {#if baseIds.length > PREVIEW_FETCH_CAP}
          <div class="preview-note">
            Preview shows the first {PREVIEW_FETCH_CAP} of {baseIds.length}
            {cartActive ? 'selected' : 'visible'} entries — the export includes all {count} included
            entr{count === 1 ? 'y' : 'ies'}.
          </div>
        {/if}
        {#if loadingTable}
          <div class="empty">Loading preview…</div>
        {:else if tableError}
          <div class="error">Failed to load export table: {tableError}</div>
        {:else}
          <div class="table-scroll" onscroll={onScroll}>
            <ExportTable
              rows={previewRows}
              {exportIds}
              {hoverId}
              onToggle={toggleEntry}
              onDownload={downloadSingle}
              onHover={(id) => (hoverId = id)}
            />
          </div>
        {/if}
      {/if}
    </div>
  </div>
</section>

<style>
  .export-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    justify-content: center;
    padding: var(--s-4);
  }

  .export-card {
    width: 100%;
    max-width: 900px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    overflow: hidden;
  }

  .export-hd {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--s-3);
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
    flex: none;
  }

  .export-title {
    font-size: var(--fs-md);
    font-weight: 600;
  }

  .export-count {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .export-count.cart {
    color: var(--accent-text);
    background: var(--accent-soft);
    padding: 1px 8px;
    border-radius: var(--r-full);
  }

  .clear-btn {
    padding: 1px 8px;
    font-size: var(--fs-xs);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-full);
    background: var(--bg-elev);
    color: var(--text-2);
  }

  .clear-btn:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .cart-note {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: var(--s-1) var(--s-3);
    border-bottom: 1px solid var(--border);
    font-size: var(--fs-xs);
    color: var(--text-3);
    background: var(--bg-panel);
  }

  .cart-note .dot--info {
    background: var(--accent);
  }

  .spacer {
    flex: 1;
  }

  .progress {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .track {
    width: 140px;
    height: 4px;
    background: var(--bg-hover);
    border-radius: var(--r-full);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--accent);
    border-radius: var(--r-full);
    transition: width var(--t-med) var(--ease);
  }

  .progress-label {
    font-size: var(--fs-xs);
    color: var(--text-2);
    white-space: nowrap;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    font-size: var(--fs-sm);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text);
    white-space: nowrap;
  }

  .btn:hover:not(:disabled) {
    background: var(--bg-hover);
  }

  .btn:disabled {
    opacity: 0.45;
    cursor: default;
  }

  .btn--primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }

  .btn--primary:hover:not(:disabled) {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: var(--bg);
  }

  .warnings {
    flex: none;
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--border);
    background: var(--accent-softer);
    font-size: var(--fs-xs);
    color: var(--text-2);
  }

  .warnings-title {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--warning);
  }

  .warnings ul {
    margin: var(--s-1) 0 0;
    padding-left: 18px;
  }

  .error {
    flex: none;
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--border);
    font-size: var(--fs-sm);
    color: var(--danger);
  }

  .export-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .preview-note {
    flex: none;
    padding: var(--s-1) var(--s-3);
    border-bottom: 1px solid var(--border);
    font-size: var(--fs-xs);
    color: var(--text-3);
    background: var(--bg-panel);
  }

  .table-scroll {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .empty {
    padding: var(--s-4);
    color: var(--text-3);
    font-size: var(--fs-sm);
    line-height: 1.6;
  }
</style>
