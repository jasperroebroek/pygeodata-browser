export const toastState = $state({ msg: '' });

let timer: ReturnType<typeof setTimeout> | null = null;

export function toast(msg: string): void {
  toastState.msg = msg;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    toastState.msg = '';
    timer = null;
  }, 1800);
}
