<script lang="ts">
  import { untrack } from 'svelte';
  import { codeApi, type DiffPayload, type SnapshotPayload, type VersionChange } from '../../lib/apiCode';
  import DiffTable from './DiffTable.svelte';
  import SnapshotTable from './SnapshotTable.svelte';

  let {
    changes,
    mode = 'inline',
    expand = 'hunks',
    scrollToClass = null,
    onLink,
    onDiff,
  }: {
    changes: VersionChange[];
    mode?: 'inline' | 'split';
    expand?: 'hunks' | 'full';
    scrollToClass?: string | null;
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
  let wrapEl: HTMLElement | undefined = $state();

  function canExpand(c: VersionChange): boolean {
    return (
      (c.status === 'changed' && !!(c.hash_old && c.hash_new)) ||
      ((c.status === 'added' || c.status === 'unchanged') && !!c.hash_new) ||
      (c.status === 'removed' && !!c.hash_old)
    );
  }

  $effect(() => {
    const list = changes;
    cardEpoch += 1;
    const epoch = cardEpoch;
    const initial: Record<string, boolean> = {};
    for (const c of list) if (c.status === 'changed' && canExpand(c)) initial[c.class_name] = true;
    open = initial;
    cardData = {};
    pending.clear();
    untrack(() => {
      for (const c of list) if (initial[c.class_name]) void loadCard(c, epoch);
      if (scrollToClass) {
        queueMicrotask(() =>
          wrapEl
            ?.querySelector(`.tree-diff-class[data-class="${CSS.escape(scrollToClass!)}"]`)
            ?.scrollIntoView({ block: 'nearest' }),
        );
      }
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
    if (!canExpand(c)) return;
    open[c.class_name] = !open[c.class_name];
    if (open[c.class_name]) void loadCard(c, cardEpoch);
  }
</script>

<div class="tree-diff-container" bind:this={wrapEl}>
  {#each sorted as c (c.class_name)}
    {@const expandable = canExpand(c)}
    <div class="tree-diff-class {c.status}" class:open={open[c.class_name]} data-class={c.class_name}>
      <div class="tree-diff-header" role="button" tabindex="0" onclick={() => toggle(c)} onkeydown={(e) => e.key === 'Enter' && toggle(c)}>
        <span class="tree-diff-status">{c.status}</span>
        <span class="tree-diff-name">{c.class_name}</span>
        {#if expandable}<span class="tree-diff-expand">▶</span>{/if}
      </div>
      {#if expandable && open[c.class_name]}
        {@const data = cardData[c.class_name]}
        <div class="tree-diff-body">
          {#if data === undefined}
            <div class="diff-loading">Loading…</div>
          {:else if data === 'error'}
            <div class="diff-no-snapshot">Unavailable</div>
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
