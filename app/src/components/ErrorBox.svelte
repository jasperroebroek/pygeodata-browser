<script lang="ts">
  import Copy from '@lucide/svelte/icons/copy';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';
  import X from '@lucide/svelte/icons/x';
  import { copyText } from '../lib/actions';

  let {
    title,
    message,
    onRetry = null,
    onClose,
  }: {
    title: string;
    message: string;
    onRetry?: (() => void) | null;
    onClose: () => void;
  } = $props();
</script>

<div class="error-box" role="alert">
  <div class="error-box-hd">
    <span class="error-box-title">{title}</span>
    <button class="act-btn error-box-btn" title="Copy the error" onclick={() => void copyText(message, 'Error copied')}>
      <Copy size={13} /> Copy
    </button>
    {#if onRetry}<button class="act-btn error-box-btn" onclick={onRetry}><RefreshCw size={13} /> Reload</button>{/if}
    <button class="act-btn error-box-close" title="Close" aria-label="Close" onclick={onClose}><X size={15} /></button>
  </div>
  <pre>{message}</pre>
</div>

<style>
  .error-box {
    width: min(960px, calc(100vw - 32px));
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    color: var(--danger);
    background: var(--danger-bg);
    border: 1px solid var(--danger-border);
    border-radius: 10px;
    box-shadow: 0 4px 24px var(--shadow-color);
    text-align: left;
  }
  .error-box-hd {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }
  .error-box-title {
    flex: 1;
    font-weight: 600;
  }
  .error-box-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .error-box-close {
    display: inline-flex;
    padding: 3px;
  }
  pre {
    margin: 0;
    max-height: 50vh;
    overflow: auto;
    font-size: 11px;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text);
  }
</style>
