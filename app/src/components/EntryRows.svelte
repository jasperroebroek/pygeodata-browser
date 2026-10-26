<script lang="ts">
  import type { TableRow } from '../lib/api';
  import { softBreak } from '../lib/format';
  import TypeBadge from './TypeBadge.svelte';

  // Card-style entry table body shared by the entries view and the export view.
  let {
    rows,
    activeId = null,
    inCart,
    onSelect = null,
    onToggleCart,
    onDownload,
  }: {
    rows: TableRow[];
    activeId?: string | null;
    inCart: (recordId: string) => boolean;
    onSelect?: ((recordId: string) => void) | null;
    onToggleCart: (recordId: string) => void;
    onDownload: (recordId: string) => void;
  } = $props();

  let hoverId = $state<string | null>(null);

  function specParts(row: TableRow): string[] {
    const s = row.spec;
    return s ? ([s.crs, s.resolution_display, s.shape, s.bounds_display].filter(Boolean) as string[]) : [];
  }

  function onRowOver(e: MouseEvent) {
    const row = (e.target as HTMLElement).closest<HTMLElement>('tr[data-entry]');
    if (row) hoverId = row.dataset.entry ?? null;
  }
</script>

<!-- svelte-ignore a11y_mouse_events_have_key_events (group hover is purely visual) -->
<tbody class="table-body" onmouseover={onRowOver} onmouseleave={() => (hoverId = null)}>
  {#each rows as r, i (r.row_type === 'header' ? `h:${r.record_id}` : `d:${r.record_id}:${i}`)}
    {@const active = r.record_id === activeId}
    {#if r.row_type === 'header'}
      {@const cart = inCart(r.record_id)}
      <tr
        class="row-entry"
        class:active
        class:row-hover={hoverId === r.record_id}
        class:selected-for-export={cart}
        data-entry={r.record_id}
        onclick={(e) => !(e.target as HTMLElement).closest('a') && onSelect?.(r.record_id)}
      >
        <td colspan="4" class="cell-entry-hd" style:cursor={onSelect ? null : 'default'}>
          <div class="cell-entry-hd-inner">
            <button
              class="select-icon"
              class:select-icon--in={cart}
              title={cart ? 'Remove from export' : 'Add to export'}
              aria-label={cart ? 'Remove from export' : 'Add to export'}
              onclick={(e) => {
                e.stopPropagation();
                onToggleCart(r.record_id);
              }}
            ></button>
            <button
              class="dl-icon"
              title="Download this entry"
              aria-label="Download this entry"
              onclick={(e) => {
                e.stopPropagation();
                onDownload(r.record_id);
              }}
            ></button>
            <span class="cell-entry-left">
              <span class="entry-cls">{r.class_name}</span>
              <TypeBadge type={r.object_type} small />
              {#if r.format_version_stale}
                <span class="badge badge--sm badge-danger" title="pygeodata version changed — entry must be regenerated">version</span>
              {:else if r.dep_hash_stale}
                <span class="badge badge--sm badge-warn" title="Dependencies changed — entry may be outdated">stale</span>
              {/if}
              {#if r.warning_count}<span class="badge badge--sm badge-warn" title={r.warnings?.join('\n')}>{r.warning_count}w</span>{/if}
              {#if r.error}<span class="badge badge--sm badge-danger" title={r.error}>!</span>{/if}
            </span>
            <span class="cell-entry-spec">
              {#each specParts(r) as part, j (j)}<span class="tbl-spec-pill">{part}</span>{/each}
            </span>
          </div>
        </td>
      </tr>
    {:else}
      {@const next = rows[i + 1]}
      <tr
        class="row-param"
        class:active
        class:row-hover={hoverId === r.record_id}
        class:entry-last={!next || next.row_type === 'header'}
        data-entry={r.record_id}
        onclick={() => onSelect?.(r.record_id)}
      >
        <td class="col-indent"></td>
        <td class="col-scope">{softBreak(r.group && r.group !== '---' ? r.group : '')}</td>
        <td class="col-param">{softBreak(r.parameter)}</td>
        <td class="col-value" class:col-value--ref={r.param_row_type === 'data_ref' || r.param_row_type === 'class_ref'}>
          {softBreak(r.value)}
        </td>
      </tr>
    {/if}
  {/each}
</tbody>
