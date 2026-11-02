/** Swap an image's (preview) src for `full` once that has downloaded and decoded; keeps the preview on failure. */
export function progressiveSrc(el: HTMLImageElement, full: string | undefined) {
  let loader: HTMLImageElement | null = null;

  function load(src: string | undefined) {
    cancel();
    if (!src) return;
    const img = new Image();
    loader = img;
    img.src = src;
    img.decode().then(
      () => {
        if (loader === img) el.src = src;
      },
      () => {},
    );
  }

  function cancel() {
    if (loader) loader.src = '';
    loader = null;
  }

  load(full);
  return {
    update: load,
    destroy: cancel,
  };
}
