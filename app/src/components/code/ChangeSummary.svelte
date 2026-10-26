<script lang="ts">
  import { untrack } from 'svelte';
  import { codeApi, type DiffPayload, type SnapshotPayload, type VersionChange } from '../../lib/apiCode';
  import DiffTable from './DiffTable.svelte';
  import SnapshotTable from './SnapshotTable.svelte';

  let {
    changes,
    mode = 'inline',
    expand = 'hunks',
    onLink,
    onDiff,
  }: {
    changes: VersionChange[];
    mode?: 'inline' | 'split';
    expand?: 'hunks' | 'full';
    onLink?: (cls: string) => void;
    onDiff?: (cls: string, diff: DiffPayload | null) => void;
  } = $props();

  const STATUS_ORDER: Record<string, number> = { changed: 0, added: 1, unchanged: 2, removed: 3 };

  const sorted = $derived(
    [...changes].sort((a, b) => (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99)),
  );

  let open = $state<Record<string, boolean>>({});
  let cardData = $state<Record<string, DiffPayload | SnapshotPayload | 'error'>>({});
  let cardEpoch = 0;
  const pending = new Set<string>();

  $effect(() => {
    const list = changes;
    cardEpoch += 1;
    const epoch = cardEpoch;
    const initial: Record<string, boolean> = {};
    for (const c of list) if (c.status === 'changed') initial[c.class_name] = true;
    open = initial;
    cardData = {};
    pending.clear();
    untrack(() => {
      for (const c of list) if (initial[c.class_name]) void loadCard(c, epoch);
    });
  });

  async function loadCard(c: VersionChange, epoch: number) {
    const key = c.class_name;
    if (cardData[key] || pending.has(key)) return;
    pending.add(key);
    try {
      if (c.hash_old && c.hash_new && c.status !== 'unchanged') {
        const diff = await codeApi.diff(c.hash_old, c.hash_new, true);
        if (epoch === cardEpoch) {
          cardData[key] = diff;
          onDiff?.(key, diff);
        }
      } else {
        const snap = await codeApi.snapshot(c.hash_new || c.hash_old || '');
        if (epoch === cardEpoch) cardData[key] = snap;
      }
    } catch {
      if (epoch === cardEpoch) cardData[key] = 'error';
    } finally {
      pending.delete(key);
    }
  }

  function toggle(c: VersionChange) {
    const canExpand =
      (c.status === 'changed' && !!(c.hash_old && c.hash_new)) ||
      ((c.status === 'added' || c.status === 'unchanged') && !!c.hash_new) ||
      (c.status === 'removed' && !!c.hash_old);
    if (!canExpand) return;
    open[c.class_name] = !open[c.class_name];
    if (open[c.class_name]) {
      void loadCard(c, cardEpoch);
    } else if (cardData[c.class_name] && cardData[c.class_name] !== 'error') {
      onDiff?.(c.class_name, null);
    }
  }
</script>

<div class="summary">
  {#each sorted as c (c.class_name)}
    {@const canExpand =
      (c.status === 'changed' && !!(c.hash_old && c.hash_new)) ||
      ((c.status === 'added' || c.status === 'unchanged') && !!c.hash_new) ||
      (c.status === 'removed' && !!c.hash_old)}
    <div class="card {c.status}" class:open={open[c.class_name]}>
      <button class="head" onclick={() => toggle(c)} class:plain={!canExpand}>
        <span class="status">{c.status}</span>
        <span class="name">{c.class_name}</span>
        {#if canExpand}<span class="chev" class:up={open[c.class_name]}>▸</span>{/if}
      </button>
      {#if open[c.class_name]}
        {@const data = cardData[c.class_name]}
        <div class="body">
          {#if data === undefined}
            <div class="loading">Loading…</div>
          {:else if data === 'error'}
            <div class="error">Source unavailable</div>
          {:else if 'hunks' in data}
            <DiffTable diff={data} {mode} {expand} />
          {:else}
            <SnapshotTable snapshot={data} {onLink} />
          {/if}
        </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .summary {
    padding: var(--s-2);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .card {
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    overflow: hidden;
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    width: 100%;
    text-align: left;
    padding: 6px 10px;
    font-size: var(--fs-sm);
  }

  .head:not(.plain):hover {
    background: var(--bg-hover);
  }

  .head.plain {
    cursor: default;
  }

  .status {
    font-size: var(--fs-xs);
    padding: 1px 8px;
    border-radius: var(--r-full);
    flex: none;
    min-width: 74px;
    text-align: center;
  }

  .card.changed .status {
    background: color-mix(in srgb, var(--warning) 14%, transparent);
    color: var(--warning);
  }

  .card.added .status {
    background: color-mix(in srgb, var(--success) 14%, transparent);
    color: var(--success);
  }

  .card.removed .status {
    background: color-mix(in srgb, var(--danger) 14%, transparent);
    color: var(--danger);
  }

  .card.unchanged .status {
    background: var(--bg-hover);
    color: var(--text-3);
  }

  .name {
    flex: 1;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
  }

  .chev {
    color: var(--text-3);
    font-size: var(--fs-xs);
    transition: transform var(--t-fast) var(--ease);
  }

  .chev.up {
    transform: rotate(90deg);
  }

  .body {
    border-top: 1px solid var(--border);
    background: var(--bg-panel);
    overflow-x: auto;
  }

  .loading,
  .error {
    padding: var(--s-2) var(--s-3);
    color: var(--text-3);
    font-size: var(--fs-sm);
  }

  .error {
    color: var(--danger);
  }
</style>
