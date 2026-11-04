<script lang="ts">
  import { classesState } from '../lib/stores.svelte';

  const roots = $derived(classesState.catalog?.unavailable_roots ?? []);
</script>

{#if roots.length > 0}
  <div class="offline-banner" role="status">
    {#each roots as r (r.path)}
      <div>
        <strong>Cache root unavailable:</strong>
        {r.name} ({r.path}) — missing or empty. {r.entries}
        {r.entries === 1 ? 'entry is' : 'entries are'} shown from the catalog; their files can't be checked.
      </div>
    {/each}
  </div>
{/if}

<style>
  .offline-banner {
    flex: 0 0 auto;
    padding: 6px 14px;
    font-size: 12px;
    color: var(--muted);
    background: var(--s2);
    border-bottom: 1px solid var(--border);
  }
</style>
