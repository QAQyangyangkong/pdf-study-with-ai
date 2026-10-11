import { Editor } from '@tiptap/react';
import { expect, it } from 'vitest';
import { markdownExtensions, needsSourceEditing } from './markdown';

it('preserves headings, formatting, nested lists, tables, tasks, links and code through Markdown round trips', () => {
  const source = '# 欧姆定律\n\n**电阻** 与 *电压*，~~旧值~~，[资料](https://example.com)。\n\n> I = U / R\n\n- 定义\n  - 适用条件\n\n1. 观察\n2. 验证\n\n- [x] 已复习\n- [ ] 待练习\n\n| 电压 | 电流 |\n| --- | --- |\n| 5V | 1A |\n\n```python\nI = U / R\n```';
  const editor = new Editor({ extensions: markdownExtensions(), content: source, contentType: 'markdown' });
  const before = editor.getJSON();
  const markdown = editor.getMarkdown();
  editor.commands.setContent(markdown, { contentType: 'markdown', emitUpdate: false });
  expect(editor.getJSON()).toEqual(before);
  expect(markdown).toContain('**电阻**');
  expect(markdown).toContain('- [x] 已复习');
  expect(markdown).toContain('https://example.com');
  expect(markdown).toContain('```python');
  editor.destroy();
});

it('keeps image references in Markdown without loading the remote image', () => {
  const editor = new Editor({ extensions: markdownExtensions(), content: '![电路图](https://example.com/circuit.png)', contentType: 'markdown' });
  expect(editor.getMarkdown()).toBe('![电路图](https://example.com/circuit.png)');
  expect(editor.getHTML()).not.toContain('<img');
  expect(editor.getHTML()).toContain('电路图');
  editor.destroy();
});

it('serializes rich formatting commands into portable Markdown', () => {
  const editor = new Editor({ extensions: markdownExtensions(), content: '电阻', contentType: 'markdown' });
  editor.commands.selectAll();
  editor.commands.toggleBold();
  editor.commands.toggleHeading({ level: 2 });
  expect(editor.getMarkdown()).toBe('## **电阻**');
  editor.commands.undo();
  expect(editor.getMarkdown()).toBe('**电阻**');
  editor.destroy();
});

it('identifies source-only syntax that must remain editable without conversion', () => {
  expect(needsSourceEditing('[[知识点]]')).toBe(true);
  expect(needsSourceEditing('$$I=U/R$$')).toBe(true);
  expect(needsSourceEditing('<details>说明</details>')).toBe(true);
  expect(needsSourceEditing('<!-- 完整保留批注 -->')).toBe(true);
  expect(needsSourceEditing('电流为 $I=U/R$')).toBe(true);
  expect(needsSourceEditing('# 标题\n\n**重点**')).toBe(false);
});
