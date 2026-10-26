<script lang="ts">
  import { api } from '../lib/api';
  import { closeModal } from '../lib/modal.svelte';
  import { followServerReload } from '../lib/stores.svelte';

  let { target }: { target: 'cache' | 'source' } = $props();

  // Always preview first (dry run); deleting needs an explicit second confirmation.
  type Phase = 'previewing' | 'ready' | 'confirm' | 'running' | 'done' | 'error';
  let phase = $state<Phase>('previewing');
  let lines = $state<string[]>([]);
  let error = $state('');

  async function run(dryRun: boolean) {
    phase = dryRun ? 'previewing' : 'running';
    try {
      const res = target === 'source' ? await api.cleanSource(dryRun) : await api.cleanCache(dryRun);
      lines = res.lines;
      phase = dryRun ? 'ready' : 'done';
      if (!dryRun) followServerReload();
    } catch (err) {
      error = String(err);
      phase = 'error';
    }
  }

  void run(true);

  const output = $derived(
    phase === 'previewing'
      ? 'Running dry run…'
      : phase === 'running'
        ? 'Cleaning…'
        : phase === 'error'
          ? `Error: ${error}`
          : lines.length
            ? lines.join('\n')
            : '(nothing to clean)',
  );
</script>

<div class="clean-cache-modal">
  {#if target === 'source'}
    <p class="clean-cache-desc">
      Removes orphaned code snapshots and dependency trees from <code>.source/</code>. Keeps the latest snapshot per
      class and anything referenced by a live cache entry.
    </p>
  {:else}
    <p class="clean-cache-desc">Removes stale or invalid cache entries from disk. Below is a dry-run preview.</p>
  {/if}
  <pre class="clean-cache-output">{output}</pre>
  <div class="clean-cache-footer">
    {#if phase === 'ready' && lines.length}
      <button class="act-btn act-btn--danger" onclick={() => (phase = 'confirm')}>Clean…</button>
    {:else if phase === 'confirm'}
      <span class="clean-cache-confirm">Permanently delete the files listed above?</span>
      <button class="act-btn" onclick={() => (phase = 'ready')}>Cancel</button>
      <button class="act-btn act-btn--danger" onclick={() => void run(false)}>Delete</button>
    {:else if phase === 'error'}
      <button class="act-btn" onclick={() => void run(true)}>Retry dry run</button>
    {:else if phase === 'done'}
      <button class="act-btn" onclick={closeModal}>Close</button>
    {/if}
  </div>
</div>
