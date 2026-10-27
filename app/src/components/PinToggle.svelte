<script lang="ts">
  import Pin from '@lucide/svelte/icons/pin';
  import { isPinned, setPinned } from '../lib/stores.svelte';

  /** Row pin toggle: always shown when pinned, on row hover otherwise (see .entry-pin in table.css). */
  let { entry }: { entry: { record_id: string; class_name: string; object_type?: string | null } } = $props();

  const pinned = $derived(isPinned(entry.record_id));
</script>

<button
  class="icon-btn icon-btn--xs entry-pin"
  class:active={pinned}
  title={pinned ? 'Unpin this entry' : 'Pin this entry'}
  aria-label={pinned ? 'Unpin' : 'Pin'}
  aria-pressed={pinned}
  onclick={(e) => {
    e.stopPropagation();
    void setPinned({ record_id: entry.record_id, class_name: entry.class_name, object_type: entry.object_type ?? null }, !pinned);
  }}
>
  <Pin size={13} fill={pinned ? 'currentColor' : 'none'} />
</button>
