import { api } from './api';
import { openModal } from './modal.svelte';
import { toast } from './toast.svelte';

export function openPath(path: string) {
  api
    .openPath(path)
    .then(() => toast('Opened'))
    .catch(() => toast('Failed to open'));
}

export function revealPath(path: string) {
  api
    .revealPath(path)
    .then(() => toast('Revealed'))
    .catch(() => toast('Failed to reveal'));
}

export async function copyText(text: string, done = 'Copied') {
  try {
    await navigator.clipboard.writeText(text);
    toast(done);
  } catch {
    toast('Copy failed');
  }
}

/**
 * JSON files open in the explorer (class links jump to the code view, routed by
 * depHash); anything else opens in an iframe. `pick` selects a sub-tree (tree/nodes).
 */
export async function openFilePopup(
  path: string,
  opts: { title?: string; pick?: 'tree' | 'nodes'; depHash?: string | null } = {},
) {
  if (!path.endsWith('.json')) {
    openModal(opts.title ?? 'File', { kind: 'iframe', src: api.fileUrl(path) });
    return;
  }
  try {
    const data = await api.popupJson(path);
    let json = data.json as Record<string, unknown>;
    if (opts.pick) json = (json?.[opts.pick] as Record<string, unknown>) ?? json;
    openModal(opts.title ?? data.title, { kind: 'json', data: json, codeNav: true, depHash: opts.depHash ?? null });
  } catch {
    toast(opts.pick === 'tree' ? 'Tree unavailable' : opts.pick === 'nodes' ? 'Nodes unavailable' : 'Failed to load JSON');
  }
}

export async function openGraphPopup(className: string, graphPath: string | null) {
  try {
    const data = await api.popupGraph(className, graphPath);
    if (data.svg) openModal(data.title, { kind: 'graph', svg: data.svg });
    else if (data.pdf_path) openModal(data.title, { kind: 'iframe', src: api.fileUrl(data.pdf_path) });
  } catch {
    toast('Graph unavailable');
  }
}
