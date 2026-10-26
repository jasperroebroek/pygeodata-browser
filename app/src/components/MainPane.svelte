<script lang="ts">
  import {
    layout,
    loadMoreEntries,
    selectEntry,
    selection,
    tableState,
    toggleSelectedEntry,
  } from '../lib/stores.svelte';
  import { singleEntryUrl, triggerDownload } from '../lib/format';
  import EntryRows from './EntryRows.svelte';
  import TypeBadge from './TypeBadge.svelte';

  let scrollEl: HTMLElement | undefined = $state();

  const headers = $derived(tableState.rows.filter((r) => r.row_type === 'header'));
  const cart = $derived(new Set(selection.selectedEntries));
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
  {#if layout.entriesMode === 'compact'}
    <div class="entry-pill-list" bind:this={scrollEl} onscroll={maybeLoadMore}>
      {#if headers.length === 0}
        <div class="detail-empty">{emptyText}</div>
      {/if}
      {#each headers as r (r.record_id)}
        {@const inC = cart.has(r.record_id)}
        <div
          class="entry-pill"
          class:active={r.record_id === tableState.selectedEntry}
          class:selected-for-export={inC}
          data-entry={r.record_id}
          role="button"
          tabindex="-1"
          onclick={() => void selectEntry(r.record_id, { toggle: true })}
          onkeydown={(e) => e.key === 'Enter' && void selectEntry(r.record_id, { toggle: true })}
        >
          <button
            class="select-icon"
            class:select-icon--in={inC}
            title={inC ? 'Remove from export' : 'Add to export'}
            aria-label={inC ? 'Remove from export' : 'Add to export'}
            onclick={(e) => {
              e.stopPropagation();
              toggleSelectedEntry(r.record_id);
            }}
          ></button>
          <button
            class="dl-icon"
            title="Download this entry"
            aria-label="Download this entry"
            onclick={(e) => {
              e.stopPropagation();
              download(r.record_id);
            }}
          ></button>
          <span class="entry-pill-name"
            >{r.class_name}{#if r.format_version_stale}<span
                class="status-dot status-dot--version"
                title="pygeodata version changed — entry must be regenerated"
              ></span>{:else if r.dep_hash_stale}<span
                class="status-dot status-dot--source"
                title="Dependencies changed — entry may be outdated"
              ></span>{/if}</span
          >
          <span class="entry-pill-right">
            <span class="entry-pill-hash">{r.record_id.slice(0, 6)}</span>
            <TypeBadge type={r.object_type} />
            {#if r.warning_count}<span class="pill-flag pill-flag--warn">{r.warning_count}⚠</span>{/if}
            {#if r.error}<span class="pill-flag pill-flag--err">!</span>{/if}
          </span>
        </div>
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
            onSelect={(id) => void selectEntry(id, { toggle: true })}
            onToggleCart={toggleSelectedEntry}
            onDownload={download}
          />
        {/if}
      </table>
    </div>
  {/if}
</main>
