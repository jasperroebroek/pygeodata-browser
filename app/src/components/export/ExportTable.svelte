<script lang="ts">
  import type { TableRow } from '../../lib/api';

  interface Props {
    rows: TableRow[];
    exportIds: Set<string>;
    hoverId: string | null;
    onToggle: (recordId: string) => void;
    onDownload: (recordId: string) => void;
    onHover: (recordId: string | null) => void;
  }

  let { rows, exportIds, hoverId, onToggle, onDownload, onHover }: Props = $props();

  function specParts(row: TableRow): string[] {
    const spec = row.spec;
    if (!spec) return [];
    return [spec.crs, spec.resolution_display, spec.shape, spec.bounds_display].filter(
      (s): s is string => Boolean(s),
    );
  }

  function scopeText(row: TableRow): string {
    return row.group && row.group !== '---' ? row.group : '';
  }

  function isRef(row: TableRow): boolean {
    return row.param_row_type === 'data_ref' || row.param_row_type === 'class_ref';
  }
</script>

<div class="scroll-table">
  <table>
    <thead>
      <tr>
        <th class="col-indent"></th>
        <th class="col-scope">Scope</th>
        <th class="col-param">Parameter</th>
        <th class="col-value">Value</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row, i}
        {#if row.row_type === 'header'}
          {@const included = exportIds.has(row.record_id)}
          <tr
            class="row-entry"
            class:in={included}
            class:hover={hoverId === row.record_id}
            onmouseenter={() => onHover(row.record_id)}
            onmouseleave={() => onHover(null)}
          >
            <td colspan="4" class="cell-entry-hd">
              <div class="cell-entry-hd-inner">
                <button
                  class="icon-btn toggle-btn"
                  class:in={included}
                  title={included ? 'Remove from export' : 'Add to export'}
                  aria-label={included ? 'Remove from export' : 'Add to export'}
                  onclick={(e) => {
                    e.stopPropagation();
                    onToggle(row.record_id);
                  }}
                ></button>
                <button
                  class="icon-btn dl-btn"
                  title="Download this entry"
                  aria-label="Download this entry"
                  onclick={(e) => {
                    e.stopPropagation();
                    onDownload(row.record_id);
                  }}
                ></button>
                <span class="entry-cls">{row.class_name}</span>
                {#if row.object_type}
                  <span class="badge kind-{row.object_type.toLowerCase()}">{row.object_type}</span>
                {/if}
                {#if row.format_version_stale}
                  <span class="badge badge--danger" title="pygeodata version changed — entry must be regenerated">version</span>
                {:else if row.dep_hash_stale}
                  <span class="badge badge--warn" title="Dependencies changed — entry may be outdated">stale</span>
                {/if}
                {#if row.warning_count}
                  <span class="badge badge--warn">{row.warning_count}w</span>
                {/if}
                {#if row.error}
                  <span class="badge badge--danger" title={row.error}>!</span>
                {/if}
                <span class="cell-entry-spec">
                  {#each specParts(row) as part}
                    <span class="spec-pill">{part}</span>
                  {/each}
                </span>
              </div>
            </td>
          </tr>
        {:else}
          {@const included = exportIds.has(row.record_id)}
          {@const next = rows[i + 1]}
          <tr
            class="row-param"
            class:in={included}
            class:hover={hoverId === row.record_id}
            class:entry-last={!next || next.row_type === 'header'}
            onmouseenter={() => onHover(row.record_id)}
            onmouseleave={() => onHover(null)}
          >
            <td class="col-indent"></td>
            <td class="col-scope">{scopeText(row)}</td>
            <td class="col-param">{row.parameter ?? ''}</td>
            <td class="col-value" class:ref={isRef(row)}>{row.value ?? ''}</td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>

<style>
  .scroll-table {
    min-width: 100%;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--bg-elev);
    text-align: left;
    font-weight: 500;
    font-size: var(--fs-xs);
    color: var(--text-3);
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--border-strong);
    white-space: nowrap;
  }

  td {
    padding: 3px var(--s-3);
    vertical-align: top;
  }

  .col-indent {
    width: 12px;
  }

  .col-scope {
    width: 18%;
  }

  .col-param {
    width: 28%;
  }

  .col-scope,
  .col-param {
    color: var(--text-3);
    overflow-wrap: break-word;
  }

  .col-value {
    color: var(--text-2);
    overflow-wrap: anywhere;
  }

  .col-value.ref {
    color: var(--link);
  }

  .row-entry td {
    border-top: 1px solid var(--border-strong);
    background: var(--bg-elev);
  }

  thead + tbody .row-entry td,
  .row-param + .row-entry td {
    border-top-width: 1px;
  }

  .row-entry.in td {
    background: var(--bg-selected);
  }

  .row-param td {
    border-top: 1px solid var(--border);
    background: var(--bg-elev);
  }

  .row-param.in td {
    background: var(--accent-softer);
  }

  .row-param.entry-last td {
    border-bottom: 1px solid var(--border);
  }

  tr.hover td {
    background: var(--bg-hover);
  }

  .cell-entry-hd-inner {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 2px 0;
    font-family: var(--font-ui);
    font-size: var(--fs-sm);
  }

  .entry-cls {
    font-weight: 600;
    color: var(--text);
    font-family: var(--font-ui);
  }

  .badge {
    display: inline-flex;
    align-items: center;
    padding: 0 6px;
    border-radius: var(--r-full);
    font-size: var(--fs-xs);
    line-height: 16px;
    background: var(--bg-hover);
    color: var(--text-2);
    white-space: nowrap;
  }

  .kind-data {
    background: color-mix(in srgb, var(--kind-data) 14%, transparent);
    color: var(--kind-data);
  }

  .kind-table {
    background: color-mix(in srgb, var(--kind-table) 14%, transparent);
    color: var(--kind-table);
  }

  .kind-figure {
    background: color-mix(in srgb, var(--kind-figure) 14%, transparent);
    color: var(--kind-figure);
  }

  .badge--warn {
    background: color-mix(in srgb, var(--warning) 14%, transparent);
    color: var(--warning);
  }

  .badge--danger {
    background: color-mix(in srgb, var(--danger) 14%, transparent);
    color: var(--danger);
  }

  .cell-entry-spec {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-left: auto;
  }

  .spec-pill {
    padding: 1px 8px;
    border-radius: var(--r-full);
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    background: var(--bg-hover);
    color: var(--text-2);
    white-space: nowrap;
  }

  .icon-btn {
    flex: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 1.5px solid var(--border-strong);
    background: none;
    cursor: pointer;
    position: relative;
    padding: 0;
    transition: border-color var(--t-fast) var(--ease), background var(--t-fast) var(--ease);
  }

  .icon-btn:hover {
    border-color: var(--accent);
  }

  /* plus sign */
  .toggle-btn::before,
  .toggle-btn::after {
    content: '';
    position: absolute;
    background: var(--text-3);
    border-radius: 1px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  .toggle-btn::before {
    width: 8px;
    height: 1.5px;
  }

  .toggle-btn::after {
    width: 1.5px;
    height: 8px;
  }

  .toggle-btn:hover::before,
  .toggle-btn:hover::after {
    background: var(--accent);
  }

  /* included: solid minus — vertical bar hidden */
  .toggle-btn.in {
    background: var(--accent-soft);
    border-color: var(--accent);
  }

  .toggle-btn.in::before {
    background: var(--accent);
  }

  .toggle-btn.in::after {
    display: none;
  }

  /* download arrow */
  .dl-btn::before {
    content: '';
    position: absolute;
    background: var(--text-3);
    border-radius: 1px;
    width: 1.5px;
    height: 6px;
    top: 3px;
    left: 50%;
    transform: translateX(-50%);
  }

  .dl-btn::after {
    content: '';
    position: absolute;
    border-left: 1.5px solid var(--text-3);
    border-bottom: 1.5px solid var(--text-3);
    width: 5px;
    height: 5px;
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%) rotate(-45deg);
  }

  .dl-btn:hover::before {
    background: var(--accent);
  }

  .dl-btn:hover::after {
    border-color: var(--accent);
  }
</style>
