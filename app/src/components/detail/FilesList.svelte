<script lang="ts">
  import { api } from '../../lib/api';
  import { detailApi, isRasterFile } from './apiDetail';
  import { toast } from './toast.svelte';
  import type { FilePayload } from '../../lib/api';

  let {
    files,
    primary = null,
  }: {
    files: FilePayload[];
    primary?: FilePayload | null;
  } = $props();

  const kindClass: Record<string, string> = {
    image: 'kind-badge--figure',
    table: 'kind-badge--table',
    raster: 'kind-badge--data',
  };

  async function open(path: string): Promise<void> {
    try {
      await detailApi.openPath(path);
      toast('Opened');
    } catch {
      toast('Failed to open');
    }
  }

  async function reveal(path: string): Promise<void> {
    try {
      await detailApi.revealPath(path);
      toast('Revealed');
    } catch {
      toast('Failed to reveal');
    }
  }

  async function copy(path: string): Promise<void> {
    try {
      await detailApi.copyText(path);
      toast('Copied');
    } catch {
      toast('Copy failed');
    }
  }
</script>

<div class="file-list">
  {#each files as f (f.path)}
    <div class="file-row" class:file-row--sidecar={primary !== null && f.path !== primary.path}>
      <span class="kind-badge {kindClass[f.kind] ?? ''}">{f.kind}</span>
      <span class="file-name" class:file-name--primary={primary !== null && f.path === primary.path}>
        {f.label}
      </span>
      <a class="dbtn" href={api.fileUrl(f.path)} download title="Download {f.label}">Download</a>
      {#if !isRasterFile(f.path)}
        <button class="act-btn" onclick={() => open(f.path)}>Open</button>
      {/if}
      <button class="act-btn" onclick={() => reveal(f.path)}>Reveal</button>
      <button class="act-btn" onclick={() => copy(f.path)} title={f.path}>Copy path</button>
    </div>
  {/each}
</div>
