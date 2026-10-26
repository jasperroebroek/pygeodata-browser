<script lang="ts">
  import {
    BOOLEAN_TARGETS,
    classesState,
    clearAllFilters,
    filterState,
    hasActiveFilters,
    layout,
    selection,
    setFilters,
    setMultiClass,
    setSidebarCollapsed,
    setVersionFilter,
    tableState,
    toggleClass,
    toggleSpecFilter,
    ui,
  } from '../lib/stores.svelte';
  import { FILTER_OPERATORS, FILTER_TARGETS, SPEC_DIMENSIONS } from '../lib/filters';
  import FilterSections from './FilterSections.svelte';
  import TypeBadge from './TypeBadge.svelte';

  let nameFilter = $state('');

  const shownCount = $derived(
    tableState.selectedClasses.length > 0 ? tableState.total : (classesState.counts?.visible_entries ?? null),
  );

  interface Pill {
    key: string;
    meta?: string;
    label: string;
    wide?: boolean;
    filter: boolean;
    remove: () => void;
  }

  const pills = $derived.by(() => {
    const out: Pill[] = [];
    for (const cn of tableState.selectedClasses) {
      out.push({
        key: `c:${cn}`,
        label: cn,
        filter: false,
        remove: () => void toggleClass(cn, true),
      });
    }
    filterState.filters.forEach((f, i) => {
      const isBool = BOOLEAN_TARGETS.has(f.target);
      if (!isBool && !f.value.trim()) return;
      const target = FILTER_TARGETS.find(([v]) => v === f.target)?.[1] ?? f.target;
      const op = FILTER_OPERATORS.find(([v]) => v === f.operator)?.[2] ?? f.operator;
      out.push({
        key: `f:${i}`,
        meta: isBool ? undefined : `${target} ${op}`,
        label: isBool ? target : f.value,
        filter: true,
        remove: () =>
          setFilters(
            i === 0
              ? [{ target: 'all', operator: 'contains', value: '' }, ...filterState.filters.slice(1)]
              : filterState.filters.filter((_, j) => j !== i),
          ),
      });
    });
    for (const dim of SPEC_DIMENSIONS) {
      const labels = new Map(
        (classesState.specOptions[dim.key] ?? []).map((o) => (typeof o === 'string' ? [o, o] : [o.value, o.label])),
      );
      for (const v of filterState.specFilters[dim.key] ?? []) {
        out.push({
          key: `s:${dim.key}:${v}`,
          meta: dim.pill,
          label: labels.get(v) ?? v,
          wide: dim.key === 'bounds',
          filter: true,
          remove: () => void toggleSpecFilter(dim.key, v),
        });
      }
    }
    if (filterState.versionFilter) {
      const opt = classesState.versionOptions.find((o) => o.version_id === filterState.versionFilter);
      out.push({
        key: 'v',
        meta: 'Snapshot',
        label: opt?.label ?? filterState.versionFilter,
        filter: true,
        remove: () => void setVersionFilter(null),
      });
    }
    return out;
  });

  const kindCards = $derived(
    classesState.cards.filter(
      (c) => filterState.kindFilter === 'all' || (c.object_type ?? '').toLowerCase() === filterState.kindFilter,
    ),
  );

  const visibleCards = $derived.by(() => {
    const q = nameFilter.toLowerCase();
    const selected = new Set(tableState.selectedClasses);
    return kindCards.filter(
      (c) =>
        (selection.showEmpty || c.visible_record_count > 0 || selected.has(c.class_name)) &&
        (!q || c.class_name.toLowerCase().includes(q)),
    );
  });

  const bootstrapNames = $derived(
    classesState.cards.length === 0 ? [...new Map(ui.bootstrap.map((r) => [r.class_name, r])).values()] : [],
  );

  function dotFor(c: (typeof classesState.cards)[number]): { cls: string; title: string } | null {
    // Single dot: version mismatch > source stale > deps stale > cache-only; stale only once run.
    const hasEntries = c.total_record_count > 0;
    if (hasEntries && c.format_version_stale)
      return { cls: 'status-dot--version', title: 'pygeodata version changed — entries must be regenerated' };
    if (hasEntries && c.source_stale)
      return { cls: 'status-dot--source', title: 'Source code changed since last run — entries may be outdated' };
    if (hasEntries && c.deps_stale)
      return {
        cls: 'status-dot--deps',
        title: 'An upstream dependency changed since last run — entries may be outdated',
      };
    if (!c.loaded) return { cls: 'status-dot--cache', title: 'Cache-only — not loaded in Python registry' };
    return null;
  }

  function onCardKey(e: KeyboardEvent, cn: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      void toggleClass(cn, e.metaKey || e.ctrlKey);
    }
  }
