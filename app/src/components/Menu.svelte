<script lang="ts">
  import EllipsisVertical from '@lucide/svelte/icons/ellipsis-vertical';
  import { api } from '../lib/api';
  import { classesState, startReload, ui } from '../lib/stores.svelte';
  import { openModal } from '../lib/modal.svelte';

  const readOnly = $derived(classesState.catalog?.read_only ?? false);
  const readOnlyTitle = 'Read-only (mirror mode): the browser never writes into the project';

  let open = $state(false);
  let wrapEl: HTMLElement | undefined = $state();

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
</script>

<svelte:window onclick={onWindowClick} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="topbar-menu-wrap" bind:this={wrapEl}>
  <button class="icon-btn" class:active={open} title="Menu" aria-haspopup="menu" aria-expanded={open} onclick={toggle}>
    <EllipsisVertical size={20} />
  </button>
  {#if open}
    <div class="topbar-menu" role="menu">
      <button class="topbar-menu-item" role="menuitem" onclick={() => run(() => void startReload())}>Reload</button>
      <div class="topbar-menu-sep"></div>
      <button
        class="topbar-menu-item"
        role="menuitem"
        disabled={!ui.hasLiveClasses || readOnly}
        title={readOnly ? readOnlyTitle : undefined}
        onclick={() => run(() => openModal('Clean Cache', { kind: 'clean', target: 'cache' }, 'md'))}
      >
        Clean cache…
      </button>
      <button
        class="topbar-menu-item"
        role="menuitem"
        disabled={!ui.hasLiveClasses || readOnly}
        title={readOnly ? readOnlyTitle : undefined}
        onclick={() => run(() => openModal('Clean Source Registry', { kind: 'clean', target: 'source' }, 'md'))}
      >
        Clean registry…
      </button>
    </div>
  {/if}
</div>
