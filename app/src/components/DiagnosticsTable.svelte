<script lang="ts">
  import Check from '@lucide/svelte/icons/check';
  import Copy from '@lucide/svelte/icons/copy';
  import Info from '@lucide/svelte/icons/info';
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
  import { copyText } from '../lib/actions';
  import { relativeTime } from '../lib/format';
  import { classesState } from '../lib/stores.svelte';

  const counts = $derived(classesState.counts);
  const diag = $derived(classesState.diagnostics);
  const catalog = $derived(classesState.catalog);

  const n = (value: number) => value.toLocaleString();
  const stamp = (epochSeconds: number) => new Date(epochSeconds * 1000).toLocaleString();
  const entries = (count: number) => `${n(count)} ${count === 1 ? 'entry' : 'entries'}`;

  const cacheOnly = $derived((counts?.classes ?? 0) - (counts?.classes_loaded ?? 0));
  const readOnly = $derived(catalog?.read_only ?? false);

  type HealthCheck = {
    label: string;
    count: number;
    status: 'ok' | 'warn' | 'info';
    explanation?: string;
    action?: string;
    lines?: string[];
    roots?: NonNullable<typeof catalog>['unavailable_roots'];
  };

  const unindexedParts = $derived.by(() => {
    const r = diag.unindexed_reasons;
    if (!r) return null;
    return [
      r.other_format && `${n(r.other_format)} written by an older cache format`,
      r.no_meta && `${n(r.no_meta)} without meta.json (interrupted runs)`,
      r.unreadable && `${n(r.unreadable)} with an unreadable meta.json`,
    ].filter((part): part is string => !!part);
  });

  const checks = $derived.by((): HealthCheck[] => {
    const unindexed = diag.unindexed_dirs ?? 0;
    const missing = diag.missing_dirs ?? 0;
    const roots = catalog?.unavailable_roots ?? [];
    const offline = diag.offline_entries ?? 0;
    const problems = diag.problems ?? [];
    const absolute = catalog?.absolute_dir_entries ?? 0;
    const warn = (count: number) => (count > 0 ? 'warn' : 'ok');

    const list: HealthCheck[] = [
      {
        label: 'Unindexed entry dirs',
        count: unindexed,
        status: warn(unindexed),
        explanation: unindexedParts
          ? `${unindexedParts.join(' · ')}. They are not used.`
          : 'Entry dirs on disk that the catalog does not list. A read-only mirror does not read them, so the reason is not known.',
        action: unindexedParts && !readOnly ? '`pygeodata clean-cache` lists and removes them.' : undefined,
      },
      {
        label: 'Missing entry dirs',
        count: missing,
        status: warn(missing),
        explanation: 'In the catalog but gone from disk.',
        action: readOnly
          ? 'They are pruned where the catalog is written; the mirror may be behind.'
          : '`pygeodata catalog build` prunes them.',
      },
      {
        label: 'Unavailable cache roots',
        count: roots.length,
        status: warn(roots.length),
        explanation: 'Missing or empty, so their entries are shown from the catalog and cannot be checked.',
        action: 'Mount the share or wait for the mirror to sync.',
        roots,
      },
      {
        label: 'Offline entries',
        count: offline,
        status: warn(offline),
        explanation: 'Entries in an unavailable cache root.',
      },
      {
        label: 'Analysis problems',
        count: problems.length,
        status: warn(problems.length),
        explanation: 'The project sources could not be fully read; classes in these files are left out.',
        lines: problems,
      },
    ];
    if (absolute > 0) {
      list.push({
        label: 'Entries with absolute dir paths',
        count: absolute,
        status: 'info',
        explanation: 'They live outside their cache root and do not resolve on another machine.',
      });
    }
    return list;
  });

  const details = $derived.by(() => {
    if (!catalog) return [];
    const w = catalog.writer;
    return [
      { label: 'Written from', value: w.root, mono: true, copy: true },
      { label: 'Host', value: w.host },
      { label: 'Written', value: `${stamp(w.written_at)} · ${relativeTime(w.written_at)}` },
      { label: 'pygeodata / Python', value: `${w.pygeodata} / ${w.python}` },
      { label: 'Catalog id', value: catalog.catalog_id, mono: true, copy: true },
      { label: 'Pins file', value: catalog.pins_path, mono: true, copy: true },
      { label: 'Thumbnails', value: catalog.thumbs_path, mono: true, copy: true },
    ];
  });

  // `code` spans in the explanations
  const parts = (text: string) => text.split(/`([^`]+)`/).map((value, i) => ({ value, code: i % 2 === 1 }));
</script>

{#snippet rich(text: string)}
  {#each parts(text) as p, i (i)}{#if p.code}<code>{p.value}</code>{:else}{p.value}{/if}{/each}
{/snippet}

<div class="diag">
  {#if catalog}
    <div class="diag-mode">
      <span class="badge {catalog.read_only ? 'badge-neutral' : 'badge-accent'}">
        {catalog.read_only ? 'Mirror · read-only' : 'Writable'}
      </span>
      <span class="diag-muted">{catalog.reason}</span>
    </div>
  {/if}

  <div class="diag-tiles">
    <div class="diag-tile">
      <span class="diag-tile-label">Classes</span>
      <span class="diag-tile-num">{n(counts?.classes ?? 0)}</span>
      {#if cacheOnly > 0}<span class="diag-tile-sub">{n(cacheOnly)} only in the cache</span>{/if}
    </div>
    <div class="diag-tile">
      <span class="diag-tile-label">Entries</span>
      <span class="diag-tile-num">{n(diag.entries ?? 0)}</span>
      <span class="diag-tile-sub">
        in the catalog{#if (diag.stale_hidden ?? 0) > 0} · {n(diag.stale_hidden ?? 0)} stale hidden{/if}
      </span>
    </div>
  </div>

  <h3 class="diag-h">Health</h3>
  <ul class="diag-checks">
    {#each checks as c (c.label)}
      <li class="diag-check diag-check--{c.status}">
        <div class="diag-check-row">
          {#if c.status === 'warn'}
            <span class="diag-ic diag-ic--warn" title="Needs attention"><TriangleAlert size={14} /></span>
          {:else if c.status === 'info'}
            <span class="diag-ic" title="For information"><Info size={14} /></span>
          {:else}
            <span class="diag-ic diag-ic--ok" title="OK"><Check size={14} /></span>
          {/if}
          <span class="diag-check-label">{c.label}</span>
          <span class="badge badge--sm {c.status === 'warn' ? 'badge-warn' : 'badge-neutral'} diag-count">{n(c.count)}</span>
        </div>
        {#if c.status !== 'ok'}
          <div class="diag-check-body">
            {#if c.explanation}<p>{@render rich(c.explanation)}</p>{/if}
            {#if c.action}<p>{@render rich(c.action)}</p>{/if}
            {#if c.roots?.length}
              <ul class="diag-lines">
                {#each c.roots as r (r.path)}
                  <li>
                    <span class="diag-mono">{r.path}</span>
                    <span class="diag-muted">· {entries(r.entries)} · since {relativeTime(r.since)}</span>
                  </li>
                {/each}
              </ul>
            {/if}
            {#if c.lines?.length}
              <ul class="diag-lines">
                {#each c.lines as line, i (i)}<li class="diag-mono">{line}</li>{/each}
              </ul>
            {/if}
          </div>
        {/if}
      </li>
    {/each}
  </ul>

  {#if details.length}
    <h3 class="diag-h">Catalog</h3>
    <dl class="diag-details">
      {#each details as d (d.label)}
        <dt>{d.label}</dt>
        <dd>
          <span class:diag-mono={d.mono}>{d.value}</span>
          {#if d.copy}
            <button class="act-btn diag-copy" title="Copy" aria-label="Copy {d.label}" onclick={() => void copyText(d.value)}>
              <Copy size={12} />
            </button>
          {/if}
        </dd>
      {/each}
    </dl>
  {/if}
</div>

<style>
  .diag {
    font-size: 13px;
    color: var(--text);
  }
  .diag-muted {
    color: var(--muted);
    font-size: 12px;
  }
  .diag-mono,
  code {
    font-family: var(--mono);
    font-size: 11.5px;
    overflow-wrap: anywhere;
  }
  code {
    padding: 0 4px;
    border-radius: 3px;
    background: var(--s3);
  }

  .diag-mode {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 10px;
    margin-bottom: 14px;
  }

  .diag-tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
  }
  .diag-tile {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 14px;
    background: var(--s2);
    border: 1px solid var(--border-s);
    border-radius: 10px;
  }
  .diag-tile-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--faint);
  }
  .diag-tile-num {
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
  }
  .diag-tile-sub {
    font-size: 11px;
    color: var(--muted);
  }

  .diag-h {
    margin: 20px 0 6px;
    padding-bottom: 5px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--faint);
    border-bottom: 1px solid var(--border-s);
  }

  .diag-checks,
  .diag-lines {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .diag-check {
    padding: 6px 0;
  }
  .diag-check--warn {
    margin: 4px 0;
    padding: 8px 10px;
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 8px;
  }
  .diag-check-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .diag-check-label {
    flex: 1;
    color: var(--text);
  }
  .diag-check--ok .diag-check-label {
    color: var(--muted);
  }
  .diag-ic {
    display: inline-flex;
    color: var(--faint);
  }
  .diag-ic--warn {
    color: var(--warn);
  }
  .diag-count {
    font-variant-numeric: tabular-nums;
  }
  .diag-check-body {
    margin: 4px 0 0 22px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--muted);
  }
  .diag-check-body p {
    margin: 0 0 2px;
  }
  .diag-lines {
    margin-top: 4px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: var(--text);
  }

  .diag-details {
    display: grid;
    grid-template-columns: 150px minmax(0, 1fr);
    gap: 6px 12px;
    margin: 0;
  }
  .diag-details dt {
    color: var(--muted);
  }
  .diag-details dd {
    margin: 0;
    min-width: 0;
  }
  .diag-copy {
    display: inline-flex;
    vertical-align: middle;
    padding: 2px 4px;
    margin-left: 2px;
    color: var(--faint);
  }
</style>
