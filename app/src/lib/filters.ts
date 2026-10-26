export const FILTER_TARGETS: [string, string][] = [
  ['all', 'All'],
  ['class', 'Class'],
  ['crs', 'CRS'],
  ['key_group', 'Group'],
  ['key', 'Key'],
  ['value', 'Value'],
  ['path', 'Path'],
  ['has_warnings', 'Has warnings'],
  ['has_error', 'Has error'],
];

// [value, word label, pill symbol]
export const FILTER_OPERATORS: [string, string, string][] = [
  ['contains', 'contains', '~'],
  ['equals', 'equals', '='],
  ['starts', 'starts with', '^'],
  ['not_contains', 'not contains', '!~'],
];

export const SPEC_DIMENSIONS: { key: string; label: string; pill: string; wide?: boolean }[] = [
  { key: 'crs', label: 'CRS', pill: 'CRS' },
  { key: 'resolution', label: 'Resolution', pill: 'Res', wide: true },
  { key: 'shape', label: 'Shape', pill: 'Shape', wide: true },
  { key: 'bounds', label: 'Bounds', pill: 'Bounds', wide: true },
];
