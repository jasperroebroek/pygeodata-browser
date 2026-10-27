import { fetchFresh } from './api';
import type { TableRow } from './api';

export interface ExportStartResult {
  job_id: string;
  total: number;
  warnings: string[];
}

export interface ExportStatusResult {
  status: 'running' | 'complete' | 'error';
  done: number;
  total: number;
  error: string | null;
  warnings: string[];
}

export interface ExportTableResult {
  table_rows: TableRow[];
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return (await res.json()) as T;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetchFresh(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return (await res.json()) as T;
}

export const exportApi = {
  start(recordIds: string[], includeSnapshots = true): Promise<ExportStartResult> {
    return postJson('/api/export/start', {
      record_ids: recordIds,
      include_snapshots: includeSnapshots,
    });
  },

  status(jobId: string): Promise<ExportStatusResult> {
    return getJson(`/api/export/status/${encodeURIComponent(jobId)}`);
  },

  table(recordIds: string[]): Promise<ExportTableResult> {
    return postJson('/api/export/table', { record_ids: recordIds });
  },

  downloadUrl(jobId: string): string {
    return `/api/export/download/${encodeURIComponent(jobId)}`;
  },

  singleUrl(recordId: string): string {
    return `/api/export/single/${encodeURIComponent(recordId)}`;
  },
};
