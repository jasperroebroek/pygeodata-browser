<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { Component } from 'svelte';
  import Activity from '@lucide/svelte/icons/activity';
  import Code from '@lucide/svelte/icons/code';
  import FileDown from '@lucide/svelte/icons/file-down';
  import GitCommitVertical from '@lucide/svelte/icons/git-commit-vertical';
  import Hash from '@lucide/svelte/icons/hash';
  import List from '@lucide/svelte/icons/list';
  import ListTree from '@lucide/svelte/icons/list-tree';
  import Moon from '@lucide/svelte/icons/moon';
  import Monitor from '@lucide/svelte/icons/monitor';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';
  import Search from '@lucide/svelte/icons/search';
  import Sun from '@lucide/svelte/icons/sun';
  import Table2 from '@lucide/svelte/icons/table-2';
  import TimerOff from '@lucide/svelte/icons/timer-off';
  import { api } from '../lib/api';
  import type { FoundEntry } from '../lib/api';
  import { codeApi, isLoading } from '../lib/apiCode';
  import type { CodeVersion } from '../lib/apiCode';
  import { openModal } from '../lib/modal.svelte';
  import { navigateToCodeVersion, switchView } from '../lib/nav.svelte';
  import { palette } from '../lib/palette.svelte';
  import {
    classesState,
    filterState,
    navigateToClass,
    openEntry,
    setEntriesMode,
    setTheme,
    setView,
    startReload,
    toggleHideStale,
  } from '../lib/stores.svelte';
  import KindIcon from './KindIcon.svelte';

  type Item =
    | { kind: 'class'; key: string; label: string; type: string; count: number }
    | { kind: 'entry'; key: string; label: string; type: string | null; className: string }
    | { kind: 'version'; key: string; label: string; changed: number }
    | { kind: 'command'; key: string; label: string; icon: Component; run: () => void };

  const GROUP_LABEL: Record<Item['kind'], string> = {
    entry: 'Entries',
    class: 'Classes',
    version: 'Code versions',
    command: 'Commands',
  };
  const CLASS_LIMIT = 40;
  const HEX = /^[0-9a-f]{4,}$/;

  let q = $state('');
  let active = $state(0);
  let input: HTMLInputElement;
  let list: HTMLDivElement;
  let versions = $state<CodeVersion[]>([]);
  let found = $state<FoundEntry[]>([]);

  const commands: Item[] = [
    { kind: 'command', key: 'v-entries', label: 'Go to Entries', icon: ListTree, run: () => switchView('entries') },
    { kind: 'command', key: 'v-code', label: 'Go to Code', icon: Code, run: () => switchView('code') },
    { kind: 'command', key: 'v-export', label: 'Go to Export', icon: FileDown, run: () => switchView('export') },
    { kind: 'command', key: 'reload', label: 'Reload', icon: RefreshCw, run: () => void startReload() },
    { kind: 'command', key: 'compact', label: 'Compact entry list', icon: List, run: () => void setEntriesMode('compact') },
    { kind: 'command', key: 'detailed', label: 'Detailed entry table', icon: Table2, run: () => void setEntriesMode('detailed') },
    {
      kind: 'command',
      key: 'stale',
      label: 'Toggle hide stale entries',
      icon: TimerOff,
      run: () => void toggleHideStale(),
    },
    { kind: 'command', key: 't-light', label: 'Theme: Light', icon: Sun, run: () => setTheme('light') },
    { kind: 'command', key: 't-dark', label: 'Theme: Dark', icon: Moon, run: () => setTheme('dark') },
    { kind: 'command', key: 't-system', label: 'Theme: System', icon: Monitor, run: () => setTheme('system') },
    {
      kind: 'command',
      key: 'diag',
      label: 'Registry diagnostics',
      icon: Activity,
      run: () => openModal('Registry diagnostics', { kind: 'diagnostics' }, 'sm'),
    },
  ];

  /** Substring beats subsequence; lower is better, null = no match. */
  function score(label: string, query: string): number | null {
    const l = label.toLowerCase();
    const i = l.indexOf(query);
    if (i === 0) return 0;
    if (i > 0) return 1 + i / 100;
    let j = 0;
    for (const c of l) if (c === query[j]) j++;
    return j === query.length ? 3 : null;
  }

  function ranked<T extends Item>(items: T[], query: string, limit = Infinity): T[] {
    if (!query) return items.slice(0, limit);
    return items
      .map((it) => [it, score(it.label, query)] as const)
      .filter(([, s]) => s !== null)
      .sort((a, b) => (a[1] as number) - (b[1] as number))
      .slice(0, limit)
      .map(([it]) => it);
  }

  const classItems = $derived(
    classesState.cards
      .filter((c) => c.total_record_count > 0)
      .map((c): Item => ({ kind: 'class', key: c.class_name, label: c.class_name, type: c.object_type, count: c.total_record_count })),
  );

  const versionItems = $derived(
    versions.map((v): Item => ({ kind: 'version', key: v.version_id, label: v.label, changed: v.changed_class_names.length })),
  );

  const shown = $derived.by(() => {
    const query = q.trim().toLowerCase();
    const entries: Item[] = found.map((f) => ({
      kind: 'entry',
      key: f.record_id,
      label: f.record_id,
      type: f.object_type,
      className: f.class_name,
    }));
    if (!query) return [...commands.slice(0, 3), ...classItems.slice(0, CLASS_LIMIT)];
    return [
      ...entries,
      ...ranked(classItems, query, CLASS_LIMIT),
      ...ranked(versionItems, query, 8),
      ...ranked(commands, query),
    ];
  });

  $effect(() => {
    void shown;
    active = 0;
  });

  // Entry lookup by id prefix, debounced; stale responses are dropped.
  let findSeq = 0;
  $effect(() => {
    const query = q.trim().toLowerCase();
    const seq = ++findSeq;
    if (!HEX.test(query)) {
      found = [];
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.findEntries(query);
        if (seq === findSeq) found = res.entries ?? [];
      } catch {
        if (seq === findSeq) found = [];
      }
    }, 120);
    return () => clearTimeout(timer);
  });

  onMount(() => {
    input.focus();
    codeApi
      .versions()
      .then((r) => {
        if (!isLoading(r)) versions = r.versions;
      })
      .catch(() => {});
  });

  function close() {
    palette.open = false;
  }

  function pick(it: Item) {
    close();
    if (it.kind === 'class') {
      if (filterState.kindFilter !== 'all' && it.type.toLowerCase() !== filterState.kindFilter) filterState.kindFilter = 'all';
      void navigateToClass(it.key);
    } else if (it.kind === 'entry') {
      setView('entries');
      void openEntry(it.key, it.className);
    } else if (it.kind === 'version') {
      navigateToCodeVersion(it.key);
    } else {
      it.run();
    }
  }

  async function scrollActive() {
    await tick();
    list.querySelector('.qs-row.active')?.scrollIntoView({ block: 'nearest' });
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      active = Math.min(shown.length - 1, active + 1);
      void scrollActive();
    } else if (e.key === 'ArrowUp') {
      active = Math.max(0, active - 1);
      void scrollActive();
    } else if (e.key === 'Enter') {
      if (shown[active]) pick(shown[active]);
    } else if (e.key === 'Escape') {
      close();
    } else return;
    e.preventDefault();
    e.stopPropagation();
  }
