<script lang="ts">
  import { api } from '../lib/api';
  import type { DetailPayload, EntryDetail, SpecPayload } from '../lib/api';
  import { app, selectClasses, selectEntry } from '../lib/stores.svelte';
  import './detail.css';
  import ClassHeader from './detail/ClassHeader.svelte';
  import CoOutputs from './detail/CoOutputs.svelte';
  import DepVersions from './detail/DepVersions.svelte';
  import FilesList from './detail/FilesList.svelte';
  import LinkedEntries from './detail/LinkedEntries.svelte';
  import ParamsTree from './detail/ParamsTree.svelte';
  import SiblingRuns from './detail/SiblingRuns.svelte';
  import SpecBlock from './detail/SpecBlock.svelte';
  import ViewerModal from './detail/ViewerModal.svelte';
  import type { ModalState } from './detail/ViewerModal.svelte';
  import { HIDDEN_JSON_KEYS, detailApi, tableSrcdoc } from './detail/apiDetail';
  import { toast, toastState } from './detail/toast.svelte';

  const detail = $derived(app.payload?.detail ?? null);
  const entry = $derived(detail?.selected_entry ?? null);

  const knownClasses = $derived.by(() => {
    const names = app.payload?.class_cards?.map((c) => c.class_name);
    return names ? new Set(names) : null;
  });

  const visibleParamsKeys = $derived.by(() => {
    if (!entry?.params_tree) return [];
    return Object.keys(entry.params_tree).filter((k) => !HIDDEN_JSON_KEYS.has(k));
  });

  // ------------------------------------------------------------------ modal

  let modal = $state<ModalState | null>(null);

  function closeModal(): void {
    modal = null;
  }

  function onClass(cls: string): void {
    if (!cls) return;
    closeModal();
    selectClasses([cls]);
  }

  async function openJsonPopup(path: string, fallbackTitle = 'JSON'): Promise<void> {
    try {
      const data = await api.popupJson(path);
      const json = (data as { json?: unknown }).json ?? data;
      const title = (data as { title?: string }).title ?? fallbackTitle;
      modal = { kind: 'tree', title, data: json, knownClasses, onClass };
    } catch {
      toast('Failed to load JSON');
    }
  }

  async function openEntryFilePopup(path: string, label: string): Promise<void> {
    if (path.endsWith('.json')) {
      await openJsonPopup(path, label);
    } else {
      modal = { kind: 'iframe', title: label, src: api.fileUrl(path) };
    }
  }

  async function openClassJson(path: string, cls: string, kind: 'tree' | 'nodes' | 'registry'): Promise<void> {
    try {
      const data = await api.popupJson(path);
      const json = (data as { json?: Record<string, unknown> }).json ?? data;
      const inner = kind === 'tree' ? (json.tree ?? json) : kind === 'nodes' ? (json.nodes ?? json) : json;
      modal = {
        kind: 'tree',
        title: `${cls} — ${kind === 'registry' ? 'Registry' : kind[0].toUpperCase() + kind.slice(1)}`,
        data: inner,
        knownClasses,
        onClass,
      };
    } catch {
      toast('Failed to load JSON');
    }
  }

  function openGraph(path: string, cls: string): void {
    modal = { kind: 'iframe', title: `${cls} — Graph`, src: api.fileUrl(path) };
  }

  function openBoundsMap(spec: SpecPayload): void {
    if (!spec.bounds_latlon) return;
    modal = {
      kind: 'iframe',
      title: `Bounds — ${spec.crs ?? ''}`,
      src: detailApi.boundsMapUrl(spec.bounds_latlon as unknown as number[], spec.crs ?? ''),
    };
  }

  // ------------------------------------------------------------------ table preview

  const TABLE_ERROR = '__error__';
  let tableSrcdocState = $state<string | null>(null);

  $effect(() => {
    const path = entry?.table_preview;
    // Re-build on theme change so the iframe follows the active tokens.
    void app.theme;
    tableSrcdocState = null;
    if (!path) return;
    let cancelled = false;
    void (async () => {
      try {
        const html = await detailApi.fetchText(api.fileUrl(path));
        if (!cancelled) tableSrcdocState = tableSrcdoc(html);
      } catch {
        if (!cancelled) tableSrcdocState = TABLE_ERROR;
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  // ------------------------------------------------------------------ hashes

  async function copyHash(label: string, value: string): Promise<void> {
    try {
      await detailApi.copyText(value);
      toast(`${label} copied`);
    } catch {
      toast('Copy failed');
    }
  }
</script>

<section class="detail">
  {#if entry && detail}
    {@const e = entry}

    {#if e.figure_preview}
      <div class="dcard">
        <div class="dcard-hd">
          <div class="dcard-hd-top">
            <span class="dcard-hd-label">Preview</span>
          </div>
          <div class="dcard-hd-actions">
            <button
              class="act-btn"
              onclick={() => detailApi.openPath(e.figure_preview ?? '').then(() => toast('Opened')).catch(() => toast('Failed to open'))}
            >
              Open
            </button>
          </div>
        </div>
        <div class="dcard-body fig-preview">
          <button
            class="fig-btn"
            title="Click to open full-size preview"
            onclick={() => {
              if (e.figure_preview) {
                modal = { kind: 'image', title: 'Preview', src: api.fileUrl(e.figure_preview) };
              }
            }}
          >
            <img src={api.fileUrl(e.figure_preview)} alt="Figure preview" loading="eager" />
          </button>
        </div>
      </div>
    {/if}

    {#if e.table_preview}
      <div class="dcard">
        <div class="dcard-hd">
          <div class="dcard-hd-top">
            <span class="dcard-hd-label">Preview</span>
          </div>
          <div class="dcard-hd-actions">
            <button
              class="act-btn"
              title="Show in a larger view"
              onclick={() => {
                if (tableSrcdocState && tableSrcdocState !== TABLE_ERROR) {
                  modal = { kind: 'srcdoc', title: 'Preview', srcdoc: tableSrcdocState };
                }
              }}
            >
              Show
            </button>
            <button
              class="act-btn"
              onclick={() => detailApi.openPath(e.table_preview ?? '').then(() => toast('Opened')).catch(() => toast('Failed to open'))}
            >
              Open
            </button>
          </div>
        </div>
        <div class="dcard-body" style="padding: 0">
          {#if tableSrcdocState === null}
            <div class="tbl-preview-loading">Loading…</div>
          {:else if tableSrcdocState === TABLE_ERROR}
            <div class="tbl-preview-loading">Failed to load preview</div>
          {:else}
            <iframe class="tbl-preview-frame" srcdoc={tableSrcdocState} title="Table preview"></iframe>
          {/if}
        </div>
      </div>
    {/if}

    <ClassHeader {detail} onClassJson={openClassJson} onGraph={openGraph} />

    <div class="dcard">
      <div class="dcard-hd">
        <div class="dcard-hd-top">
          <span class="dcard-hd-label">Entry</span>
          {#if e.format_version_stale}
            <span class="dbadge dbadge--danger" title="pygeodata version changed — entry must be regenerated">
              version
            </span>
          {:else if e.dep_hash_stale}
            <span
              class="dbadge dbadge--warn"
              title="Dependencies changed since this entry was last computed — results may no longer match current code"
            >
              stale
            </span>
          {/if}
          {#if detail.entry_version_label}
            <span class="dbadge dbadge--neutral" title="Code version this entry was computed with">
              {detail.entry_version_label}
            </span>
          {/if}
        </div>
        <div class="dcard-hd-actions">
          {#if visibleParamsKeys.length > 0 && e.params_path}
            <button class="act-btn" title="View full params JSON" onclick={() => openEntryFilePopup(e.params_path ?? '', 'Params')}>
              Params
            </button>
          {/if}
          {#if e.state_hash_path}
            <button class="act-btn" title="View state hash JSON" onclick={() => openEntryFilePopup(e.state_hash_path ?? '', 'Hash')}>
              Hash
            </button>
          {/if}
          {#if e.execution_graph_path}
            <button class="act-btn" title="View execution graph" onclick={() => openEntryFilePopup(e.execution_graph_path ?? '', 'Graph')}>
              Graph
            </button>
          {/if}
        </div>
      </div>
      <div class="dcard-body">
        <SpecBlock spec={e.spec} onBoundsMap={openBoundsMap} />
        <div class="dcard-sep"></div>
        <div class="hash-row">
          {#if e.record_id}
            <button class="hash-chip" title={e.record_id} onclick={() => copyHash('Record hash', e.record_id)}>
              <b>record</b>{e.record_id.slice(0, 8)}
            </button>
          {/if}
          {#if e.state_hash}
            <button class="hash-chip" title={e.state_hash} onclick={() => copyHash('State hash', e.state_hash)}>
              <b>state</b>{e.state_hash.slice(0, 8)}
            </button>
          {/if}
          {#if e.instance_hash}
            <button class="hash-chip" title={e.instance_hash} onclick={() => copyHash('Instance hash', e.instance_hash)}>
              <b>instance</b>{e.instance_hash.slice(0, 8)}
            </button>
          {/if}
          {#if e.dep_hash}
            <button class="hash-chip" title={e.dep_hash} onclick={() => copyHash('Dep hash', e.dep_hash)}>
              <b>dep</b>{e.dep_hash.slice(0, 8)}
            </button>
          {/if}
        </div>
        {#if e.primary_file}
          <div class="dcard-sep"></div>
          <FilesList files={[e.primary_file, ...e.sidecar_files]} primary={e.primary_file} />
        {/if}
      </div>
      {#if e.warnings.length > 0}
        <div class="entry-warnings">
          {#each e.warnings as w, i (i)}
            <div class="entry-warning">⚠ {w}</div>
          {/each}
        </div>
      {/if}
    </div>

    {#if e.co_outputs.length > 0}
      <div class="dcard">
        <CoOutputs outputs={e.co_outputs} />
      </div>
    {/if}

    {#if e.same_instance_runs.length > 0}
      <div class="dcard">
        <SiblingRuns runs={e.same_instance_runs} />
      </div>
    {/if}

    {#if e.linked_entries.length > 0}
      <div class="dcard">
        <div class="dcard-hd">
          <span class="dcard-hd-label">Associated entries</span>
        </div>
        <LinkedEntries links={e.linked_entries} />
      </div>
    {/if}

    <DepVersions {detail} />

    {#if visibleParamsKeys.length > 0}
      <div class="dcard">
        <div class="dcard-hd">
          <span class="dcard-hd-label">Parameters</span>
        </div>
        <div class="dcard-body">
          <ParamsTree data={e.params_tree} filterHidden {knownClasses} {onClass} />
        </div>
      </div>
    {/if}
  {:else if detail}
    <ClassHeader {detail} onClassJson={openClassJson} onGraph={openGraph} />
    <div class="detail-hint">Select an entry to view details.</div>
  {:else if app.selectedClasses.length > 1}
    <div class="detail-hint detail-hint--multi">
      <span class="hint-label">{app.selectedClasses.length} classes selected</span>
      <div class="hint-chips">
        {#each app.selectedClasses as cn (cn)}
          <button class="dep-chip" onclick={() => selectClasses([cn])}>{cn}</button>
        {/each}
      </div>
      <span class="hint-sub">Select an entry to view details.</span>
    </div>
  {:else}
    <div class="detail-hint">Select an entry to inspect it.</div>
  {/if}

  <ViewerModal {modal} onClose={closeModal} />

  {#if toastState.msg}
    <div class="dtoast">{toastState.msg}</div>
  {/if}
</section>

<style>
  .detail {
    overflow-y: auto;
    background: var(--bg);
    min-height: 0;
    padding-top: var(--s-3);
    padding-bottom: var(--s-4);
  }

  .detail-hint {
    padding: var(--s-4);
    color: var(--text-3);
    font-size: var(--fs-sm);
  }

  .detail-hint--multi {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    align-items: flex-start;
  }

  .hint-label {
    color: var(--text-2);
    font-size: var(--fs-xs);
  }

  .hint-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .hint-sub {
    color: var(--text-3);
    font-size: var(--fs-xs);
  }
</style>
