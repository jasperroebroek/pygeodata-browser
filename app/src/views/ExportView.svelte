<script lang="ts">
  import ReloadBar from '../components/ReloadBar.svelte';
  import type { TableRow } from '../lib/api';
  import { exportApi } from '../lib/apiExport';
  import { singleEntryUrl, triggerDownload } from '../lib/format';
  import { selection, toggleSelectedEntry } from '../lib/stores.svelte';
  import { toast } from '../lib/toast.svelte';
  import EntryRows from '../components/EntryRows.svelte';

  // ~47 param rows per entry: render in chunks as the card scrolls.
  const RENDER_CHUNK = 50;

  let rows = $state<TableRow[]>([]);
  let renderLimit = $state(RENDER_CHUNK);
  let exporting = $state(false);
  let progress = $state<{ pct: number; label: string } | null>(null);

  const ids = $derived(selection.selectedEntries);
  const count = $derived(ids.length);
  const cart = $derived(new Set(ids));

  // Rows of removed entries drop out locally; only additions need a fetch.
  let fetchedKey = '';
  $effect(() => {
    const wanted = new Set(ids);
    const have = new Set(rows.filter((r) => r.row_type === 'header').map((r) => r.record_id));
    if ([...wanted].every((id) => have.has(id))) {
      if (have.size !== wanted.size) rows = rows.filter((r) => wanted.has(r.record_id));
      return;
    }
    const key = ids.join(',');
    if (key === fetchedKey) return;
    fetchedKey = key;
    exportApi
      .table([...ids])
      .then((res) => {
        if (fetchedKey === key) rows = res.table_rows ?? [];
      })
      .catch((err) => toast(`Failed to load export table: ${err}`));
  });

  const visibleRows = $derived.by(() => {
    const out: TableRow[] = [];
    let seen = 0;
    for (const r of rows) {
      if (r.row_type === 'header' && ++seen > renderLimit) break;
      out.push(r);
    }
    return out;
  });

  function onScroll(e: Event) {
    const el = e.currentTarget as HTMLElement;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 200) renderLimit += RENDER_CHUNK;
  }

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  async function startExport() {
    if (exporting || count === 0) return;
    exporting = true;
    progress = { pct: 0, label: 'Starting…' };
    try {
      const { job_id, total, warnings } = await exportApi.start([...ids], true);
      if (warnings?.length) {
        console.warn('Export skipped some entries:', warnings);
        toast(`Exporting ${total} files — ${warnings.length} entr${warnings.length === 1 ? 'y' : 'ies'} skipped (see console)`);
      }
      while (true) {
        await sleep(500);
        const status = await exportApi.status(job_id);
        if (status.error) throw new Error(status.error);
        progress = { pct: total > 0 ? Math.round((status.done / total) * 100) : 0, label: `${status.done} / ${total} files` };
        if (status.status === 'complete') break;
      }
      progress = { pct: 100, label: 'Done — downloading…' };
      triggerDownload(exportApi.downloadUrl(job_id), 'pygeodata_export.tar');
      setTimeout(() => (progress = null), 2000);
    } catch (err) {
      progress = null;
      toast(`Export failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      exporting = false;
    }
  }
</script>

<div class="view-export">
  <ReloadBar />
  <div class="export-card">
    <div class="export-card-hd">
      <span class="export-card-title">Export</span>
      <span class="export-toolbar-count">{count} entr{count === 1 ? 'y' : 'ies'}</span>
      <span class="main-hd-spacer"></span>
      {#if progress}
        <div class="export-progress">
          <div class="loading-bar-track export-progress-track">
            <div class="loading-bar-fill" style:width="{progress.pct}%"></div>
          </div>
          <span class="export-progress-label">{progress.label}</span>
        </div>
      {/if}
      <button class="act-btn" disabled={count === 0 || exporting} onclick={() => void startExport()}>Download .tar</button>
    </div>
    <div class="export-card-body">
      {#if count === 0}
        <div class="export-empty">No entries selected. Use the <strong>Select</strong> toggle to add entries.</div>
      {:else}
        <div class="table-scroll export-table-scroll" onscroll={onScroll}>
          <table>
            <colgroup>
              <col class="col-indent" />
              <col class="col-group" />
              <col class="col-param" />
              <col class="col-value" />
            </colgroup>
            <thead>
              <tr>
                <th class="col-indent"></th>
                <th class="col-scope">Scope</th>
                <th class="col-param">Parameter</th>
                <th class="col-value">Value</th>
              </tr>
            </thead>
            <EntryRows
              rows={visibleRows}
              inCart={(id) => cart.has(id)}
              onToggleCart={toggleSelectedEntry}
              onDownload={(id) => triggerDownload(singleEntryUrl(id))}
            />
          </table>
        </div>
      {/if}
    </div>
  </div>
</div>