</script>

<aside class="sidebar" class:collapsed={layout.sidebarCollapsed}>
  <button
    class="sidebar-collapse-btn"
    title={layout.sidebarCollapsed ? 'Expand filters' : 'Collapse filters'}
    onclick={() => setSidebarCollapsed(!layout.sidebarCollapsed)}
  >
    {layout.sidebarCollapsed ? '»' : '«'}
  </button>
  <div class="sb-count-row">
    <span class="count-chip">{shownCount === null ? '' : `${shownCount} shown`}</span>
  </div>
  <div class="sb-pills-row" class:pills-empty={!hasActiveFilters()}>
    <div class="active-pills">
      {#each pills as p (p.key)}
        <span class="pill" class:pill-filter={p.filter} class:pill-filter--wide={p.wide}>
          <span class="pill-label">
            {#if p.meta}<span class="pill-meta">{p.meta}</span>{/if}
            {p.label}
          </span>
          <button class="pill-rm" onclick={p.remove}>✕</button>
        </span>
      {/each}
    </div>
    <button class="clear-all-btn" title="Clear all filters" onclick={() => void clearAllFilters()}>Clear all</button>
    <span class="sb-no-filters">No filters active</span>
  </div>

  <FilterSections />

  <div class="sb-section sb-section--classes">
    <div class="sb-section-hd sb-section-hd--static">
      <span class="sb-section-title">Classes</span>
      <span class="sb-section-meta">
        {#if classesState.cards.length}
          {visibleCards.length < kindCards.length ? `${visibleCards.length} / ${kindCards.length}` : kindCards.length}
        {/if}
      </span>
      <div class="class-list-toolbar">
        <button class="toggle-btn" class:active={selection.showEmpty} onclick={() => (selection.showEmpty = !selection.showEmpty)}>
          Show empty
        </button>
        <button class="toggle-btn" class:active={selection.multiClass} onclick={() => void setMultiClass(!selection.multiClass)}>
          Multi-select
        </button>
      </div>
    </div>
    <div class="class-filter-row">
      <input class="code-filter" placeholder="Filter classes…" bind:value={nameFilter} />
    </div>
    <div class="class-list">
      {#if classesState.cards.length === 0}
        {#each bootstrapNames as r (r.class_name)}
          <div class="class-card" title="Latest entry (full state still loading): {r.state_hash ?? ''}">{r.class_name}</div>
        {/each}
      {:else if visibleCards.length === 0}
        <div class="empty-list">No classes.</div>
      {:else}
        {#each visibleCards as c (c.class_name)}
          {@const dot = dotFor(c)}
          <div
            class="class-card"
            class:filtered={tableState.selectedClasses.includes(c.class_name)}
            class:class-card--dim={c.visible_record_count === 0}
            title={c.class_name}
            role="button"
            tabindex="0"
            onclick={(e) => void toggleClass(c.class_name, e.metaKey || e.ctrlKey)}
            onkeydown={(e) => onCardKey(e, c.class_name)}
          >
            <span class="class-card-name"
              >{c.class_name}{#if dot}<span class="status-dot {dot.cls}" title={dot.title}></span>{/if}</span
            >
            <span class="class-card-meta">
              <span class="class-card-count">{c.visible_record_count}/{c.total_record_count}</span>
              <TypeBadge type={c.object_type} />
            </span>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</aside>
