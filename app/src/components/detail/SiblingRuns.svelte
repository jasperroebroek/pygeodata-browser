<script lang="ts">
  import type { SameInstanceRun } from '../../lib/api';
  import type { SameInstanceRunFull } from './apiDetail';
  import { selectEntry } from '../../lib/stores.svelte';

  let { runs }: { runs: SameInstanceRun[] } = $props();

  const full = $derived(runs as SameInstanceRunFull[]);

  function specParts(s: SameInstanceRunFull): string[] {
    return [s.spec?.crs, s.spec?.resolution, s.spec?.shape, s.spec?.bounds_display].filter(
      (v): v is string => Boolean(v),
    );
  }
</script>

<div class="dcard-hd">
  <span class="dcard-hd-label">Sibling entries</span>
</div>
<div class="dcard-body">
  {#each full as s (s.record_id)}
    <div class="link-row">
      <div class="link-row-top">
        <button class="link-entry-name" onclick={() => selectEntry(s.record_id)}>
          {s.class_name}
        </button>
        <span class="link-spec-right">
          {#each specParts(s) as part (part)}
            <span class="spec-pill">{part}</span>
          {/each}
        </span>
      </div>
    </div>
  {/each}
</div>
