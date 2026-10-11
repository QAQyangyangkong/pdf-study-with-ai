import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Notes } from './index';
import type { Note } from '../../types';

afterEach(()=>{cleanup();vi.restoreAllMocks();});
const props={onSelect:vi.fn(),onDirty:vi.fn(),run:vi.fn()};
it('preserves or discards a new draft according to the confirmation',()=>{
  const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
  render(<Notes {...props} notes={[]} selectedId={null}/>);
  fireEvent.change(screen.getByLabelText('笔记标题'),{target:{value:'新理解'}});
  fireEvent.click(screen.getByRole('button',{name:'新建笔记'}));
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value','新理解');
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole('button',{name:'新建笔记'}));
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value','');
});
it('updates a restored version even when both saves have the same timestamp',()=>{
  const note:Note={id:1,title:'最新标题',body:'最新正文',tags:[],sources:[],kind:'note',updated_at:'2026-10-11T00:00:00'};
  const view=render(<Notes {...props} notes={[note]} selectedId={1}/>);
  view.rerender(<Notes {...props} notes={[{...note,title:'恢复标题',body:'恢复正文'}]} selectedId={1}/>);
  expect(screen.getByLabelText('笔记标题')).toHaveProperty('value','恢复标题');
  expect(screen.getByLabelText('笔记正文')).toHaveProperty('value','恢复正文');
});
