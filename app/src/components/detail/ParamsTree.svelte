<script lang="ts">
  import ParamsTree from './ParamsTree.svelte';
  import { HIDDEN_JSON_KEYS } from './apiDetail';

  interface Node {
    key: string;
    leaf: boolean;
    children: unknown | null;
    summary: string | null;
    cls: string | null;
    clsAsKey: boolean;
    value: unknown;
  }

  let {
    data,
    depth = 0,
    filterHidden = false,
    knownClasses = null,
    onClass = null,
  }: {
    data: unknown;
    depth?: number;
    filterHidden?: boolean;
    knownClasses?: Set<string> | null;
    onClass?: ((cls: string) => void) | null;
  } = $props();

  // Port of legacy detail.js buildJsonExplorer / _jxItem, collapsed per key.
  let collapsed = $state<Record<string, boolean>>({});

  const entries = $derived.by(() => {
    if (Array.isArray(data)) return data.map((v, i) => [String(i), v] as const);
    if (data !== null && typeof data === 'object') {
      const src = Object.entries(data as Record<string, unknown>);
      const visible =
        filterHidden && depth === 0 ? src.filter(([k]) => !HIDDEN_JSON_KEYS.has(k)) : src;
      return visible as [string, unknown][];
    }
    return [];
  });

  function isDataRef(v: unknown): v is Record<string, unknown> {
    return (
      v !== null &&
      typeof v === 'object' &&
      !Array.isArray(v) &&
      typeof (v as Record<string, unknown>).class_name === 'string' &&
      'params' in (v as Record<string, unknown>)
    );
  }

  function nodeFor(key: string, value: unknown): Node {
    // Data/TrackedObject reference: {class_name, params, ...} → key → class link.
    if (isDataRef(value)) {
      const inner = (value.params ?? {}) as Record<string, unknown>;
      return {
        key,
        leaf: Object.keys(inner).length === 0,
        children: inner,
        summary: null,
        cls: String(value.class_name),
        clsAsKey: false,
        value: null,
      };
    }
    if (Array.isArray(value)) {
      return {
        key,
        leaf: value.length === 0,
        children: value,
        summary: `[${value.length}]`,
        cls: null,
        clsAsKey: false,
        value: null,
      };
    }
    if (value !== null && typeof value === 'object') {
      const obj = value as Record<string, unknown>;
      const cn = typeof obj.class_name === 'string' ? obj.class_name : null;
      const showLabel = cn !== null && cn !== key;
      let keys = Object.keys(obj);
      if (filterHidden) keys = keys.filter((k) => !HIDDEN_JSON_KEYS.has(k));
      if (cn !== null) keys = keys.filter((k) => k !== 'class_name');
      const children = Object.fromEntries(keys.map((k) => [k, obj[k]]));
      return {
        key,
        leaf: keys.length === 0,
        children,
        summary: null,
        cls: showLabel ? cn : null,
        clsAsKey: cn !== null && !showLabel,
        value: null,
      };
    }
    return { key, leaf: true, children: null, summary: null, cls: null, clsAsKey: false, value };
  }

  function isKnownClass(cn: string): boolean {
    return knownClasses?.has(cn) ?? false;
  }

  function displayValue(v: unknown): string {
    return v === null ? 'null' : String(v);
  }

  function valueClass(v: unknown): string {
    if (v === null) return 'jx-val jx-val--null';
    if (typeof v === 'number') return 'jx-val jx-val--num';
    if (typeof v === 'boolean') return 'jx-val jx-val--bool';
    return 'jx-val';
  }

  function toggle(key: string): void {
    collapsed[key] = !collapsed[key];
  }
</script>

<ul class="jx-list" class:jx-depth-0={depth === 0}>
  {#each entries as [key, raw] (key)}
    {@const node = nodeFor(key, raw)}
    <li class="jx-item">
      <span class="jx-row">
        {#if !node.leaf}
          <button
            class="jx-toggle"
            class:jx-open={!collapsed[key]}
            aria-label={collapsed[key] ? 'expand' : 'collapse'}
            onclick={() => toggle(key)}
          ></button>
        {:else}
          <span class="jx-leaf-dot"></span>
        {/if}
        {#if node.clsAsKey && isKnownClass(key)}
          <button class="jx-key jx-cls" onclick={() => onClass?.(key)}>{key}</button>
        {:else if node.clsAsKey}
          <span class="jx-key">{key}</span>
        {:else if isKnownClass(key)}
          <button class="jx-key jx-cls" onclick={() => onClass?.(key)}>{key}</button>
        {:else}
          <span class="jx-key">{key}</span>
        {/if}
        {#if node.cls && !node.clsAsKey}
          <span class="jx-sep">→</span>
          <button class="jx-cls" onclick={() => onClass?.(node.cls ?? '')}>{node.cls}</button>
        {/if}
        {#if node.summary}
          <span class="jx-dim">{node.summary}</span>
        {/if}
        {#if node.leaf}
          <span class="jx-sep">:</span>
          <span class={valueClass(node.value)}>{displayValue(node.value)}</span>
        {/if}
      </span>
      {#if !node.leaf && !collapsed[key]}
        <ParamsTree
          data={node.children}
          depth={depth + 1}
          {filterHidden}
          {knownClasses}
          {onClass}
        />
      {/if}
    </li>
  {/each}
</ul>
