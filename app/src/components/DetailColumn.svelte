<script lang="ts">
  import { app } from '../lib/stores.svelte';

  // Owned by the detail-view milestone: params tree, spec block, files,
  // linked entries, figure/table viewers.
</script>

<section class="detail">
  {#if app.payload?.detail?.selected_entry}
    <div class="stub">
      <h2>{app.payload.detail.selected_entry.class_name}</h2>
      <p class="mono">{app.payload.detail.selected_entry.record_id.slice(0, 16)}</p>
    </div>
  {:else if app.payload?.detail}
    <div class="stub">
      <h2>{app.payload.detail.class_name}</h2>
      <p>{app.payload.detail.object_type}</p>
    </div>
  {:else}
    <div class="stub">
      <p>Select an entry to inspect it.</p>
    </div>
  {/if}
</section>

<style>
  .detail {
    overflow-y: auto;
    background: var(--bg);
    min-height: 0;
  }

  .stub {
    padding: var(--s-4);
    color: var(--text-2);
  }

  h2 {
    margin: 0 0 4px;
    font-size: var(--fs-lg);
  }

  p {
    margin: 0;
    font-size: var(--fs-sm);
    color: var(--text-3);
  }
</style>
