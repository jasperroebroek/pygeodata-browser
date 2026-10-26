<script lang="ts">
  import type { SnapshotPayload } from '../../lib/apiCode';

  let { snapshot, onLink }: { snapshot: SnapshotPayload; onLink?: (cls: string) => void } = $props();
</script>

<table class="diff-table diff-table--inline source-table">
  <tbody>
    {#each snapshot.lines as line, i (i)}
      <tr class="diff-ctx">
        <td class="diff-ln">{i + 1}</td>
        <td class="diff-code"
          >{#if line.cls_link}{@const cls = line.cls_link}<a
              href="#top"
              class="src-cls-link"
              onclick={(e) => (e.preventDefault(), onLink?.(cls))}>{line.text}</a
            >{:else}{line.text}{/if}</td
        >
      </tr>
    {/each}
  </tbody>
</table>
