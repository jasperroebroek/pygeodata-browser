<script lang="ts">
  import Box from '@lucide/svelte/icons/box';
  import ChartColumn from '@lucide/svelte/icons/chart-column';
  import Layers from '@lucide/svelte/icons/layers';
  import Table from '@lucide/svelte/icons/table';

  let { type, size = 15 }: { type: string | null | undefined; size?: number } = $props();

  const ICONS = { data: Layers, table: Table, figure: ChartColumn };
  const kind = $derived((type ?? '').toLowerCase());
  const Icon = $derived(ICONS[kind as keyof typeof ICONS] ?? Box);
</script>

<span class="kind-icon kind-icon--{kind || 'none'}" title={type ?? 'unknown'}><Icon {size} /></span>
