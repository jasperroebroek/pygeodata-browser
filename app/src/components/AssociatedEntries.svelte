<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { LinkedEntry } from '../lib/api';

  let {
    entries,
    knownClasses,
    onEntry,
    onClass,
  }: {
    entries: LinkedEntry[];
    knownClasses: Set<string>;
    onEntry: (stateHash: string, className: string) => void;
    onClass: (className: string) => void;
  } = $props();

  const LIMIT = 5;

  interface Part {
    key: string;
    value: string;
  }

  interface Group {
    className: string;
    items: LinkedEntry[];
    /** Every item has at most one param: render one row per item under a shared header. */
    flat: boolean;
  }

  /** Contiguous runs of the same class share one header. */
  const groups = $derived.by(() => {
    const out: Group[] = [];
    for (const l of entries) {
      const last = out[out.length - 1];
      if (last && last.className === l.class_name) last.items.push(l);
      else out.push({ className: l.class_name, items: [l], flat: false });
    }
    for (const g of out) {
      g.flat = g.items.length > 1 && g.items.every((l) => Object.keys(l.params_summary ?? {}).length <= 1);
    }
    return out;
  });

  let expanded = $state<Record<number, boolean>>({});

  $effect(() => {
    void entries;
    expanded = {};
  });

  function summarize(summary: Record<string, string[]>): Part[] {
    return Object.entries(summary).map(([k, values]) => {
      if (!k.endsWith('[]')) return { key: k, value: values[0] ?? '' };
      const uniq = [...new Set(values)];
      const value = uniq.length === 1 && values.length > 1 ? `${uniq[0]} ×${values.length}` : values.join(', ');
      return { key: `${k.slice(0, -2)} [${values.length}]`, value };
    });
  }

  const fullText = (summary: Record<string, string[]>) =>
    Object.entries(summary)
      .map(([k, v]) => `${k}: ${v.join(', ')}`)
      .join('\n');

  const sharedKey = (g: Group) => Object.keys(g.items[0].params_summary ?? {})[0] ?? '';
</script>

{#snippet cls(name: string)}
  {#if knownClasses.has(name)}
    <a
      href="#top"
      class="assoc-cls"
      title="Show source"
      onclick={(ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        onClass(name);
      }}>{name}</a
    >
  {:else}
    <span class="assoc-cls">{name}</span>
  {/if}
{/snippet}

{#snippet hashCell(l: LinkedEntry)}
  <span class="assoc-hash">{l.state_hash ? l.state_hash.slice(0, 6) : ''}</span>
{/snippet}

{#snippet item(l: LinkedEntry, body: Snippet)}
  {@const hash = l.state_hash}
  {#if hash}
    <div
      class="assoc-item assoc-item--link"
      role="button"
      tabindex="0"
      title={fullText(l.params_summary ?? {}) || undefined}
      onclick={() => onEntry(hash, l.class_name)}
      onkeydown={(ev) => ev.key === 'Enter' && onEntry(hash, l.class_name)}
    >
      {@render body()}
    </div>
  {:else}
    <div class="assoc-item" title={fullText(l.params_summary ?? {}) || undefined}>{@render body()}</div>
  {/if}
{/snippet}

<div class="assoc">
  {#each groups as g, gi (gi)}
    {@const shown = expanded[gi] ? g.items : g.items.slice(0, LIMIT)}
    {#if g.flat}
      <div class="assoc-hd">
        <span class="assoc-title">{@render cls(g.className)}<span class="assoc-sub">×{g.items.length}</span></span>
        <span class="assoc-sub assoc-sub--key">{sharedKey(g)}</span>
      </div>
      {#each shown as l, i (i)}
        {@const value = summarize(l.params_summary ?? {})[0]?.value ?? ''}
        {#snippet flatRow()}
          <span class="assoc-k">{l.param_name || '—'}</span>
          <span class="assoc-v">{value}</span>
          {@render hashCell(l)}
        {/snippet}
        {@render item(l, flatRow)}
      {/each}
    {:else}
      {#each shown as l, i (i)}
        {@const parts = summarize(l.params_summary ?? {})}
        {#snippet block()}
          <span class="assoc-title assoc-title--item">
            {@render cls(l.class_name)}<span class="assoc-sub">{l.param_name}</span>
          </span>
          {@render hashCell(l)}
          {#each parts as p (p.key)}
            <span class="assoc-k">{p.key}</span>
            <span class="assoc-v">{p.value}</span>
            <span></span>
          {/each}
        {/snippet}
        {@render item(l, block)}
      {/each}
    {/if}
    {#if g.items.length > LIMIT}
      <button class="assoc-more" onclick={() => (expanded[gi] = !expanded[gi])}>
        {expanded[gi] ? 'Show fewer' : `Show ${g.items.length - LIMIT} more`}
      </button>
    {/if}
  {/each}
</div>

<style>
  /* One grid for the whole card so keys, values and hashes line up across entries. */
  .assoc {
    display: grid;
    grid-template-columns: minmax(0, max-content) minmax(0, 1fr) auto;
    column-gap: 14px;
    font-size: 11px;
    line-height: 1.55;
  }
  .assoc-hd,
  .assoc-item {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: subgrid;
    padding: 0 6px;
    border-radius: 5px;
  }
  .assoc-hd {
    margin-top: 12px;
    padding-bottom: 2px;
  }
  .assoc-hd:first-child,
  .assoc-item:first-child {
    margin-top: 0;
  }
  .assoc-item:has(.assoc-title--item) {
    margin-top: 12px;
    padding-bottom: 2px;
  }
  .assoc-item--link {
    cursor: pointer;
  }
  .assoc-item--link:hover {
    background: var(--s2);
  }
  .assoc-title {
    grid-column: 1 / 3;
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }
  .assoc-hd .assoc-title {
    grid-column: 1;
  }
  .assoc-cls {
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
  }
  a.assoc-cls:hover {
    color: var(--accent);
  }
  .assoc-sub {
    color: var(--faint);
    font-family: var(--mono);
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .assoc-sub--key {
    grid-column: 2 / -1;
    align-self: baseline;
  }
  .assoc-k {
    padding-left: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .assoc-v {
    font-family: var(--mono);
    color: var(--text);
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    overflow: hidden;
  }
  .assoc-hash {
    grid-column: 3;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--faint);
    align-self: baseline;
  }
  .assoc-item--link .assoc-hash {
    color: var(--accent);
  }
  .assoc-more {
    grid-column: 1 / -1;
    justify-self: start;
    margin: 2px 0 0 18px;
    padding: 0;
    border: none;
    background: none;
    font-size: 11px;
    color: var(--accent);
    cursor: pointer;
  }
  .assoc-more:hover {
    text-decoration: underline;
  }
</style>
