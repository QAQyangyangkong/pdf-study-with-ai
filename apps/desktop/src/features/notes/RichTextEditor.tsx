import { useEffect, useRef, type ReactNode } from 'react';
import { EditorContent, useEditor, useEditorState, type Editor } from '@tiptap/react';
import { Bold, Italic, Heading2, List, ListOrdered, Quote, Code2, Undo2, Redo2, ListChecks, Table2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { markdownExtensions } from './markdown';

export function RichTextEditor({ value, onChange }: { value: string; onChange: (markdown: string) => void }) {
  const loadedValue = useRef(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const editor = useEditor({
    extensions: markdownExtensions(),
    content: value,
    contentType: 'markdown',
    immediatelyRender: false,
    editorProps: { attributes: { role: 'textbox', 'aria-label': '笔记正文', 'aria-multiline': 'true', class: 'tiptap note-rich-content' } },
    onUpdate: ({ editor: updated }) => {
      const markdown = updated.getMarkdown();
      loadedValue.current = markdown;
      onChangeRef.current(markdown);
    },
  });

  useEffect(() => {
    if (editor && loadedValue.current !== value) {
      editor.commands.setContent(value, { contentType: 'markdown', emitUpdate: false });
      loadedValue.current = value;
    }
  }, [editor, value]);

  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current?.isActive('bold'), italic: current?.isActive('italic'),
      heading: current?.isActive('heading', { level: 2 }),
      bullet: current?.isActive('bulletList'), ordered: current?.isActive('orderedList'),
      quote: current?.isActive('blockquote'), code: current?.isActive('codeBlock'),
      tasks: current?.isActive('taskList'),
      canUndo: current?.can().undo(), canRedo: current?.can().redo(),
    }),
  });

  function tool(label: string, icon: ReactNode, active: boolean | undefined, command: (instance: Editor) => void, disabled = false) {
    return <Button aria-label={label} title={label} variant={active ? 'secondary' : 'ghost'} size="icon" aria-pressed={active} disabled={!editor || disabled} onMouseDown={event => event.preventDefault()} onClick={() => { if (editor) command(editor); }}>{icon}</Button>;
  }

  return <div className="rich-editor-shell">
    <div className="flex flex-wrap items-center gap-1 border-b border-border bg-secondary/40 p-2" role="toolbar" aria-label="正文格式">
      {tool('加粗', <Bold size={16} />, state?.bold, instance => instance.chain().focus().toggleBold().run())}
      {tool('斜体', <Italic size={16} />, state?.italic, instance => instance.chain().focus().toggleItalic().run())}
      {tool('二级标题', <Heading2 size={16} />, state?.heading, instance => instance.chain().focus().toggleHeading({ level: 2 }).run())}
      {tool('项目列表', <List size={16} />, state?.bullet, instance => instance.chain().focus().toggleBulletList().run())}
      {tool('编号列表', <ListOrdered size={16} />, state?.ordered, instance => instance.chain().focus().toggleOrderedList().run())}
      {tool('待办列表', <ListChecks size={16} />, state?.tasks, instance => instance.chain().focus().toggleTaskList().run())}
      {tool('引用', <Quote size={16} />, state?.quote, instance => instance.chain().focus().toggleBlockquote().run())}
      {tool('代码块', <Code2 size={16} />, state?.code, instance => instance.chain().focus().toggleCodeBlock().run())}
      {tool('插入表格', <Table2 size={16} />, undefined, instance => instance.chain().focus().insertTable({ rows: 3, cols: 2, withHeaderRow: true }).run())}
      <span className="mx-1 h-5 border-l border-border" />
      {tool('撤销', <Undo2 size={16} />, undefined, instance => instance.chain().focus().undo().run(), !state?.canUndo)}
      {tool('重做', <Redo2 size={16} />, undefined, instance => instance.chain().focus().redo().run(), !state?.canRedo)}
    </div>
    <EditorContent editor={editor} />
  </div>;
}
