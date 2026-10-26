<script lang="ts">
  import { app, selectClasses, toggleShowEmpty, clearAllFilters, setVersionFilter, setFilters } from '../lib/stores.svelte';
  import type { ClassCard } from '../lib/api';
  import { toggleSpecFilter } from '../lib/stores.svelte';
  import FilterPanel from './FilterPanel.svelte';

  let search = $state('');

  const cards = $derived.by(() => {
    const fromBootstrap = app.payload === null && app.bootstrap.length > 0;
    if (fromBootstrap) {
      const grouped = new Map<string, { object_type: string; count: number }>();
      for (const row of app.bootstrap) {
        const g = grouped.get(row.class_name) ?? { object_type: row.object_type ?? 'Data', count: 0 };
        g.count += 1;
        grouped.set(row.class_name, g);
      }
      return [...grouped.entries()]
        .map(([class_name, g]) => ({
          class_name,
          object_type: g.object_type as ClassCard['object_type'],
          loaded: true,
          call_dependency_names: [],
          inheritance_dependency_names: [],
          total_record_count: g.count,
          visible_record_count: g.count,
          selected: app.selectedClasses.includes(class_name),
          source_stale: false,
          deps_stale: false,
          format_version_stale: false,
        }))
        .sort((a, b) => a.class_name.localeCompare(b.class_name));
    }
    return app.payload?.class_cards ?? [];
  });

  const filtered = $derived(
    search ? cards.filter((c) => c.class_name.toLowerCase().includes(search.toLowerCase())) : cards,
  );

  const activeFilters = $derived.by(() => {
    const out: { key: string; label: string; title: string; clear: () => void }[] = [];
    for (const f of app.filters) {
      if (f.value || f.target === 'has_warnings' || f.target === 'has_error') {
        out.push({
          key: `f:${f.target}:${f.operator}:${f.value}`,
          label: `${f.target.replace(/_/g, ' ')} ${f.operator.replace(/_/g, ' ')} ${f.value || ''}`.trim(),
          title: 'Remove this filter',
          clear: () => setFilters(app.filters.filter((x) => x !== f)),
        });
      }
    }
    for (const [dim, values] of Object.entries(app.specFilters)) {
      for (const v of values) {
        out.push({
          key: `s:${dim}:${v}`,
          label: v,
          title: `Spec filter: ${dim}`,
          clear: () => toggleSpecFilter(dim, v),
        });
      }
    }
    if (app.versionFilter) {
      const label = app.payload?.version_options.find((x) => x.version_id === app.versionFilter)?.label ?? 'snapshot';
      out.push({ key: 'v', label, title: 'Snapshot filter', clear: () => setVersionFilter(null) });
    }
    return out;
  });

  const visible = $derived(
    app.showEmpty || app.selectedClasses.length > 0
      ? filtered
      : filtered.filter((c) => c.visible_record_count > 0),
  );
</script>

<aside class="classes">
  <div class="pills-row">
    {#if activeFilters.length > 0}
      {#each activeFilters as f (f.key)}
        <button class="active-pill" title={f.title} onclick={f.clear}>{f.label} ✕</button>
      {/each}
      <button class="clear-all" onclick={clearAllFilters}>Clear all</button>
    {:else}
      <span class="no-filters">No filters active</span>
    {/if}
  </div>
  <FilterPanel />



  <div class="classes-hd">
    <span class="classes-title">Classes</span>
    <button class:active={app.showEmpty} onclick={toggleShowEmpty} title="Show classes without entries">
      Show empty
    </button>
  </div>
  <div class="search">
    <input type="search" placeholder="Filter classes…" bind:value={search} />
  </div>

  <div class="list">
    {#if cards.length === 0 && app.loading}
      <div class="empty">loading…</div>
    {:else if visible.length === 0}
      <div class="empty">No classes.</div>
    {/if}
    {#each visible as card (card.class_name)}
      <button
        class="card"
        class:selected={card.selected}
        class:dim={card.visible_record_count === 0}
        onclick={(e) =>
          selectClasses(
            card.selected
              ? app.selectedClasses.filter((c) => c !== card.class_name)
              : e.metaKey || e.ctrlKey
                ? [...app.selectedClasses, card.class_name]
                : [card.class_name],
          )}
      >
        <span class="name">{card.class_name}</span>
        <span class="meta">
          {#if card.source_stale}<span class="dot dot--warning" title="source changed"></span>{/if}
          {#if card.deps_stale}<span class="dot dot--danger" title="dependencies changed"></span>{/if}
          <span class="type">{card.object_type}</span>
          <span class="count mono">{card.visible_record_count}/{card.total_record_count}</span>
        </span>
      </button>
    {/each}
  </div>
</aside>

<style>
  .classes {
    display: flex;
    flex-direction: column;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    min-height: 0;
  }

  .classes-hd {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s-2) var(--s-2) var(--s-1);
  }

  .classes-hd button {
    padding: 2px 8px;
    border-radius: var(--r-full);
    border: 1px solid var(--border-strong);
    color: var(--text-2);
    font-size: var(--fs-xs);
  }

  .classes-hd button.active {
    background: var(--accent-soft);
    color: var(--accent-text);
    border-color: transparent;
  }

  .classes-title {
    font-size: var(--fs-xs);
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .search {
    padding: 0 var(--s-2) var(--s-2);
  }

  input {
    width: 100%;
    padding: 5px 8px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-sm);
  }

  input:focus {
    outline: 1.5px solid var(--accent);
    border-color: transparent;
  }

  .pills-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
    min-height: 26px;
    padding: var(--s-1) var(--s-2);
    border-bottom: 1px solid var(--border);
  }

  .no-filters {
    color: var(--text-3);
    font-size: var(--fs-xs);
  }

  .active-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: var(--r-full);
    background: var(--accent-soft);
    color: var(--accent-text);
    font-size: var(--fs-xs);
  }

  .active-pill:hover {
    background: var(--bg-active);
  }

  .clear-all {
    color: var(--text-3);
    font-size: var(--fs-xs);
    text-decoration: underline;
  }

  .toggles {
    display: flex;
    gap: var(--s-1);
    padding: var(--s-2);
    border-bottom: 1px solid var(--border);
  }

  .toggles button {
    flex: 1;
    padding: 3px 8px;
    border-radius: var(--r-full);
    border: 1px solid var(--border-strong);
    color: var(--text-2);
    font-size: var(--fs-xs);
  }

  .toggles button.active {
    background: var(--accent-soft);
    color: var(--accent-text);
    border-color: transparent;
  }

  .list {
    overflow-y: auto;
    padding: var(--s-2);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: 2px;
    text-align: left;
    padding: 6px 8px;
    border-radius: var(--r-sm);
    border: 1px solid transparent;
  }

  .card:hover {
    background: var(--bg-hover);
  }

  .card.selected {
    background: var(--bg-selected);
    border-color: var(--accent-soft);
  }

  .card.dim {
    opacity: 0.5;
  }

  .name {
    font-size: var(--fs-sm);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .type {
    flex: 1;
  }

  .count {
    font-size: var(--fs-xs);
  }

  .empty {
    padding: var(--s-3);
    color: var(--text-3);
    font-size: var(--fs-sm);
    text-align: center;
  }
</style>