</script>

<div class="qs-backdrop" role="presentation" onmousedown={(e) => e.target === e.currentTarget && close()}>
  <div class="qs" role="dialog" aria-label="Quick switcher">
    <div class="qs-search">
      <Search size={17} />
      <input
        bind:this={input}
        bind:value={q}
        {onkeydown}
        placeholder="Jump to a class, entry hash, code version or command…"
        spellcheck="false"
        autocomplete="off"
      />
      <kbd>esc</kbd>
    </div>
    <div class="qs-list" bind:this={list}>
      {#each shown as it, i (`${it.kind}:${it.key}`)}
        {#if i === 0 || shown[i - 1].kind !== it.kind}
          <div class="qs-group">{GROUP_LABEL[it.kind]}</div>
        {/if}
        <button class="qs-row" class:active={i === active} onmousemove={() => (active = i)} onclick={() => pick(it)}>
          {#if it.kind === 'class'}
            <KindIcon type={it.type} size={15} />
            <span class="qs-label">{it.label}</span>
            <span class="qs-meta">{it.count}</span>
          {:else if it.kind === 'entry'}
            <Hash size={15} />
            <span class="qs-label qs-mono">{it.label.slice(0, 12)}</span>
            <span class="qs-meta"><KindIcon type={it.type} size={13} /> {it.className}</span>
          {:else if it.kind === 'version'}
            <GitCommitVertical size={15} />
            <span class="qs-label">{it.label}</span>
            <span class="qs-meta">{it.changed ? `${it.changed} changed` : ''}</span>
          {:else}
            <it.icon size={15} />
            <span class="qs-label">{it.label}</span>
          {/if}
        </button>
      {:else}
        <div class="qs-empty">Nothing found</div>
      {/each}
    </div>
  </div>
</div>

<style>
  .qs-backdrop {
    position: fixed;
    inset: 0;
    z-index: 500;
    background: var(--backdrop);
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 14vh;
  }
  .qs {
    width: min(620px, calc(100vw - 32px));
    max-height: 64vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: 0 18px 48px var(--shadow-color), 0 3px 10px var(--shadow-color-soft);
  }
  .qs-search {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: 10px;
    height: 52px;
    padding: 0 16px;
    border-bottom: 1px solid var(--border-s);
    color: var(--faint);
  }
  .qs-search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: none;
    font-size: 15px;
    color: var(--text);
  }
  .qs-search input::placeholder {
    color: var(--faint);
  }
  kbd {
    font: inherit;
    font-size: 10px;
    color: var(--muted);
    background: var(--s2);
    border: 1px solid var(--border);
    border-bottom-width: 2px;
    border-radius: 4px;
    padding: 0 5px;
  }
  .qs-list {
    overflow-y: auto;
    padding: 6px;
  }
  .qs-group {
    padding: 8px 10px 4px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .qs-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 34px;
    padding: 0 10px;
    border: none;
    border-radius: 7px;
    background: none;
    text-align: left;
    color: var(--muted);
    cursor: pointer;
  }
  .qs-row.active {
    background: var(--accent-bg2);
    box-shadow: inset 3px 0 0 var(--accent);
    color: var(--text);
  }
  .qs-label {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .qs-mono {
    font-family: var(--mono);
    font-size: 12px;
  }
  .qs-meta {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
    font-size: 11px;
    color: var(--faint);
  }
  .qs-empty {
    padding: 24px;
    text-align: center;
    font-size: 12px;
    color: var(--faint);
  }
</style>
