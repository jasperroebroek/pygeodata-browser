<script lang="ts">
  let { type, small = false }: { type: string | null | undefined; small?: boolean } = $props();

  const kind = $derived((type ?? '').toLowerCase());
  const cls = $derived(['data', 'table', 'figure'].includes(kind) ? `badge-type-${kind}` : 'badge-neutral');
</script>

{#if type}
  <span class="badge {cls}" class:badge--sm={small}>{type}</span>
{:else}
  <span class="kv-nil">unknown</span>
{/if}
