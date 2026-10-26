export interface ToastItem {
  id: number;
  message: string;
  on: boolean;
}

export const toasts = $state<ToastItem[]>([]);

let nextId = 0;

/** Bottom-right toast: fades in, stays 8s, fades out. */
export function toast(message: string): void {
  const id = ++nextId;
  toasts.push({ id, message, on: false });
  // Two frames so the off state paints before the fade-in transition starts.
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      const t = toasts.find((x) => x.id === id);
      if (t) t.on = true;
    }),
  );
  setTimeout(() => {
    const t = toasts.find((x) => x.id === id);
    if (t) t.on = false;
    setTimeout(() => {
      const i = toasts.findIndex((x) => x.id === id);
      if (i !== -1) toasts.splice(i, 1);
    }, 200);
  }, 8000);
}
