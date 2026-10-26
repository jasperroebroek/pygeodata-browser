<script lang="ts">
  import { app, selectEntry, toggleSelectedEntry } from '../lib/stores.svelte';
  import type { TableRow } from '../lib/api';

  const headerRows = $derived(app.payload?.table_rows.filter((r) => r.row_type === 'header') ?? []);

  // Large classes (CountPrediction: 1916 entries) render in chunks on scroll.
  let tableEl: HTMLElement | undefined = $state();
  const CHUNK = 50; // legacy PAGE_ENTRIES
  let renderLimit = $state(CHUNK);
  $effect(() => {
    headerRows;
    renderLimit = CHUNK;
  });
  const visibleRows = $derived(headerRows.slice(0, renderLimit));
  const detailByRecord = $derived.by(() => {
    const map = new Map<string, TableRow[]>();
    for (const row of app.payload?.table_rows ?? []) {
      if (row.row_type === 'detail') {
        const list = map.get(row.record_id) ?? [];
        list.push(row);
        map.set(row.record_id, list);
      }
    }
    return map;
  });

  function maybeLoadMore() {
    if (!tableEl) return;
    if (tableEl.scrollTop + tableEl.clientHeight > tableEl.scrollHeight - 400) {
      renderLimit = Math.min(renderLimit + CHUNK, headerRows.length);
    }
  }

  function specSummary(row: TableRow): string {
    const spec = row.spec;
    if (!spec) return '';
    const parts = [spec.resolution_display ?? spec.resolution, spec.bounds_display].filter(Boolean);
    return parts.join(' · ');
  }
</script>

<section class="table" bind:this={tableEl} onscroll={maybeLoadMore}>
  <div class="rows">
    {#if headerRows.length === 0}
      <div class="empty">
        {#if app.loading}building state…{:else}Select a class on the left.{/if}
      </div>
    {/if}
    {#each visibleRows as row (row.record_id)}
      <div class="group" class:has-details={app.rowDisplay === 'all'}>
        <div class="group-label mono">{row.class_name}</div>
        <button
          class="entry"
          class:focused={row.focused}
          onclick={() => selectEntry(row.record_id)}
        >
          <div class="entry-head">
            {#if app.selectMode}
              <span
                class="check"
                class:checked={app.selectedEntries.includes(row.record_id)}
                role="checkbox"
                aria-checked={app.selectedEntries.includes(row.record_id)}
                tabindex="0"
                onclick={(e) => {
                  e.stopPropagation();
                  toggleSelectedEntry(row.record_id);
                }}
                onkeydown={(e) => e.key === ' ' && toggleSelectedEntry(row.record_id)}
              ></span>
            {/if}
            {#if row.dep_hash_stale || row.format_version_stale || row.source_stale}
              <span class="dot dot--warning" title="stale"></span>
            {/if}
            <span class="hash mono">{row.record_id.slice(0, 12)}</span>
            <span class="spacer"></span>
            <span class="res mono">{specSummary(row)}</span>
          </div>
          {#if row.warnings && row.warnings.length > 0}
            <div class="warnings">{row.warnings.join(', ')}</div>
          {/if}
          {#if app.rowDisplay === 'all'}
            {#each detailByRecord.get(row.record_id) ?? [] as d}
              <div class="param-row">
                <span class="param mono">{d.parameter}</span>
                <span class="value mono">{d.value}</span>
              </div>
            {/each}
          {/if}
        </button>
      </div>
    {/each}
    {#if renderLimit < headerRows.length}
      <div class="more-row">
        <span>Showing {renderLimit} of {headerRows.length} entries</span>
        <button onclick={() => (renderLimit = headerRows.length)}>Show all</button>
      </div>
      <div class="sentinel" data-sentinel></div>
    {/if}
  </div>
</section>

<style>
  .table {
    border-right: 1px solid var(--border);
    background: var(--bg-panel);
    min-height: 0;
    overflow-y: auto;
  }

  .group {
    padding: var(--s-2) var(--s-3) 0;
  }

  .group-label {
    font-size: var(--fs-xs);
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }

  .entry {
    display: flex;
    flex-direction: column;
    gap: 3px;
    width: 100%;
    text-align: left;
    padding: var(--s-2);
    border-radius: var(--r-sm);
    border: 1px solid transparent;
    background: var(--bg-elev);
    box-shadow: var(--shadow-md);
    margin-bottom: 6px;
  }

  .entry:hover {
    border-color: var(--border-strong);
  }

  .entry.focused {
    border-color: var(--accent);
    background: var(--bg-selected);
  }

  .entry-head {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .check {
    width: 14px;
    height: 14px;
    border: 1.5px solid var(--border-strong);
    border-radius: var(--r-xs);
    flex: none;
    background: var(--bg-elev);
  }

  .check.checked {
    background: var(--accent);
    border-color: var(--accent);
  }

  .hash {
    font-size: var(--fs-xs);
    color: var(--text-2);
  }

  .res {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .spacer {
    flex: 1;
  }

  .warnings {
    font-size: var(--fs-xs);
    color: var(--warning);
  }

  .param-row {
    display: flex;
    gap: var(--s-2);
    font-size: var(--fs-xs);
    border-top: 1px solid var(--border);
    padding-top: 2px;
  }

  .param {
    color: var(--text-3);
    flex: none;
    max-width: 40%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .value {
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .more-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s-2);
    padding: var(--s-2);
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .more-row button {
    color: var(--accent-text);
    text-decoration: underline;
  }

  .sentinel {
    height: 1px;
  }

  .empty {
    padding: var(--s-4);
    color: var(--text-3);
    font-size: var(--fs-sm);
    text-align: center;
  }
</style>
