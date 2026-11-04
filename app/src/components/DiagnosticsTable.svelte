<script lang="ts">
  import { classesState } from '../lib/stores.svelte';

  const counts = $derived(classesState.counts);
  const diag = $derived(classesState.diagnostics);
  const unavailableRoots = $derived((diag.unavailable_roots ?? []) as unknown as string[]);

  const sections = $derived([
    {
      title: 'Classes',
      rows: [
        { label: 'Total', value: counts?.classes ?? 0 },
        { label: 'In registry', value: counts?.classes_loaded ?? 0 },
        { label: 'Cache-only', value: (counts?.classes ?? 0) - (counts?.classes_loaded ?? 0), warn: true },
      ],
    },
    {
      title: 'Scan',
      rows: [
        { label: 'Entries created', value: diag.created_entries ?? 0 },
        { label: 'Unindexed entry dirs', value: diag.unindexed_dirs ?? 0, warn: true },
      ],
    },
    {
      title: 'Entry quality',
      rows: [
        { label: 'Missing entry dirs', value: diag.missing_dirs ?? 0, warn: true },
        { label: 'Unavailable cache roots', value: unavailableRoots.length, warn: true },
        ...((diag.stale_hidden ?? 0) > 0 ? [{ label: 'Stale entries hidden', value: diag.stale_hidden }] : []),
      ],
    },
  ]);
</script>

<table class="diag-table">
  <tbody>
    {#each sections as s (s.title)}
      <tr class="diag-section-row"><td colspan="2">{s.title}</td></tr>
      {#each s.rows as r (r.label)}
        <tr class:diag-warn={'warn' in r && r.warn && r.value > 0}>
          <td class="diag-label">{r.label}</td>
          <td class="diag-val">{r.value}</td>
        </tr>
      {/each}
    {/each}
  </tbody>
</table>
