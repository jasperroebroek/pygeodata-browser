<script lang="ts">
  import {
    BOOLEAN_TARGETS,
    classesState,
    filterState,
    setFilters,
    setLogicMode,
    setVersionFilter,
    toggleSpecFilter,
  } from '../lib/stores.svelte';
  import type { FilterRow, LogicMode } from '../lib/stores.svelte';
  import { FILTER_OPERATORS, FILTER_TARGETS, SPEC_DIMENSIONS } from '../lib/filters';

  const DEFAULT_ROW: FilterRow = { target: 'all', operator: 'contains', value: '' };
  const LOGIC_MODES: LogicMode[] = ['AND', 'OR', 'NOT'];

  type SectionId = 'search' | 'spec' | 'snapshots';
  // Accordion: at most one section open.
  let openSection = $state<SectionId | null>(null);

  const rows = $derived(filterState.filters.length > 0 ? filterState.filters : [DEFAULT_ROW]);

  function updateRow(i: number, patch: Partial<FilterRow>, debounce = false) {
    setFilters(
      rows.map((f, j) => (j === i ? { ...f, ...patch } : f)),
      { debounce },
    );
  }

  let valueInputs: HTMLInputElement[] = $state([]);

  async function addRow() {
    setFilters([...rows, { ...DEFAULT_ROW }]);
    await Promise.resolve();
    valueInputs[rows.length - 1]?.focus();
  }

  function removeRow(i: number) {
    setFilters(i === 0 ? rows.map((f, j) => (j === 0 ? { ...f, value: '' } : f)) : rows.filter((_, j) => j !== i));
  }

  const optValue = (o: string | { value: string }) => (typeof o === 'string' ? o : o.value);
  const optLabel = (o: string | { label: string }) => (typeof o === 'string' ? o : o.label);
</script>

{#snippet header(id: SectionId, title: string)}
  <button class="sb-section-hd" onclick={() => (openSection = openSection === id ? null : id)}>
    <span class="sb-section-title">{title}</span>
    <span class="sb-chevron">▾</span>
  </button>
{/snippet}

<div class="sb-section collapsible" class:open={openSection === 'search'}>
  {@render header('search', 'Search')}
  <div class="sb-section-body">
    <div class="logic-row">
      <span class="sb-label">Mode</span>
      <div class="kind-tabs">
        {#each LOGIC_MODES as m (m)}
          <button class="kind-tab" class:active={filterState.logicMode === m} onclick={() => void setLogicMode(m)}>{m}</button>
        {/each}
      </div>
    </div>
    <div>
      {#each rows as row, i (i)}
        {@const isBool = BOOLEAN_TARGETS.has(row.target)}
        <div class="filter-row" class:filter-row--bool={isBool}>
          <select
            value={row.target}
            style:grid-column={isBool ? '1/-2' : null}
            onchange={(e) => updateRow(i, { target: e.currentTarget.value })}
          >
            {#each FILTER_TARGETS as [val, label] (val)}
              <option value={val}>{label}</option>
            {/each}
          </select>
          {#if !isBool}
            <select value={row.operator} onchange={(e) => updateRow(i, { operator: e.currentTarget.value })}>
              {#each FILTER_OPERATORS as [val, label] (val)}
                <option value={val}>{label}</option>
              {/each}
            </select>
            <input
              bind:this={valueInputs[i]}
              value={row.value}
              placeholder="…"
              autocomplete="off"
              oninput={(e) => updateRow(i, { value: e.currentTarget.value }, true)}
            />
          {/if}
          <button class="rm-filter-btn" class:fr-clear={i === 0} title={i === 0 ? 'Clear' : 'Remove'} onclick={() => removeRow(i)}>
            ✕
          </button>
        </div>
      {/each}
    </div>
    <button class="add-row-btn" onclick={() => void addRow()}>＋ Add filter</button>
  </div>
</div>

<div class="sb-section collapsible" class:open={openSection === 'spec'}>
  {@render header('spec', 'Spec filters')}
  <div class="sb-section-body">
    <div class="spec-grid-sidebar">
      {#each SPEC_DIMENSIONS as dim (dim.key)}
        {@const options = classesState.specOptions[dim.key] ?? []}
        <div class="spec-group" class:spec-group--wide={dim.wide}>
          <div class="sb-label">{dim.label}</div>
          <div class="spec-pills">
            {#if options.length === 0}
              <span class="spec-none">—</span>
            {:else}
              {#each options as opt (optValue(opt))}
                <button
                  class="spec-pill"
                  class:active={(filterState.specFilters[dim.key] ?? []).includes(optValue(opt))}
                  title={optLabel(opt)}
                  onclick={() => void toggleSpecFilter(dim.key, optValue(opt))}
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
</div>

<div class="sb-section collapsible" class:open={openSection === 'snapshots'}>
  {@render header('snapshots', 'Snapshots')}
  <div class="sb-section-body">
    <select
      class="version-select"
      value={filterState.versionFilter ?? 'all'}
      onchange={(e) => void setVersionFilter(e.currentTarget.value === 'all' ? null : e.currentTarget.value)}
    >
      <option value="all">All snapshots</option>
      {#each classesState.versionOptions as o (o.version_id)}
        <option value={o.version_id}>{o.label}</option>
      {/each}
    </select>
  </div>
</div>
