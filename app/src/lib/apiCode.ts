// Client for the /api/code/* endpoints (api/web.py). Owned by the code-view milestone.

export interface CodeVersion {
  version_id: string;
  mtime: string;
  label: string;
  class_names: string[];
  changed_class_names: string[];
  has_entries: boolean;
}

export interface CodeClassState {
  class_name: string;
  object_type: string;
  source_hash: string;
  is_loaded: boolean;
  is_stale: boolean;
}

export interface SnapshotLine {
  text: string;
  cls_link: string | null;
}

export interface SnapshotPayload {
  class_name: string;
  lines: SnapshotLine[];
}

export type DiffSegmentType = 'eq' | 'del' | 'ins';

export interface DiffSegment {
  type: DiffSegmentType;
  text: string;
}

export interface DiffLine {
  type: 'ctx' | 'del' | 'add';
  text: string;
  line_old: number | null;
  line_new: number | null;
  segments?: DiffSegment[];
}

export interface DiffHunk {
  header: string;
  start_old: number;
  start_new: number;
  lines: DiffLine[];
}

export interface DiffPayload {
  hunks: DiffHunk[];
  full_old?: string;
  full_new?: string;
}

export type ChangeStatus = 'changed' | 'added' | 'removed' | 'unchanged';

export interface VersionChange {
  class_name: string;
  status: ChangeStatus;
  hash_old: string | null;
  hash_new: string | null;
}

export interface VersionDiffPayload {
  changes?: VersionChange[];
  base_version_id?: string | null;
  has_live_stale?: boolean;
  error?: string;
  message?: string;
}

export interface LoadingPayload {
  loading: true;
  fast: boolean;
}

export type VersionsResponse = { versions: CodeVersion[]; has_live_classes: boolean } | LoadingPayload;

export function isLoading(r: VersionsResponse): r is LoadingPayload {
  return (r as LoadingPayload).loading === true;
}

async function request(url: string): Promise<{ ok: boolean; status: number; data: unknown }> {
  const res = await fetch(url);
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  return { ok: res.ok, status: res.status, data };
}

export const codeApi = {
  /** Version groups, newest first, plus whether any classes are live in memory. */
  async versions(): Promise<VersionsResponse> {
    const { ok, status, data } = await request('/api/code/versions');
    if (status === 202) return data as LoadingPayload;
    if (!ok) throw new Error(`codeApi.versions: ${status}`);
    return data as { versions: CodeVersion[]; has_live_classes: boolean };
  },

  /** Per-class states at a version; omit version_id for the newest group. */
  async versionClasses(versionId = ''): Promise<CodeClassState[]> {
    const { ok, status, data } = await request(
      `/api/code/version-classes?version_id=${encodeURIComponent(versionId)}`,
    );
    if (status === 202) return [];
    if (!ok) throw new Error(`codeApi.versionClasses: ${status}`);
    return data as CodeClassState[];
  },

  /** Per-class change summary for a version group. */
  async versionChanges(versionId: string): Promise<VersionChange[]> {
    const { ok, status, data } = await request(
      `/api/code/version-changes?version_id=${encodeURIComponent(versionId)}`,
    );
    if (!ok) throw new Error(`codeApi.versionChanges: ${status}`);
    return data as VersionChange[];
  },

  /** Source snapshot lines for a class at a source_hash. */
  async snapshot(sourceHash: string): Promise<SnapshotPayload> {
    const { ok, status, data } = await request(
      `/api/code/snapshot?source_hash=${encodeURIComponent(sourceHash)}`,
    );
    if (!ok) throw new Error(`codeApi.snapshot: ${status}`);
    return data as SnapshotPayload;
  },

  /** Structured unified diff between two source hashes. */
  async diff(hashOld: string, hashNew: string, full = false): Promise<DiffPayload> {
    const { ok, status, data } = await request(
      `/api/code/diff?hash_old=${encodeURIComponent(hashOld)}&hash_new=${encodeURIComponent(hashNew)}` +
        (full ? '&full=1' : ''),
    );
    if (!ok) throw new Error(`codeApi.diff: ${status}`);
    return data as DiffPayload;
  },

  /** Per-class diff between two versions (or a record's base vs live). */
  async versionDiff(params: {
    record_id?: string;
    base_version_id?: string;
    target_version_id?: string;
  }): Promise<VersionDiffPayload> {
    const q = new URLSearchParams();
    if (params.record_id) q.set('record_id', params.record_id);
    if (params.base_version_id) q.set('base_version_id', params.base_version_id);
    if (params.target_version_id) q.set('target_version_id', params.target_version_id);
    const { ok, status, data } = await request(`/api/code/version-diff?${q.toString()}`);
    if (!ok) throw new Error(`codeApi.versionDiff: ${status}`);
    return data as VersionDiffPayload;
  },

  /** Resolve a dep_hash + class_name to the version group and source_hash it was computed at. */
  async resolveDepHash(
    depHash: string,
    className: string,
  ): Promise<{ version_id: string | null; source_hash: string }> {
    const { ok, status, data } = await request(
      `/api/code/resolve-dep-hash?dep_hash=${encodeURIComponent(depHash)}&class_name=${encodeURIComponent(className)}`,
    );
    if (!ok) throw new Error(`codeApi.resolveDepHash: ${status}`);
    return data as { version_id: string | null; source_hash: string };
  },

  /** Resolve a source_hash to the version group it belongs to. */
  async sourceHashVersion(sourceHash: string): Promise<{ version_id: string }> {
    const { ok, status, data } = await request(
      `/api/code/source-hash-version?source_hash=${encodeURIComponent(sourceHash)}`,
    );
    if (!ok) throw new Error(`codeApi.sourceHashVersion: ${status}`);
    return data as { version_id: string };
  },
};
