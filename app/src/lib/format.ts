// Zero-width spaces after punctuation (except _) let long values wrap there.
export function softBreak(value: unknown): string {
  return String(value ?? '').replace(/([./\-:,;@#!?=+*|\\[\]{}()<>~`^%$&])/g, '$1​');
}

export function triggerDownload(url: string, name?: string) {
  const a = document.createElement('a');
  a.href = url;
  if (name) a.download = name;
  a.click();
}

export const offlineTitle = (root: string) =>
  `Cache root ${root} is unavailable (missing or empty): this entry is shown from the catalog and its files can't be checked`;

export const singleEntryUrl = (recordId: string) => `/api/export/single/${encodeURIComponent(recordId)}`;

const RASTER_EXTS = new Set(['.tif', '.tiff', '.nc', '.vrt', '.npy', '.zarr']);

export function isRasterFile(path: string): boolean {
  const i = path.lastIndexOf('.');
  return i !== -1 && RASTER_EXTS.has(path.slice(i).toLowerCase());
}

export type FileTone = 'data' | 'table' | 'figure' | 'neutral';

const FILE_TONES: Record<string, FileTone> = { raster: 'data', table: 'table', image: 'figure', pdf: 'figure' };

/** Colour family for a file-kind pill (kinds come from pygeodata's classify_file). */
export const fileTone = (kind: string): FileTone => FILE_TONES[kind] ?? 'neutral';
