<script lang="ts">
  import {
    layout,
    loadMoreEntries,
    selectEntry,
    selection,
    tableState,
    toggleSelectedEntry,
  } from '../lib/stores.svelte';
  import { offlineTitle, singleEntryUrl, triggerDownload } from '../lib/format';
  import Download from '@lucide/svelte/icons/download';
  import type { TableRow } from '../lib/api';
  import EntryRows from './EntryRows.svelte';
  import KindIcon from './KindIcon.svelte';
  import OfflineBanner from './OfflineBanner.svelte';
  import PinToggle from './PinToggle.svelte';

  let scrollEl: HTMLElement | undefined = $state();

  const headers = $derived(tableState.rows.filter((r) => r.row_type === 'header'));
  const cart = $derived(new Set(selection.selectedEntries));

  /** Contiguous runs of one class share a label instead of repeating it per row. */
  const groups = $derived.by(() => {
    const out: { className: string; rows: TableRow[] }[] = [];
    for (const r of headers) {
      const last = out[out.length - 1];
      if (last && last.className === r.class_name) last.rows.push(r);
      else out.push({ className: r.class_name, rows: [r] });
    }
    return out;
  });

  function specParts(row: TableRow): string[] {
    const s = row.spec;
    return s ? ([s.crs, s.resolution_display, s.shape, s.bounds_display].filter(Boolean) as string[]) : [];
  }
  const inCart = (id: string) => cart.has(id);
  const download = (id: string) => triggerDownload(singleEntryUrl(id));

  function maybeLoadMore() {
    if (!scrollEl || tableState.fullyLoaded || tableState.loading) return;
    if (scrollEl.scrollTop + scrollEl.clientHeight >= scrollEl.scrollHeight - 200) void loadMoreEntries();
  }

  // Keep filling until the pane scrolls (tall screens, compact pills).
  $effect(() => {
    void tableState.rows.length;
    void tableState.loading;
    queueMicrotask(maybeLoadMore);
  });

  // Keep the focused entry in view (class auto-open, arrow-key walks, back/forward):
  // once per focus change, as soon as its row exists — never on plain page appends.
  let scrolledFor: string | null = null;
  $effect(() => {
    const id = tableState.selectedEntry;
    void tableState.rows;
    if (!id || id === scrolledFor || !scrollEl) return;
    const el = scrollEl.querySelector(`.row-entry[data-entry="${CSS.escape(id)}"], .entry-pill[data-entry="${CSS.escape(id)}"]`);
    if (!el) return;
    scrolledFor = id;
    el.scrollIntoView({ block: 'nearest' });
  });

  // New class selection starts at the top.
  $effect(() => {
    void tableState.selectedClasses;
    scrollEl?.scrollTo({ top: 0 });
  });

  const emptyText = $derived(
    tableState.selectedClasses.length === 0
      ? 'Select a class on the left.'
      : tableState.loading
        ? ''
        : 'No entries match the current filters.',
  );
</script>

<main class="main-pane">
  <OfflineBanner />
  {#if layout.entriesMode === 'compact'}
    <div class="entry-pill-list" bind:this={scrollEl} onscroll={maybeLoadMore}>
      {#if headers.length === 0}
        <div class="detail-empty">{emptyText}</div>
      {/if}
      {#each groups as g, gi (gi)}
        <div class="entry-group-hd">
          <KindIcon type={g.rows[0].object_type} size={13} />
          <span class="entry-group-name">{g.className}</span>
        </div>
        {#each g.rows as r (r.record_id)}
          {@const inC = cart.has(r.record_id)}
          <div
            class="entry-pill"
            class:active={r.record_id === tableState.selectedEntry}
            class:selected-for-export={inC}
            data-entry={r.record_id}
            role="button"
            tabindex="-1"
            onclick={() => void selectEntry(r.record_id)}
            onkeydown={(e) => e.key === 'Enter' && void selectEntry(r.record_id)}
          >
            <button
              class="select-icon"
              class:select-icon--in={inC}
              role="checkbox"
              aria-checked={inC}
              title={inC ? 'Remove from export' : 'Add to export'}
              aria-label={inC ? 'Remove from export' : 'Add to export'}
              onclick={(e) => {
                e.stopPropagation();
                toggleSelectedEntry(r.record_id);
              }}
            ></button>
            <span class="entry-pill-hash" title={r.record_id}>{r.record_id.slice(0, 8)}</span>
            {#if r.format_version_stale}
              <span class="pill-flag pill-flag--err" title="pygeodata version changed — entry must be regenerated">version</span>
            {:else if r.dep_hash_stale}
              <span class="pill-flag pill-flag--warn" title="Dependencies changed — entry may be outdated">stale</span>
            {/if}
            {#if r.offline_root}
              <span class="pill-flag pill-flag--off" title={offlineTitle(r.offline_root)}>offline</span>
            {/if}
            <span class="entry-pill-spec">
              {#each specParts(r) as part, j (j)}<span class="tbl-spec-pill">{part}</span>{/each}
            </span>
            <span class="entry-actions">
              <PinToggle entry={r} />
              <button
                class="icon-btn icon-btn--xs entry-dl"
                title={r.offline_root ? 'Unavailable: its cache root is offline' : 'Download this entry'}
                aria-label="Download this entry"
                disabled={!!r.offline_root}
                onclick={(e) => {
                  e.stopPropagation();
                  download(r.record_id);
                }}
              >
                <Download size={13} />
              </button>
            </span>
          </div>
        {/each}
      {/each}
    </div>
  {:else}
    <div class="table-scroll" bind:this={scrollEl} onscroll={maybeLoadMore}>
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
        {#if headers.length === 0}
          <tbody class="table-body">
            <tr><td colspan="4" class="detail-empty" style="padding:14px">{emptyText}</td></tr>
          </tbody>
        {:else}
          <EntryRows
            rows={tableState.rows}
            activeId={tableState.selectedEntry}
            {inCart}
            onSelect={(id) => void selectEntry(id)}
            onToggleCart={toggleSelectedEntry}
            onDownload={download}
          />
        {/if}
      </table>
    </div>
  {/if}
</main>
