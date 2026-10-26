<script lang="ts">
  import { api } from '../lib/api';
  import { setTheme, startReload, ui } from '../lib/stores.svelte';
  import type { Theme } from '../lib/stores.svelte';
  import { openModal } from '../lib/modal.svelte';

  let open = $state(false);
  let wrapEl: HTMLElement | undefined = $state();

  const THEMES: Theme[] = ['light', 'dark', 'system'];
  const THEME_LABEL: Record<Theme, string> = { light: 'Light', dark: 'Dark', system: 'System' };

  async function toggle() {
    open = !open;
    if (open) {
      try {
        ui.hasLiveClasses = (await api.status()).has_live_classes;
      } catch {
        /* keep last known value */
      }
    }
  }

  function onWindowClick(e: MouseEvent) {
    if (open && wrapEl && !wrapEl.contains(e.target as Node)) open = false;
  }

  function run(action: () => void) {
    open = false;
    action();
  }

  function cycleTheme() {
    setTheme(THEMES[(THEMES.indexOf(ui.theme) + 1) % THEMES.length]);
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="topbar-menu-wrap" bind:this={wrapEl}>
  <button class="ghost-btn topbar-icon-btn" title="Menu" aria-haspopup="menu" aria-expanded={open} onclick={toggle}>⋮</button>
  {#if open}
    <div class="topbar-menu" role="menu">
      <button class="topbar-menu-item" role="menuitem" onclick={() => run(() => void startReload(false))}>Reload from disk</button>
      <button class="topbar-menu-item" role="menuitem" onclick={() => run(() => void startReload(true))}>Reimport Python files</button>
      <div class="topbar-menu-sep"></div>
      <button
        class="topbar-menu-item"
        role="menuitem"
        disabled={!ui.hasLiveClasses}
        onclick={() => run(() => openModal('Clean Cache', { kind: 'clean', target: 'cache' }, 'md'))}
      >
        Clean cache…
      </button>
      <button
        class="topbar-menu-item"
        role="menuitem"
        disabled={!ui.hasLiveClasses}
        onclick={() => run(() => openModal('Clean Source Registry', { kind: 'clean', target: 'source' }, 'md'))}
      >
        Clean registry…
      </button>
      <div class="topbar-menu-sep"></div>
      <button class="topbar-menu-item" role="menuitem" onclick={cycleTheme}>Theme: {THEME_LABEL[ui.theme]}</button>
    </div>
  {/if}
</div>
