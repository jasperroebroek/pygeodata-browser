<script lang="ts">
  import { startReload, ui } from '../lib/stores.svelte';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';
  import ErrorBox from './ErrorBox.svelte';

  const clock = (epochSeconds: number) =>
    new Date(epochSeconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const pendingImport = $derived(ui.mode === 'import' && ui.codeChangedSince !== null);
  // closing hides this error only; a different one shows again
  let dismissed = $state<string | null>(null);
  const failure = $derived(ui.ready && ui.loadError !== dismissed ? ui.loadError : null);
</script>

{#if failure || pendingImport}
  <div class="status-notice-stack">
    {#if failure}
      <ErrorBox
        title={ui.hasState ? 'Reload failed — showing the last good state' : 'Loading failed'}
        message={failure}
        onRetry={() => void startReload()}
        onClose={() => (dismissed = failure)}
      />
    {/if}
    {#if pendingImport}
      <div class="status-notice">
        <span>
          Code changed since the last import{ui.nextImportAt ? ` — next import at ${clock(ui.nextImportAt)}` : ''}
        </span>
        <button class="act-btn status-notice-btn" onclick={() => void startReload()}><RefreshCw size={13} /> Reload</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .status-notice-stack {
    position: fixed;
    left: 50%;
    bottom: 14px;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    z-index: 55;
  }
  .status-notice-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .status-notice {
    max-width: min(640px, calc(100vw - 28px));
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px 12px;
    font-size: 12px;
    color: var(--warn);
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 10px;
    box-shadow: 0 4px 24px var(--shadow-color);
  }
</style>
