<script lang="ts">
  import Settings2 from '@lucide/svelte/icons/settings-2';
  import { filterState, layout, selection, setMultiClass, setParamDisplay, setTheme, toggleHideStale, ui } from '../lib/stores.svelte';
  import type { ParamDisplay, Theme } from '../lib/stores.svelte';
  import { codeUi, setHideEmpty } from '../lib/nav.svelte';

  let open = $state(false);
  let wrapEl: HTMLElement | undefined = $state();

  function onWindowClick(e: MouseEvent) {
    if (open && wrapEl && !wrapEl.contains(e.target as Node)) open = false;
  }

  const paramModes: { key: ParamDisplay; label: string; title: string }[] = [
    { key: 'selected', label: 'Selected', title: 'Only parameter rows matching the active filters' },
    { key: 'all', label: 'All', title: 'Every parameter row' },
  ];

  const themes: { key: Theme; label: string }[] = [
    { key: 'system', label: 'System' },
    { key: 'light', label: 'Light' },
    { key: 'dark', label: 'Dark' },
  ];

  interface Row {
    label: string;
    desc: string;
    on: boolean;
    toggle: () => void;
  }

  const rows = $derived.by((): Row[] => {
    if (ui.view === 'code') {
      return [
        {
          label: 'Hide empty versions',
          desc: 'Skip versions without changes for the current filter',
          on: codeUi.hideEmpty,
          toggle: () => setHideEmpty(!codeUi.hideEmpty),
        },
      ];
    }
    if (ui.view !== 'entries') return [];
    return [
      {
        label: 'Hide stale entries',
        desc: 'Skip entries whose dependencies or format version changed',
        on: filterState.hideStale,
        toggle: () => void toggleHideStale(),
      },
      {
        label: 'Show empty classes',
        desc: 'List classes without visible entries',
        on: selection.showEmpty,
        toggle: () => (selection.showEmpty = !selection.showEmpty),
      },
      {
        label: 'Multi-select classes',
        desc: 'Class clicks add to the selection without holding ⌘/Ctrl',
        on: selection.multiClass,
        toggle: () => void setMultiClass(!selection.multiClass),
      },
    ];
  });
</script>

<svelte:window onclick={onWindowClick} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="vs-wrap" bind:this={wrapEl}>
  <button
    class="icon-btn"
    class:active={open}
    aria-haspopup="menu"
    aria-expanded={open}
    title="View settings"
    onclick={() => (open = !open)}
  >
    <Settings2 size={20} />
  </button>

  {#if open}
    <div class="vs-popover" role="menu">
      {#if ui.view === 'entries'}
        <div class="vs-group" class:disabled={layout.entriesMode === 'compact'}>
          <div class="vs-label">Parameter rows</div>
          <div class="vs-seg" role="group" aria-label="Parameter rows">
            {#each paramModes as m (m.key)}
              <button
                class="vs-seg-btn"
                class:active={filterState.paramDisplay === m.key}
                title={m.title}
                disabled={layout.entriesMode === 'compact'}
                onclick={() => void setParamDisplay(m.key)}
              >
                {m.label}
              </button>
            {/each}
          </div>
        </div>
      {/if}

      {#each rows as r (r.label)}
        <button class="vs-row" role="menuitemcheckbox" aria-checked={r.on} onclick={r.toggle}>
          <span class="vs-row-text">
            <span class="vs-row-label">{r.label}</span>
            <span class="vs-row-desc">{r.desc}</span>
          </span>
          <span class="vs-switch" class:on={r.on} aria-hidden="true"></span>
        </button>
      {/each}

      <div class="vs-group">
        <div class="vs-label">Theme</div>
        <div class="vs-seg" role="group" aria-label="Theme">
          {#each themes as th (th.key)}
            <button class="vs-seg-btn" class:active={ui.theme === th.key} onclick={() => setTheme(th.key)}>{th.label}</button>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .vs-wrap {
    position: relative;
    display: flex;
  }
  .vs-popover {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    width: 300px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 4px 16px var(--shadow-color);
    padding: 6px;
    z-index: 200;
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: var(--text);
  }
  .vs-group {
    padding: 8px 8px 6px;
  }
  .vs-group.disabled {
    opacity: 0.4;
  }
  .vs-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--faint);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }
  .vs-seg {
    display: flex;
    gap: 2px;
    background: var(--s2);
    border-radius: 999px;
    padding: 2px;
  }
  .vs-seg-btn {
    flex: 1;
    padding: 3px 8px;
    border: none;
    border-radius: 999px;
    background: transparent;
    font-size: 11px;
    color: var(--muted);
    cursor: pointer;
  }
  .vs-seg-btn:hover:not(.active):not(:disabled) {
    background: var(--s3);
    color: var(--text);
  }
  .vs-seg-btn.active {
    background: var(--accent-bg);
    color: var(--accent);
    font-weight: 600;
  }
  .vs-row {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 6px 8px;
    border: none;
    border-radius: 6px;
    background: none;
    text-align: left;
    cursor: pointer;
  }
  .vs-row:hover {
    background: var(--s2);
  }
  .vs-row-text {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
  }
  .vs-row-label {
    font-size: 12px;
  }
  .vs-row-desc {
    font-size: 11px;
    color: var(--faint);
    line-height: 1.35;
  }
  .vs-switch {
    flex: none;
    position: relative;
    width: 28px;
    height: 16px;
    border-radius: 999px;
    background: var(--s3);
    border: 1px solid var(--border);
    transition: background 0.12s, border-color 0.12s;
  }
  .vs-switch::after {
    content: '';
    position: absolute;
    top: 1px;
    left: 1px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--surface);
    box-shadow: 0 1px 2px var(--shadow-color);
    transition: transform 0.12s;
  }
  .vs-switch.on {
    background: var(--accent);
    border-color: var(--accent);
  }
  .vs-switch.on::after {
    transform: translateX(12px);
  }
</style>
