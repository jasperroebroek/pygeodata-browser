export type ModalContent =
  | { kind: 'json'; data: unknown; codeNav: boolean; depHash?: string | null }
  | { kind: 'iframe'; src: string }
  | { kind: 'image'; src: string }
  | { kind: 'html'; html: string; className?: string }
  | { kind: 'graph'; svg: string }
  | { kind: 'diagnostics' }
  | { kind: 'clean'; target: 'cache' | 'source' };

export interface ModalState {
  title: string;
  size: '' | 'sm' | 'md';
  content: ModalContent;
}

export const modal = $state({ current: null as ModalState | null });

export function openModal(title: string, content: ModalContent, size: ModalState['size'] = '') {
  modal.current = { title, content, size };
}

export function closeModal() {
  modal.current = null;
}
