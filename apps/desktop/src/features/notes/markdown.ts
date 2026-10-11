import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import { TableKit } from '@tiptap/extension-table';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Image from '@tiptap/extension-image';

// Preserve image references in Markdown without fetching external resources
// while a user is reading or editing a local note.
const LocalImageReference = Image.extend({
  renderHTML({ HTMLAttributes }) {
    return ['span', { class: 'note-image-reference' }, `图片：${HTMLAttributes.alt || '附件'}（原文保留链接）`];
  },
});

export function markdownExtensions() {
  return [
    StarterKit.configure({
      underline: false,
      trailingNode: false,
      link: { openOnClick: false, autolink: false, linkOnPaste: false },
    }),
    TableKit,
    TaskList,
    TaskItem.configure({ nested: true }),
    LocalImageReference.configure({ allowBase64: true }),
    Markdown.configure({ markedOptions: { gfm: true } }),
  ];
}

// These source-only syntaxes have no editor node yet. Keep the original text
// editable instead of silently dropping metadata during a rich-text edit.
export function needsSourceEditing(markdown: string) {
  return /(^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$))|<!--|<\/?[a-z][^>]*>|\[\[[^\]]+\]\]|\[\^[^\]]+\]|\$[^\r\n]*\$|\\[([]|^>\s*\[![^\]]+\]/im.test(markdown);
}
