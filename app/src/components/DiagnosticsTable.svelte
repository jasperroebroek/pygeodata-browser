<script lang="ts">
  import { classesState } from '../lib/stores.svelte';

  const counts = $derived(classesState.counts);
  const diag = $derived(classesState.diagnostics);
  const catalog = $derived(classesState.catalog);
  const roots = $derived(catalog?.unavailable_roots ?? []);

  const stamp = (epochSeconds: number) => new Date(epochSeconds * 1000).toLocaleString();

  type Row = { label: string; value: number | string; warn?: boolean };

  const catalogRows = $derived.by((): Row[] => {
    if (!catalog) return [];
    const w = catalog.writer;
    return [
      { label: 'Mode', value: `${catalog.mode} (${catalog.reason})` },
      { label: 'Written from', value: w.root },
      { label: 'Host', value: w.host },
      { label: 'Written', value: stamp(w.written_at) },
      { label: 'pygeodata / Python', value: `${w.pygeodata} / ${w.python}` },
      { label: 'Catalog id', value: catalog.catalog_id },
      { label: 'Pins file', value: catalog.pins_path },
      { label: 'Thumbnails', value: catalog.thumbs_path },
      { label: 'Entries with absolute dir paths', value: catalog.absolute_dir_entries },
    ];
  });

  const sections = $derived([
    ...(catalogRows.length ? [{ title: 'Catalog', rows: catalogRows }] : []),
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
        { label: 'Offline entries', value: diag.offline_entries ?? 0, warn: true },
        ...((diag.stale_hidden ?? 0) > 0 ? [{ label: 'Stale entries hidden', value: diag.stale_hidden }] : []),
      ],
    },
    ...(roots.length
      ? [
          {
            title: 'Unavailable cache roots',
            rows: roots.map((r) => ({
              label: r.name,
              value: `${r.path}: ${r.entries} ${r.entries === 1 ? 'entry' : 'entries'}, since ${stamp(r.since)}`,
              warn: true,
            })),
          },
        ]
      : []),
  ] as { title: string; rows: Row[] }[]);
</script>

<table class="diag-table">
  <colgroup><col style="width: 230px" /><col /></colgroup>
  <tbody>
    {#each sections as s (s.title)}
      <tr class="diag-section-row"><td colspan="2">{s.title}</td></tr>
      {#each s.rows as r (r.label)}
        <tr class:diag-warn={r.warn && (typeof r.value === 'string' || r.value > 0)}>
          <td class="diag-label">{r.label}</td>
          <td class="diag-val" class:diag-val--text={typeof r.value === 'string'}>{r.value}</td>
        </tr>
      {/each}
    {/each}
  </tbody>
</table>
