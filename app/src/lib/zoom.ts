/** Ctrl+wheel zoom, wheel/drag pan once zoomed — attaches to an image or SVG inside a clipping parent. */
export function zoomable(el: HTMLElement | SVGElement) {
  const parent = el.parentElement!;
  let scale = 1;
  let ox = 0;
  let oy = 0;
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startOx = 0;
  let startOy = 0;

  function clamp() {
    const r = el.getBoundingClientRect();
    const pr = parent.getBoundingClientRect();
    const maxX = Math.max(0, (r.width - pr.width) / 2);
    const maxY = Math.max(0, (r.height - pr.height) / 2);
    ox = Math.max(-maxX, Math.min(maxX, ox));
    oy = Math.max(-maxY, Math.min(maxY, oy));
  }

  function apply() {
    el.style.transform = `translate(${ox}px, ${oy}px) scale(${scale})`;
    el.style.transformOrigin = 'center center';
    el.style.cursor = scale > 1 ? (dragging ? 'grabbing' : 'grab') : '';
  }

  function onWheel(e: WheelEvent) {
    if (scale === 1 && !e.ctrlKey) return;
    e.preventDefault();
    if (e.ctrlKey) {
      scale = Math.max(1, Math.min(10, scale * (e.deltaY < 0 ? 1.08 : 1 / 1.08)));
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
  }

  function onDown(e: Event) {
    const me = e as MouseEvent;
    if (scale <= 1) return;
    dragging = true;
    startX = me.clientX;
    startY = me.clientY;
    startOx = ox;
    startOy = oy;
    apply();
    me.preventDefault();
  }

  function onMove(e: MouseEvent) {
    if (!dragging) return;
    ox = startOx + (e.clientX - startX);
    oy = startOy + (e.clientY - startY);
    clamp();
    apply();
  }

  function onUp() {
    if (!dragging) return;
    dragging = false;
    apply();
  }

  parent.addEventListener('wheel', onWheel, { passive: false });
  el.addEventListener('mousedown', onDown);
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
  return {
    destroy() {
      parent.removeEventListener('wheel', onWheel);
      el.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    },
  };
}
