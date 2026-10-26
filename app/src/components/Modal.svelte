<script lang="ts">
  import { classesState } from '../lib/stores.svelte';
  import { closeModal, modal } from '../lib/modal.svelte';
  import { navigateToCodeClass } from '../lib/nav.svelte';
  import { zoomable } from '../lib/zoom';
  import CleanPanel from './CleanPanel.svelte';
  import DiagnosticsTable from './DiagnosticsTable.svelte';
  import JsonExplorer from './JsonExplorer.svelte';

  const current = $derived(modal.current);
  const knownClasses = $derived(new Set(classesState.cards.map((c) => c.class_name)));

  function toCode(cls: string, depHash: string | null = null) {
    closeModal();
    navigateToCodeClass(cls, { depHash });
  }

  // Graph SVGs carry clickable class nodes; hover highlights the deepest node.
  let graphEl: HTMLElement | undefined = $state();
  let hovered: Element | null = null;

  function onGraphMove(e: MouseEvent) {
    const node = (e.target as Element).closest('.graph-node-link');
    if (node === hovered) return;
    hovered?.classList.remove('hovered');
    node?.classList.add('hovered');
    hovered = node;
  }

  function onGraphClick(e: MouseEvent) {
    const link = (e.target as Element).closest<HTMLElement | SVGElement>('.graph-node-link, .src-cls-link');
    const cls = link?.dataset.cls;
    if (cls) {
      e.preventDefault();
      toCode(cls);
    }
  }

  $effect(() => {
    const svg = graphEl?.querySelector('svg');
    if (!svg) return;
    svg.style.display = 'block';
    svg.style.margin = 'auto';
    return zoomable(svg).destroy;
  });
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && current && closeModal()} />

{#if current}
  <div
    class="modal-backdrop open"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && closeModal()}
  >
    <div class="modal-card" class:modal-card--sm={current.size === 'sm'} class:modal-card--md={current.size === 'md'}>
      <div class="modal-bar">
        <span class="modal-title">{current.title}</span>
        <button class="modal-close" onclick={closeModal}>✕</button>
      </div>
      <div class="modal-content">
        {#if current.content.kind === 'json'}
          {@const c = current.content}
          <div class="jx-popup-wrap">
            <JsonExplorer data={c.data} filterHidden={false} {knownClasses} onClass={(cls) => toCode(cls, c.depHash ?? null)} />
          </div>
        {:else if current.content.kind === 'iframe'}
          <iframe src={current.content.src} title={current.title} style="width:100%;height:74vh;border:0"></iframe>
        {:else if current.content.kind === 'image'}
          <div style="display:flex;align-items:center;justify-content:center;height:100%;overflow:hidden">
            <img
              src={current.content.src}
              alt={current.title}
              use:zoomable
              style="max-width:100%;max-height:100%;object-fit:contain;cursor:grab;user-select:none"
            />
          </div>
        {:else if current.content.kind === 'html'}
          <div class={current.content.className}>{@html current.content.html}</div>
        {:else if current.content.kind === 'graph'}
          <div
            class="svg-zoom-wrap"
            bind:this={graphEl}
            role="presentation"
            onmousemove={onGraphMove}
            onmouseleave={() => (hovered?.classList.remove('hovered'), (hovered = null))}
            onclick={onGraphClick}
          >
            {@html current.content.svg}
          </div>
        {:else if current.content.kind === 'diagnostics'}
          <DiagnosticsTable />
        {:else if current.content.kind === 'clean'}
          <CleanPanel target={current.content.target} />
        {/if}
      </div>
    </div>
  </div>
{/if}
