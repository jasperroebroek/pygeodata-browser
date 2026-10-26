import { app } from './stores.svelte';

/** Jump to the code view with a class (optionally pinned to a source hash) open. */
export function navigateToCodeClass(className: string, sourceHash?: string) {
  app.codeTarget = { className, sourceHash };
  app.diffRecordId = null;
  app.view = 'code';
}

/** Jump to the code view showing the entry's version diff (what changed for it). */
export function showWhatChanged(recordId: string) {
  app.diffRecordId = recordId;
  app.codeTarget = null;
  app.view = 'code';
}

/** Consume a pending code navigation target (CodeView calls this once). */
export function takeCodeTarget() {
  const target = app.codeTarget;
  app.codeTarget = null;
  return target;
}

export function takeDiffRecordId() {
  const id = app.diffRecordId;
  app.diffRecordId = null;
  return id;
}
