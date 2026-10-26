<script lang="ts">
  import { app, setFilters, setLogicMode, toggleSpecFilter, setVersionFilter } from '../lib/stores.svelte';
  import type { FilterRow, LogicMode } from '../lib/stores.svelte';

  const TARGETS: [string, string][] = [
    ['all', 'All'],
    ['class', 'Class'],
    ['crs', 'CRS'],
    ['key_group', 'Group'],
    ['key', 'Key'],
    ['value', 'Value'],
    ['path', 'Path'],
    ['has_warnings', 'Has warnings'],
    ['has_error', 'Has error'],
  ];
  const OPERATORS: [string, string][] = [
    ['contains', 'contains'],
    ['equals', 'equals'],
    ['starts', 'starts with'],
    ['not_contains', 'not contains'],
  ];
  const BOOLEAN_TARGETS = new Set(['has_warnings', 'has_error']);
  const DEFAULT_ROW: FilterRow = { target: 'all', operator: 'contains', value: '' };
  const LOGIC_MODES: LogicMode[] = ['AND', 'OR', 'NOT'];

  type SectionId = 'search' | 'spec' | 'snapshots';
  // Accordion like the legacy sidebar: at most one section open.
  let openSection = $state<SectionId | null>(null);

  function toggleSection(id: SectionId) {
    openSection = openSection === id ? null : id;
  }

  // ---------------------------------------------------------------------------
  // Filter rows. Local UI state may hold empty placeholder rows; only active
  // rows (non-empty value, or a boolean target) are pushed to app.filters so
  // the backend never evaluates blank rows (legacy buildPayload behaviour).
  // ---------------------------------------------------------------------------

  let rows = $state<FilterRow[]>(app.filters.map((f) => ({ ...f })));
  const displayRows = $derived(rows.length > 0 ? rows : [DEFAULT_ROW]);

  function isActive(f: FilterRow) {
    return BOOLEAN_TARGETS.has(f.target) || f.value.trim() !== '';
  }

  function commit(next: FilterRow[]) {
    rows = next;
    setFilters(next.filter(isActive));
  }

  function updateRow(i: number, patch: Partial<FilterRow>) {
    const base = rows.length > 0 ? rows : [DEFAULT_ROW];
    commit(base.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  }

  function addRow() {
    const base = rows.length > 0 ? rows : [DEFAULT_ROW];
    commit([...base.map((f) => ({ ...f })), { ...DEFAULT_ROW }]);
  }

  function removeRow(i: number) {
    if (rows.length === 0) return; // placeholder row is already empty
    if (i === 0) {
      commit(rows.map((f, j) => (j === 0 ? { ...f, value: '' } : f)));
    } else {
      commit(rows.filter((_, j) => j !== i));
    }
  }

  // ---------------------------------------------------------------------------
  // Spec filters
  // ---------------------------------------------------------------------------

  type SpecOption = string | { value: string; label: string };
  const SPEC_DIMENSIONS: { key: string; label: string; wide?: boolean }[] = [
    { key: 'crs', label: 'CRS' },
    { key: 'resolution', label: 'Resolution', wide: true },
    { key: 'shape', label: 'Shape' },
    { key: 'bounds', label: 'Bounds', wide: true },
  ];

  const specOptions = $derived(
    (app.payload?.spec_options ?? {}) as Record<string, SpecOption[]>,
  );
  const optValue = (o: SpecOption) => (typeof o === 'string' ? o : o.value);
  const optLabel = (o: SpecOption) => (typeof o === 'string' ? o : o.label);

  function specActive(dim: string, value: string) {
    return (app.specFilters[dim] ?? []).includes(value);
  }

  // ---------------------------------------------------------------------------
  // Snapshots
  // ---------------------------------------------------------------------------

  const versionOptions = $derived(app.payload?.version_options ?? []);
  const versionValue = $derived(
    app.versionFilter && versionOptions.some((v) => v.version_id === app.versionFilter)
      ? app.versionFilter
      : 'all',
  );

  function onVersionChange(e: Event) {
    const v = (e.currentTarget as HTMLSelectElement).value;
    setVersionFilter(v === 'all' ? null : v);
  }
</script>

{#if app.payload}
  <div class="panel">
    <section class:open={openSection === 'search'}>
      <button class="hd" onclick={() => toggleSection('search')}>
        <span class="title">Search</span>
        <span class="chev">▾</span>
      </button>
      {#if openSection === 'search'}
        <div class="body">
          <div class="logic">
            <span class="label">Mode</span>
            <div class="seg">
              {#each LOGIC_MODES as m (m)}
                <button class:active={app.logicMode === m} onclick={() => setLogicMode(m)}>{m}</button>
              {/each}
            </div>
          </div>
          {#each displayRows as row, i (i)}
            <div class="row" class:bool={BOOLEAN_TARGETS.has(row.target)}>
              <select
                value={row.target}
                onchange={(e) => updateRow(i, { target: e.currentTarget.value })}
              >
                {#each TARGETS as [val, label] (val)}
                  <option value={val}>{label}</option>
                {/each}
              </select>
              {#if !BOOLEAN_TARGETS.has(row.target)}
                <select
                  value={row.operator}
                  onchange={(e) => updateRow(i, { operator: e.currentTarget.value })}
                >
                  {#each OPERATORS as [val, label] (val)}
                    <option value={val}>{label}</option>
                  {/each}
                </select>
                <input
                  value={row.value}
                  placeholder="…"
                  autocomplete="off"
                  oninput={(e) => updateRow(i, { value: e.currentTarget.value })}
                />
              {/if}
              <button
                class="rm"
                class:clear={i === 0}
                title={i === 0 ? 'Clear' : 'Remove'}
                onclick={() => removeRow(i)}
              >
                ✕
              </button>
            </div>
          {/each}
          <button class="add" onclick={addRow}>＋ Add filter</button>
        </div>
      {/if}
    </section>

    <section class:open={openSection === 'spec'}>
      <button class="hd" onclick={() => toggleSection('spec')}>
        <span class="title">Spec filters</span>
        <span class="chev">▾</span>
      </button>
      {#if openSection === 'spec'}
        <div class="body">
          <div class="spec-grid">
            {#each SPEC_DIMENSIONS as dim (dim.key)}
              <div class:spec-wide={dim.wide}>
                <span class="label">{dim.label}</span>
                <div class="pills">
                  {#if (specOptions[dim.key] ?? []).length === 0}
                    <span class="none">—</span>
                  {:else}
                    {#each specOptions[dim.key] as opt (optValue(opt))}
                      <button
                        class="pill"
                        class:active={specActive(dim.key, optValue(opt))}
                        title={optLabel(opt)}
                        onclick={() => toggleSpecFilter(dim.key, optValue(opt))}
                      >
                        {optLabel(opt)}
                      </button>
                    {/each}
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </section>

    <section class:open={openSection === 'snapshots'}>
      <button class="hd" onclick={() => toggleSection('snapshots')}>
        <span class="title">Snapshots</span>
        <span class="chev">▾</span>
      </button>
      {#if openSection === 'snapshots'}
        <div class="body">
          <select value={versionValue} onchange={onVersionChange}>
            <option value="all">All snapshots</option>
            {#each versionOptions as v (v.version_id)}
              <option value={v.version_id}>{v.label}</option>
            {/each}
          </select>
        </div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    padding: var(--s-2);
    border-bottom: 1px solid var(--border);
  }

  section {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    overflow: hidden;
  }

  .hd {
    display: flex;
    align-items: center;
    gap: var(--s-1);
    width: 100%;
    padding: 5px var(--s-2);
    background: none;
    text-align: left;
  }

  .hd:hover {
    background: var(--bg-hover);
  }

  .title {
    flex: 1;
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-3);
  }

  .chev {
    font-size: var(--fs-xs);
    color: var(--text-3);
    transition: transform var(--t-fast) var(--ease);
  }

  section.open .chev {
    transform: rotate(180deg);
  }

  .body {
    padding: var(--s-2);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  select,
  input {
    min-width: 0;
    padding: 4px 7px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-xs);
  }

  select:focus,
  input:focus {
    outline: 1.5px solid var(--accent);
    border-color: transparent;
  }

  .logic {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .label {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .seg {
    display: flex;
    gap: 3px;
  }

  .seg button {
    padding: 3px 11px;
    border: none;
    border-radius: var(--r-full);
    background: transparent;
    font-size: var(--fs-xs);
    color: var(--text-2);
    white-space: nowrap;
  }

  .seg button:hover:not(.active) {
    background: var(--bg-hover);
    color: var(--text);
  }

  .seg button.active {
    background: var(--accent-soft);
    color: var(--accent-text);
    font-weight: 600;
  }

  .row {
    display: grid;
    grid-template-columns: 62px auto 1fr 22px;
    gap: 3px;
    align-items: center;
  }

  .row select,
  .row input {
    padding: 4px 4px;
  }

  .row.bool select {
    grid-column: 1 / -2;
  }

  .rm {
    width: 22px;
    height: 22px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-xs);
    color: var(--text-3);
    font-size: var(--fs-xs);
  }

  .rm:hover {
    border-color: var(--danger);
    color: var(--danger);
  }

  .rm.clear:hover {
    border-color: var(--text-2);
    color: var(--text-2);
  }

  .add {
    margin-top: 2px;
    width: 100%;
    padding: 4px;
    background: none;
    border: 1px dashed var(--border-strong);
    border-radius: var(--r-sm);
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .add:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .spec-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-2) var(--s-3);
  }

  .spec-wide {
    grid-column: 1 / -1;
  }

  .spec-grid .label {
    display: block;
    margin-bottom: var(--s-1);
  }

  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-1);
  }

  .pill {
    padding: 3px 9px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-full);
    background: var(--bg-elev);
    font-size: var(--fs-xs);
    color: var(--text-2);
    white-space: nowrap;
  }

  .pill:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .pill.active {
    background: var(--accent-soft);
    border-color: var(--accent-soft);
    color: var(--accent-text);
  }

  .none {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .body > select {
    width: 100%;
  }
</style>
