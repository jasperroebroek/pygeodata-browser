<script lang="ts">
  import ChevronsDownUp from '@lucide/svelte/icons/chevrons-down-up';
  import Pin from '@lucide/svelte/icons/pin';
  import ChevronsUpDown from '@lucide/svelte/icons/chevrons-up-down';
  import { api, fetchFresh } from '../lib/api';
  import type { EntryDetail, FilePayload, SpecPayload } from '../lib/api';
  import { copyText, openFilePopup, openGraphPopup, openPath, revealPath } from '../lib/actions';
  import { fileTone, isRasterFile } from '../lib/format';
  import { openModal } from '../lib/modal.svelte';
  import { navigateToCodeClass, showWhatChanged } from '../lib/nav.svelte';
  import {
    classesState,
    detailState,
    followServerReload,
    forgetEntry,
    isPinned,
    openEntry,
    selectEntry,
    setPinned,
    tableState,
  } from '../lib/stores.svelte';
  import { toast } from '../lib/toast.svelte';
  import { progressiveSrc } from '../lib/progressive';
  import { zoomable } from '../lib/zoom';
  import AssociatedEntries from './AssociatedEntries.svelte';
  import JsonExplorer, { HIDDEN_JSON_KEYS } from './JsonExplorer.svelte';
  import TypeBadge from './TypeBadge.svelte';

  const detail = $derived(detailState.current);
  const entry = $derived(detail?.selected_entry ?? null);
  const depHash = $derived(entry?.dep_hash ?? null);
  const knownClasses = $derived(new Set(classesState.cards.map((c) => c.class_name)));

  let paramsExpanded = $state({ open: false, seq: 0 });

  function setParamsExpanded(open: boolean) {
    paramsExpanded = { open, seq: paramsExpanded.seq + 1 };
  }
  let coShowAll = $state(false);

  const entryPinned = $derived(!!entry && isPinned(entry.record_id));

  const hasSpec = $derived(
    !!entry && !!(entry.spec.crs || entry.spec.resolution_display || entry.spec.shape || entry.spec.bounds_display),
  );

  const hasVisibleParams = $derived(
    !!entry?.params_tree && Object.keys(entry.params_tree).some((k) => !HIDDEN_JSON_KEYS.has(k)),
  );

  const toCode = (cls: string) => navigateToCodeClass(cls, { depHash });

  function specParts(spec: SpecPayload | null | undefined, resolution: 'display' | 'raw' = 'display'): string[] {
    if (!spec) return [];
    const res = resolution === 'display' ? spec.resolution_display : spec.resolution;
    return [spec.crs, res, spec.shape, spec.bounds_display].filter(Boolean) as string[];
  }

  const srcTitle = $derived(
    !detail
      ? ''
      : detail.loaded
        ? detail.source_stale
          ? 'Live source — reflects current code on disk (changed since last run)'
          : 'Live source — reflects current code on disk'
        : 'Source from registry snapshot (class not loaded)',
  );
  const graphTitle = $derived(
    !detail
      ? ''
      : detail.loaded
        ? detail.source_stale || detail.deps_stale
          ? 'Live dependency graph — reflects current code (changed since last run)'
          : 'Live dependency graph — reflects current code'
        : 'Graph from registry snapshot (class not loaded)',
  );

  const crsUrl = $derived.by(() => {
    const m = entry?.spec.crs?.match(/^(?:EPSG|ESRI):(\d+)$/);
    return m ? `https://epsg.io/${m[1]}` : null;
  });

  // ------------------------------------------------------------------ table preview

  let tableHtml = $state<string | null>(null);
  let tableError = $state(false);

  $effect(() => {
    const path = entry?.table_preview;
    tableHtml = null;
    tableError = false;
    if (!path) return;
    let cancelled = false;
    fetchFresh(api.fileUrl(path))
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      .then((html) => !cancelled && (tableHtml = html))
      .catch(() => !cancelled && (tableError = true));
    return () => {
      cancelled = true;
    };
  });

  async function deleteEntry(e: EntryDetail) {
    if (!confirm('Delete this cache entry from disk? This cannot be undone.')) return;
    try {
      await api.deleteEntry(e.record_id);
      toast('Entry deleted — reloading…');
      forgetEntry(e.record_id);
      await selectEntry(null);
      followServerReload();
    } catch {
      toast('Failed to delete entry');
    }
  }
