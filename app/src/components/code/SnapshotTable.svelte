<script lang="ts">
  import type { SnapshotPayload } from '../../lib/apiCode';

  let {
    snapshot,
    onLink,
  }: {
    snapshot: SnapshotPayload;
    onLink?: (cls: string) => void;
  } = $props();
</script>

<table class="source">
  <tbody>
    {#each snapshot.lines as line, i}
      <tr>
        <td class="ln">{i + 1}</td>
        <td class="code">
          {#if line.cls_link}
            <button class="cls-link" title={`Go to ${line.cls_link}`} onclick={() => onLink?.(line.cls_link!)}
              >{line.text}</button
            >
          {:else}
            {line.text}
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .source {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    line-height: 1.6;
    table-layout: fixed;
  }

  td {
    padding: 0 8px;
    vertical-align: top;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .ln {
    width: 44px;
    color: var(--text-3);
    text-align: right;
    user-select: none;
  }

  .code {
    color: var(--text-2);
  }

  .cls-link {
    color: var(--link);
    font: inherit;
    text-align: left;
    padding: 0;
  }

  .cls-link:hover {
    text-decoration: underline;
  }
</style>
