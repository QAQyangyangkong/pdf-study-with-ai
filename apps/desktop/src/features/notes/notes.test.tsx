import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, expect, it, vi } from 'vitest';
import { Notes } from './index';
import type { Note } from '../../types';

const mock = vi.hoisted(() => ({ rpc: vi.fn() }));
vi.mock('../../services/backend', () => ({ rpc: mock.rpc }));
beforeAll(() => {
  Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
  Range.prototype.getBoundingClientRect = () => new DOMRect();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); mock.rpc.mockReset(); });
const props = { onSelect: vi.fn(), onDirty: vi.fn(), run: async (work: () => Promise<unknown>) => { await work(); } };
const note: Note = { id: 1, title: '最新标题', body: '最新正文', tags: ['电路'], sources: ['教材 p.1–2'], kind: 'note', updated_at: '2026-10-11T00:00:00' };

it('preserves or discards a new draft according to the confirmation', () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  render(<Notes {...props} notes={[]} selectedId={null} />);
  fireEvent.change(screen.getByLabelText('笔记标题'), { target: { value: '新理解' } });
  fireEvent.click(screen.getByRole('button', { name: '新建笔记' }));
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value', '新理解');
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole('button', { name: '新建笔记' }));
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value', '');
});

it('updates a restored version even when both saves have the same timestamp', async () => {
  const view = render(<Notes {...props} notes={[note]} selectedId={1} />);
  view.rerender(<Notes {...props} notes={[{ ...note, title: '恢复标题', body: '恢复正文' }]} selectedId={1} />);
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value', '恢复标题');
  await waitFor(() => expect(screen.getByRole('textbox', { name: '笔记正文' }).textContent).toContain('恢复正文'));
});

it('keeps original Markdown unchanged and clean when switching modes without edits', async () => {
  const original = '# 理解\n\n__加粗__ 与 *斜体*\n\n- 项目一\n- 项目二\n';
  const onDirty = vi.fn();
  render(<Notes {...props} onDirty={onDirty} notes={[{ ...note, body: original }]} selectedId={1} />);
  await waitFor(() => expect(screen.getByRole('textbox', { name: '笔记正文' }).querySelector('strong')?.textContent).toBe('加粗'));
  onDirty.mockClear();
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 原文' }));
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value', original);
  fireEvent.click(screen.getByRole('button', { name: '阅读预览' }));
  fireEvent.click(screen.getByRole('button', { name: '富文本' }));
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 原文' }));
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value', original);
  expect(onDirty).not.toHaveBeenCalledWith(true);
});

it('saves source edits as Markdown and leaves provenance to the backend', async () => {
  mock.rpc.mockResolvedValue({ note_id: 1 });
  const onDirty = vi.fn();
  render(<Notes {...props} onDirty={onDirty} notes={[note]} selectedId={1} />);
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 原文' }));
  fireEvent.change(screen.getByLabelText('笔记正文'), { target: { value: '## 新理解\n\n**电阻**' } });
  expect(onDirty).toHaveBeenLastCalledWith(true);
  fireEvent.click(screen.getByRole('button', { name: '保存笔记' }));
  await waitFor(() => expect(mock.rpc).toHaveBeenCalledWith('notes.save', { note_id: 1, title: '最新标题', body: '## 新理解\n\n**电阻**', tags: ['电路'] }));
  expect(onDirty).toHaveBeenLastCalledWith(false);
});

it('preserves source-only syntax instead of dropping it through rich-text parsing', () => {
  const body = '---\nsubject: 电路\n---\n\n<!-- 复习批注 -->\n\n[[欧姆定律]]\n\n$$I=U/R$$';
  render(<Notes {...props} notes={[{ ...note, body }]} selectedId={1} />);
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value', body);
  expect(screen.getByText(/当前使用原文编辑以保留这些内容/)).toBeTruthy();
});

it('retains HTML comments exactly when switching between source and rich modes', () => {
  const body = '# 笔记\n\n<!-- 下次复习时检查条件 -->\n\n欧姆定律';
  render(<Notes {...props} notes={[{ ...note, body }]} selectedId={1} />);
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value', body);
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 原文' }));
  fireEvent.click(screen.getByRole('button', { name: '富文本' }));
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value', body);
});

it('uses backend full-text search and an explicit theme filter', async () => {
  const match = { ...note, id: 2, title: '后端排序的命中', body: '欧姆定律适用条件' };
  mock.rpc.mockResolvedValue({ notes: [match] });
  render(<Notes {...props} notes={[note]} selectedId={null} />);
  fireEvent.change(screen.getByLabelText('搜索笔记'), { target: { value: '欧姆定律' } });
  fireEvent.change(screen.getByLabelText('知识主题筛选'), { target: { value: '电路' } });
  await waitFor(() => expect(mock.rpc).toHaveBeenCalledWith('notes.search', { query: '欧姆定律', topic: '电路' }));
  expect(await screen.findByRole('heading', { name: '后端排序的命中' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: '最新标题' })).toBeNull();
});

it('ignores an older search response after the query changes', async () => {
  let firstResolve: (response: { notes: Note[] }) => void = () => {};
  mock.rpc.mockImplementation(async (_method: string, params: { query: string }) => params.query === '电压' ? new Promise(resolve => { firstResolve = resolve; }) : { notes: [{ ...note, id: 2, title: '最新搜索结果' }] });
  render(<Notes {...props} notes={[note]} selectedId={null} />);
  fireEvent.change(screen.getByLabelText('搜索笔记'), { target: { value: '电压' } });
  await waitFor(() => expect(mock.rpc).toHaveBeenCalledWith('notes.search', { query: '电压', topic: '' }));
  fireEvent.change(screen.getByLabelText('搜索笔记'), { target: { value: '电阻' } });
  expect(await screen.findByRole('heading', { name: '最新搜索结果' })).toBeTruthy();
  firstResolve({ notes: [{ ...note, title: '过期结果' }] });
  await waitFor(() => expect(screen.queryByRole('heading', { name: '过期结果' })).toBeNull());
  expect(screen.getByRole('heading', { name: '最新搜索结果' })).toBeTruthy();
});

it('restores a selected historical version through the backend after confirmation', async () => {
  mock.rpc.mockImplementation(async (method: string) => method === 'notes.versions' ? { versions: [{ id: 4, title: '原始理解', body: '正文', created_at: '2026-10-10' }] } : {});
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  render(<Notes {...props} notes={[note]} selectedId={1} />);
  fireEvent.click(screen.getByRole('button', { name: '历史版本' }));
  fireEvent.click(await screen.findByRole('button', { name: '恢复此版本' }));
  await waitFor(() => expect(mock.rpc).toHaveBeenCalledWith('notes.restore', { note_id: 1, version_id: 4 }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});