</script>

{#snippet fileActions(f: FilePayload)}
  {#if !isRasterFile(f.path)}<button class="act-btn" onclick={() => openPath(f.path)}>Open</button>{/if}
  <button class="act-btn" onclick={() => revealPath(f.path)}>Reveal</button>
  <button class="act-btn" onclick={() => copyText(f.path)}>Copy path</button>
{/snippet}

{#snippet fileType(f: FilePayload)}
  <span class="file-type file-type--{fileTone(f.kind)}">{f.kind}</span>
{/snippet}

{#snippet fileRow(f: FilePayload)}
  <div class="entry-file-row" style="margin-top:4px">
    {@render fileType(f)}
    <span class="entry-file-name">{f.label}</span>
    {@render fileActions(f)}
  </div>
{/snippet}

{#snippet entryLink(recordId: string, className: string)}
  <a href="#top" class="link-entry-name" onclick={(ev) => (ev.preventDefault(), void openEntry(recordId, className))}>
    {className}
  </a>
{/snippet}

{#snippet hdSep()}<span class="dcard-hd-sep"></span>{/snippet}

<div class="detail-scroll">
  {#if detail && entry}
    {@const e = entry}

    {#if e.figure_preview}
      {@const path = e.figure_preview}
      <div class="dcard dcard--figure">
        <div class="dcard-hd">
          <div class="dcard-hd-top"><span class="dcard-hd-label">Preview</span></div>
          <div class="dcard-hd-actions"><button class="act-btn" onclick={() => openPath(path)}>Open</button></div>
        </div>
        <div class="dcard-body dcard-body--fig">
          <div class="fig-preview">
            {#key e.record_id}
              <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions (the Open button is the keyboard path) -->
              <img
                class="fig-main"
                src={api.thumbUrl(e.record_id)}
                alt=""
                loading="eager"
                use:progressiveSrc={api.fileUrl(path)}
                use:zoomable
                onclick={() =>
                  openModal('Preview', { kind: 'image', src: api.fileUrl(path), preview: api.thumbUrl(e.record_id) })}
              />
            {/key}
          </div>
        </div>
      </div>
    {/if}

    {#if e.table_preview}
      {@const path = e.table_preview}
      <div class="dcard dcard--table">
        <div class="dcard-hd">
          <div class="dcard-hd-top"><span class="dcard-hd-label">Preview</span></div>
          <div class="dcard-hd-actions">
            <button
              class="act-btn"
              onclick={() => tableHtml && openModal('Preview', { kind: 'html', html: tableHtml, className: 'tbl-preview' })}
            >
              Show
            </button>
            <button class="act-btn" onclick={() => openPath(path)}>Open</button>
          </div>
        </div>
        <div class="dcard-body dcard-body--table">
          {#if tableHtml !== null}
            <div class="tbl-preview">{@html tableHtml}</div>
          {:else}
            <div class="tbl-preview-loading">{tableError ? 'Failed to load preview' : 'Loading…'}</div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Class -->
    <div class="dcard">
      <div class="dcard-hd">
        <div class="dcard-hd-top">
          <span class="dcard-hd-label">Class</span>
          <span class="dcard-hd-title"
            >{detail.class_name}{#if detail.object_type}<span class="dcard-hd-type"><TypeBadge type={detail.object_type} /></span
              >{/if}{#if !detail.loaded || detail.source_stale || detail.deps_stale}<span class="dcard-hd-type"
                >{#if !detail.loaded}<span
                    class="badge badge--sm badge-cache"
                    title="Not loaded in Python registry — Source and Graph reflect registry snapshot">cache-only</span
                  >{/if}{#if detail.source_stale}<span
                    class="badge badge--sm badge-warn"
                    title="Source code changed since last run — Source and Graph reflect current code, not the registry snapshot"
                    >stale</span
                  >{:else if detail.deps_stale}<span
                    class="badge badge--sm badge-deps"
                    title="An upstream dependency changed since last run — Source and Graph reflect current code, not the registry snapshot"
                    >stale</span
                  >{/if}</span
              >{/if}</span
          >
        </div>
        <div class="dcard-hd-actions">
          {#if detail.source_available}
            <button class="act-btn" title={srcTitle} onclick={() => toCode(detail.class_name)}>Source</button>
          {/if}
          {#if detail.graph_available}
            <button class="act-btn" title={graphTitle} onclick={() => openGraphPopup(detail.class_name, detail.class_graph_path)}>
              Graph
            </button>
          {/if}
          {#if detail.class_tree_path}
            {@const tree = detail.class_tree_path}
            <button
              class="act-btn"
              title="View dependency tree JSON"
              onclick={() => openFilePopup(tree, { title: `${detail.class_name} — Tree`, pick: 'tree', depHash })}
            >
              Tree
            </button>
            <button
              class="act-btn"
              title="View nodes JSON"
              onclick={() => openFilePopup(tree, { title: `${detail.class_name} — Nodes`, pick: 'nodes', depHash })}
            >
              Nodes
            </button>
          {/if}
          {#if detail.class_registry_path}
            {@const reg = detail.class_registry_path}
            <button class="act-btn" title="View registry JSON" onclick={() => openFilePopup(reg, { depHash })}>Registry</button>
          {/if}
        </div>
      </div>
      <div class="dcard-body">
        {#each [['Call dependencies', detail.call_dependency_names], ['Inheritance dependencies', detail.inheritance_dependency_names]] as [label, names] (label)}
          <div class="kv-dep-block">
            <div class="spec-kv-label">{label}</div>
            <div class="spec-kv-val">
              {#if names.length}
                {#each names as n, i (n)}<a href="#top" onclick={(ev) => (ev.preventDefault(), toCode(n as string))}>{n}</a
                  >{#if i < names.length - 1},&nbsp;{/if}{/each}
              {:else}
                <span class="kv-nil">None</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Entry -->
    <div class="dcard">
      <div class="dcard-hd">
        <div class="dcard-hd-top">
          <span class="dcard-hd-label">Entry</span
          >{#if e.format_version_stale}<span
              class="badge badge--sm badge-danger"
              title="pygeodata version changed — entry must be regenerated">version</span
            >{:else if e.dep_hash_stale}<span
              class="badge badge--sm badge-warn"
              title="Dependencies changed since this entry was last computed — results may no longer match current code"
              >stale</span
            >{/if}
        </div>
        <div class="dcard-hd-actions">
          {#if e.dep_hash_stale && e.record_id}
            <button class="act-btn" onclick={() => showWhatChanged(e.record_id, e.class_name)}>Show diff</button>
            {@render hdSep()}
          {/if}
          {#if (hasVisibleParams && e.params_path) || e.state_hash_path || e.execution_graph_path}
            {#if hasVisibleParams && e.params_path}
              <button class="act-btn" onclick={() => openFilePopup(e.params_path)}>Params</button>
            {/if}
            {#if e.state_hash_path}<button class="act-btn" onclick={() => openFilePopup(e.state_hash_path)}>Hash</button>{/if}
            {#if e.execution_graph_path}
              <button class="act-btn" onclick={() => openFilePopup(e.execution_graph_path)}>Graph</button>
            {/if}
            {@render hdSep()}
          {/if}
          {#if e.state_hash}
            <button class="act-btn act-btn--mono" title={e.state_hash} onclick={() => copyText(e.state_hash, 'Hash copied')}>
              {e.state_hash.slice(0, 6)}
            </button>
            {@render hdSep()}
          {/if}
          <button
            class="icon-btn icon-btn--sm pin-btn"
            class:active={entryPinned}
            title={entryPinned ? 'Unpin this entry' : 'Pin this entry (kept in the sidebar’s Pinned section)'}
            aria-label={entryPinned ? 'Unpin' : 'Pin'}
            aria-pressed={entryPinned}
            onclick={() =>
              void setPinned({ record_id: e.record_id, class_name: e.class_name, object_type: e.object_type }, !entryPinned)}
          >
            <Pin size={14} fill={entryPinned ? 'currentColor' : 'none'} />
          </button>
          {@render hdSep()}
          <button class="act-btn act-btn--danger" title="Delete this cache entry from disk" onclick={() => deleteEntry(e)}>
            Delete
          </button>
        </div>
      </div>
      <div class="dcard-body dcard-body--entry" class:has-spec={hasSpec}>
        {#if hasSpec}
          <div class="spec-kv-table">
            {#if e.spec.crs}
              <div class="spec-kv-row">
                <span class="spec-kv-label">CRS</span>
                <span class="spec-kv-val">
                  {#if crsUrl}<a class="spec-cell-link" href={crsUrl} target="_blank" rel="noopener">{e.spec.crs}</a>
                  {:else}<span class="kv-val">{e.spec.crs}</span>{/if}
                </span>
              </div>
            {/if}
            {#if e.spec.resolution_display}
              <div class="spec-kv-row">
                <span class="spec-kv-label">Resolution</span>
                <span class="spec-kv-val"><span class="kv-val">{e.spec.resolution_display}</span></span>
              </div>
            {/if}
            {#if e.spec.shape}
              <div class="spec-kv-row">
                <span class="spec-kv-label">Shape</span>
                <span class="spec-kv-val"><span class="kv-val">{e.spec.shape}</span></span>
              </div>
            {/if}
            {#if e.spec.bounds_display}
              {@const bl = e.spec.bounds_latlon}
              <div class="spec-kv-row">
                <span class="spec-kv-label">Bounds</span>
                <span class="spec-kv-val">
                  {#if bl}
                    <button
                      class="act-btn js-bounds-map"
                      onclick={() => openModal(`Bounds — ${e.spec.crs ?? ''}`, { kind: 'bounds', bounds: bl, crs: e.spec.crs ?? '' })}
                    >
                      {e.spec.bounds_display}
                    </button>
                  {:else}
                    <span class="kv-val">{e.spec.bounds_display}</span>
                  {/if}
                </span>
              </div>
            {/if}
          </div>
        {/if}
        {#if e.primary_file}
          {#if hasSpec}<div class="dcard-sep"></div>{/if}
          <div class="entry-file-row">
            {@render fileType(e.primary_file)}
            <span class="entry-file-name" class:entry-file-name--primary={e.sidecar_files.length > 0}>{e.primary_file.label}</span>
            {@render fileActions(e.primary_file)}
          </div>
          {#each e.sidecar_files as f (f.path)}
            <div class="entry-file-row entry-file-row--sidecar">
              {@render fileType(f)}
              <span class="entry-file-name">{f.label}</span>
              {@render fileActions(f)}
            </div>
          {/each}
        {/if}
      </div>
      {#if e.warnings.length}
        <div class="entry-warnings">
          {#each e.warnings as w, i (i)}<div class="entry-warning">⚠ {w}</div>{/each}
        </div>
      {/if}
    </div>

    {#if e.co_outputs.length}
      {@const showToggle = e.co_outputs.some((o) => o.diff_rows.length) && e.co_outputs.some((o) => o.rows.length)}
      <div class="dcard">
        <div class="dcard-hd">
          <div class="dcard-hd-top"><span class="dcard-hd-label">Co-outputs</span></div>
          {#if showToggle}
            <div class="dcard-hd-actions">
              <button class="act-btn" class:active={coShowAll} onclick={() => (coShowAll = !coShowAll)}>
                {coShowAll ? 'Show diff only' : 'Show all params'}
              </button>
            </div>
          {/if}
        </div>
        <div class="dcard-body dcard-body--links">
          {#each e.co_outputs as o (o.record_id)}
            {@const params = coShowAll ? o.rows : o.diff_rows}
            <div class="link-row">
              <div class="link-row-top">
                {@render entryLink(o.record_id, o.class_name)}
                <span class="link-hash" title={o.state_hash ?? ''}>{o.state_hash ? o.state_hash.slice(0, 6) : '—'}</span>
              </div>
              {#if o.primary_file}{@render fileRow(o.primary_file)}{/if}
              {#if params.length}
                <div class="link-params co-params">
                  {#each params as r, i (i)}
                    <div class="link-param-line">
                      <span class="link-param-key">{r.parameter}</span>
                      <span class="link-param-val">{r.value}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if e.same_instance_runs.length}
      <div class="dcard">
        <div class="dcard-hd"><span class="dcard-hd-label">Sibling entries</span></div>
        <div class="dcard-body dcard-body--links">
          {#each e.same_instance_runs as s (s.record_id)}
            <div class="link-row">
              <div class="link-row-top">
                {@render entryLink(s.record_id, s.class_name)}
                <span class="link-spec-right">
                  {#each specParts(s.spec, 'raw') as p, i (i)}<span class="tbl-spec-pill">{p}</span>{/each}
                </span>
              </div>
              {#if s.primary_file}{@render fileRow(s.primary_file)}{/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if e.linked_entries.length}
      <div class="dcard">
        <div class="dcard-hd">
          <span class="dcard-hd-label">Associated entries</span><span class="dcard-hd-meta">{e.linked_entries.length}</span>
        </div>
        <div class="dcard-body">
          <AssociatedEntries
            entries={e.linked_entries}
            {knownClasses}
            onEntry={(hash, cls) => void openEntry(hash, cls)}
            onClass={toCode}
          />
        </div>
      </div>
    {/if}

    {#if (detail.dep_version_siblings ?? []).length > 1}
      {@const versions = detail.dep_version_siblings ?? []}
      <div class="dcard">
        <div class="dcard-hd">
          <span class="dcard-hd-label">Versions</span><span class="dcard-hd-meta">{versions.length}</span>
        </div>
        <div class="dcard-body dcard-body--versions">
          {#each versions as s (s.record_id)}
            {@const parts = specParts(s.spec)}
            <div class="ver-row" class:ver-row--self={s.is_self}>
              <div class="ver-row-main">
                <span class="ver-label">{s.version_label ?? `v? · ${s.dep_hash ? s.dep_hash.slice(0, 8) : '—'}`}</span>
                {#if s.dep_hash_stale}<span class="badge badge--sm badge-warn">stale</span>
                {:else}<span class="badge badge--sm badge-ok">current</span>{/if}
                <span class="ver-spacer"></span>
                <span class="ver-row-right">
                  {#if !s.is_self}<button class="act-btn" onclick={() => void selectEntry(s.record_id)}>Select</button>{/if}
                </span>
              </div>
              {#if parts.length}
                <div class="ver-row-spec">{#each parts as p, i (i)}<span class="tbl-spec-pill">{p}</span>{/each}</div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if hasVisibleParams}
      <div class="dcard dcard--params">
        <div class="dcard-hd">
          <div class="dcard-hd-top"><span class="dcard-hd-label">Parameters</span></div>
          <div class="dcard-hd-actions">
            <button class="icon-btn icon-btn--sm" title="Expand all" onclick={() => setParamsExpanded(true)}>
              <ChevronsUpDown size={15} />
            </button>
            <button class="icon-btn icon-btn--sm" title="Collapse all" onclick={() => setParamsExpanded(false)}>
              <ChevronsDownUp size={15} />
            </button>
          </div>
        </div>
        <div class="dcard-body dcard-body--params">
          {#key `${e.record_id}:${paramsExpanded.seq}`}
            <JsonExplorer data={e.params_tree} {knownClasses} open={paramsExpanded.open} onClass={toCode} />
          {/key}
        </div>
      </div>
    {/if}
  {:else if tableState.selectedClasses.length > 1 && !detailState.loading}
    <div class="detail-empty" style="display:flex;flex-direction:column;gap:10px;align-items:flex-start;padding:16px">
      <span style="color:var(--muted);font-size:12px">{tableState.selectedClasses.length} classes selected</span>
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        {#each tableState.selectedClasses as cn (cn)}<span class="badge badge-neutral">{cn}</span>{/each}
      </div>
      <span style="color:var(--faint);font-size:11px">Select an entry to view details.</span>
    </div>
  {:else if detailState.failed && tableState.selectedEntry}
    {@const rid = tableState.selectedEntry}
    <div class="detail-empty detail-failed">
      Couldn’t load this entry.
      <button class="act-btn" onclick={() => void selectEntry(rid)}>Retry</button>
    </div>
  {:else if !detailState.loading}
    <div class="detail-empty">Select an entry to view details.</div>
  {/if}
</div>
