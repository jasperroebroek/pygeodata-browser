<script lang="ts">
  import type { LinkedEntry } from '../../lib/api';
  import type { LinkedEntryFull } from './apiDetail';
  import { selectEntry } from '../../lib/stores.svelte';

  let { links }: { links: LinkedEntry[] } = $props();

  function summary(le: LinkedEntry): Record<string, string> {
    // api.ts narrows params_summary to a string; the backend sends a map.
    const full = le as unknown as LinkedEntryFull;
    return typeof full.params_summary === 'string'
      ? {}
      : (full.params_summary as Record<string, string> | undefined) ?? {};
  }

  function jump(le: LinkedEntry): void {
    if (le.state_hash) selectEntry(le.state_hash);
  }
</script>

<div class="dcard-body">
  {#each links as le, i (i)}
    <div class="link-row">
      <div class="link-row-top">
        <span class="link-param-name">{le.param_name || '—'}</span>
        {#if le.state_hash}
          <button class="link-entry-name" title={le.state_hash} onclick={() => jump(le)}>
            {le.class_name}
          </button>
          <span class="link-hash" title={le.state_hash}>{le.state_hash.slice(0, 6)}</span>
        {:else}
          <span class="link-entry-name link-entry-name--plain">{le.class_name}</span>
        {/if}
      </div>
      {#if Object.keys(summary(le)).length > 0}
        <div class="link-params">
          {#each Object.entries(summary(le)) as [k, v]}
            <div class="link-param-line">
              <span class="link-param-key">{k}</span>
              <span class="link-param-val">{v}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/each}
</div>
