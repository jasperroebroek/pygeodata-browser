<script lang="ts">
  import ParamsTree from './ParamsTree.svelte';

  export type ModalState =
    | { kind: 'image'; title: string; src: string }
    | { kind: 'iframe'; title: string; src: string }
    | { kind: 'srcdoc'; title: string; srcdoc: string }
    | {
        kind: 'tree';
        title: string;
        data: unknown;
        knownClasses?: Set<string> | null;
        onClass?: (cls: string) => void;
      };

  let {
    modal,
    onClose,
  }: {
    modal: ModalState | null;
    onClose: () => void;
  } = $props();

  // Figure zoom/pan — port of legacy bindZoom (ctrl+wheel zoom, wheel/drag pan).
  let wrapEl: HTMLElement | null = $state(null);
  let imgEl: HTMLImageElement | null = $state(null);
  let scale = $state(1);
  let ox = $state(0);
  let oy = $state(0);
  let dragging = $state(false);
  let startX = 0;
  let startY = 0;
  let startOx = 0;
  let startOy = 0;

  function clamp(): void {
    if (!imgEl || !wrapEl) return;
    const r = imgEl.getBoundingClientRect();
    const pr = wrapEl.getBoundingClientRect();
    const maxX = Math.max(0, (r.width - pr.width) / 2);
    const maxY = Math.max(0, (r.height - pr.height) / 2);
    ox = Math.max(-maxX, Math.min(maxX, ox));
    oy = Math.max(-maxY, Math.min(maxY, oy));
  }

  function apply(): void {
    if (!imgEl) return;
    imgEl.style.transform = `translate(${ox}px, ${oy}px) scale(${scale})`;
    imgEl.style.transformOrigin = 'center center';
    imgEl.style.cursor = scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'default';
  }

  $effect(() => {
    if (!modal || modal.kind !== 'image') return;
    const wrap = wrapEl;
    const img = imgEl;
    if (!wrap || !img) return;

    scale = 1;
    ox = 0;
    oy = 0;
    dragging = false;

    const onWheel = (e: WheelEvent) => {
      if (scale === 1 && !e.ctrlKey) return;
      e.preventDefault();
      if (e.ctrlKey) {
        const factor = e.deltaY < 0 ? 1.08 : 1 / 1.08;
        scale = Math.max(1, Math.min(10, scale * factor));
        if (scale === 1) {
          ox = 0;
          oy = 0;
        }
      } else {
        ox -= e.deltaX;
        oy -= e.deltaY;
      }
      clamp();
      apply();
    };

    const onDown = (e: MouseEvent) => {
      if (scale <= 1) return;
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      startOx = ox;
      startOy = oy;
      img.style.cursor = 'grabbing';
      e.preventDefault();
    };

    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      ox = startOx + (e.clientX - startX);
      oy = startOy + (e.clientY - startY);
      clamp();
      apply();
    };

    const onUp = () => {
      if (!dragging) return;
      dragging = false;
      apply();
    };

    wrap.addEventListener('wheel', onWheel, { passive: false });
    img.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      wrap.removeEventListener('wheel', onWheel);
      img.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  });

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={modal ? onKeydown : undefined} />

{#if modal}
  <div
    class="dmodal"
    role="dialog"
    aria-modal="true"
    aria-label={modal.title}
    tabindex="-1"
    onclick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}
    onkeydown={(e) => {
      if (e.key === 'Escape') onClose();
    }}
  >
    <div class="dmodal-card">
      <div class="dmodal-hd">
        <span class="dmodal-title">{modal.title}</span>
        <button class="dmodal-close" aria-label="Close" onclick={onClose}>×</button>
      </div>
      {#if modal.kind === 'image'}
        <div class="dmodal-body dmodal-body--img" bind:this={wrapEl}>
          <img bind:this={imgEl} src={modal.src} alt={modal.title} />
        </div>
      {:else if modal.kind === 'iframe'}
        <div class="dmodal-body">
          <iframe class="dmodal-frame" src={modal.src} title={modal.title}></iframe>
        </div>
      {:else if modal.kind === 'srcdoc'}
        <div class="dmodal-body">
          <iframe class="dmodal-frame" srcdoc={modal.srcdoc} title={modal.title}></iframe>
        </div>
      {:else if modal.kind === 'tree'}
        <div class="dmodal-body dmodal-body--tree">
          <ParamsTree
            data={modal.data}
            filterHidden={false}
            knownClasses={modal.knownClasses ?? null}
            onClass={modal.onClass ?? null}
          />
        </div>
      {/if}
    </div>
  </div>
{/if}
