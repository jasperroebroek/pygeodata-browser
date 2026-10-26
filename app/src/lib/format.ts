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

export const singleEntryUrl = (recordId: string) => `/api/export/single/${encodeURIComponent(recordId)}`;

const RASTER_EXTS = new Set(['.tif', '.tiff', '.nc', '.vrt', '.npy', '.zarr']);

export function isRasterFile(path: string): boolean {
  const i = path.lastIndexOf('.');
  return i !== -1 && RASTER_EXTS.has(path.slice(i).toLowerCase());
}
