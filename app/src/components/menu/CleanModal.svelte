<script lang="ts">
  import { api } from '../../lib/api';
  import { app, pollStatus } from '../../lib/stores.svelte';
  import { toast } from '../detail/toast.svelte';

  let {
    kind,
    onClose,
  }: {
    kind: 'cache' | 'source';
    onClose: () => void;
  } = $props();

  const isSource = $derived(kind === 'source');
  const title = $derived(isSource ? 'Clean Source Registry' : 'Clean Cache');

  type Phase = 'dry' | 'ready' | 'confirm' | 'running' | 'cleaned' | 'error';
  let phase = $state<Phase>('dry');
  let lines = $state<string[]>([]);
  let error = $state('');

  async function runClean(dryRun: boolean): Promise<void> {
    if (dryRun) phase = 'dry';
    else phase = 'running';
    try {
      const res = isSource ? await api.cleanSource(dryRun) : await api.cleanCache(dryRun);
      lines = res.lines;
      if (dryRun) phase = 'ready';
      else {
        phase = 'cleaned';
        // Backend already started a reload; pick it up like the Reload menu item does.
        app.loading = true;
        app.ready = false;
        pollStatus();
      }
    } catch (err) {
      error = String(err);
      phase = 'error';
    }
  }

  function confirmClean(): void {
    phase = 'confirm';
  }

  function cancelConfirm(): void {
    phase = 'ready';
  }

  const outputText = $derived.by(() => {
    if (phase === 'dry') return 'Running dry-run preview…';
    if (phase === 'error') return `Error: ${error}`;
    if (lines.length === 0) return '(nothing to clean)';
    return lines.join('\n');
  });

  const cleanDisabled = $derived(lines.length === 0);

  void runClean(true);

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div
  class="modal"
  role="dialog"
  aria-modal="true"
  aria-label={title}
  tabindex="-1"
  onclick={(e) => {
    if (e.target === e.currentTarget) onClose();
  }}
  onkeydown={(e) => {
    if (e.key === 'Escape') onClose();
  }}
>
  <div class="card">
    <div class="hd">
      <span class="title">{title}</span>
      <button class="close" aria-label="Close" onclick={onClose}>×</button>
    </div>

    <div class="body">
      {#if isSource}
        <p class="desc">
          Removes orphaned code snapshots and dependency trees from <code>.source/</code>. Keeps the
          latest snapshot per class and anything referenced by a live cache entry.
        </p>
      {:else}
        <p class="desc">
          Removes stale or invalid cache entries from disk, then prunes empty directories and the
          catalog.
        </p>
      {/if}

      <pre class="output mono" class:err={phase === 'error'}>{outputText}</pre>

      {#if phase === 'confirm'}
        <p class="warn">
          This will permanently delete the files listed above. Continue?
        </p>
      {:else if phase === 'cleaned'}
        <p class="ok">Cleaned — reloading the dashboard…</p>
      {/if}
    </div>

    <div class="ft">
      {#if phase === 'confirm'}
        <button class="btn" onclick={cancelConfirm}>Cancel</button>
        <button class="btn btn--danger" onclick={() => void runClean(false)}>Clean now</button>
      {:else if phase === 'ready'}
        <button class="btn" onclick={onClose}>Close</button>
        <button class="btn btn--danger" disabled={cleanDisabled} onclick={confirmClean}>
          Clean
        </button>
      {:else if phase === 'error'}
        <button class="btn" onclick={onClose}>Close</button>
        <button class="btn" onclick={() => void runClean(true)}>Retry dry run</button>
      {:else}
        <button class="btn" onclick={onClose}>Close</button>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal {
    position: fixed;
    inset: 0;
    background: var(--backdrop);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: var(--s-4);
  }

  .card {
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    box-shadow: var(--shadow-md);
    width: min(640px, 100%);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .hd {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--border);
  }

  .title {
    font-size: var(--fs-sm);
    font-weight: 600;
  }

  .close {
    flex: none;
    width: 22px;
    height: 22px;
    border-radius: var(--r-sm);
    color: var(--text-3);
    font-size: var(--fs-md);
    line-height: 1;
  }

  .close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .body {
    min-height: 0;
    overflow: auto;
    padding: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .desc {
    margin: 0;
    font-size: var(--fs-sm);
    color: var(--text-2);
  }

  .desc code {
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    background: var(--bg-hover);
    border-radius: var(--r-xs);
    padding: 0 4px;
  }

  .output {
    margin: 0;
    max-height: 40vh;
    overflow: auto;
    padding: var(--s-2) var(--s-3);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--code-bg);
    font-size: var(--fs-xs);
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .output.err {
    color: var(--danger);
  }

  .warn {
    margin: 0;
    font-size: var(--fs-sm);
    color: var(--warning);
  }

  .ok {
    margin: 0;
    font-size: var(--fs-sm);
    color: var(--success);
  }

  .ft {
    display: flex;
    justify-content: flex-end;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-3);
    border-top: 1px solid var(--border);
  }

  .btn {
    padding: 3px 12px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text-2);
    font-size: var(--fs-sm);
    line-height: 1.4;
    white-space: nowrap;
  }

  .btn:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .btn--danger {
    color: var(--danger);
  }

  .btn--danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--danger) 12%, transparent);
    color: var(--danger);
  }
</style>
