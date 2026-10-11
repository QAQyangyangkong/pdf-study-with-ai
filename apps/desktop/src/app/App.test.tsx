import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { Workspace } from '../types';

const mock=vi.hoisted(()=>({rpc:vi.fn()}));
vi.mock('../services/backend',()=>({rpc:mock.rpc,pickFile:vi.fn(),pickDestination:vi.fn()}));
vi.mock('../components/PdfPage',()=>({PdfPage:()=>null}));
const base:Workspace={version:'0.2.0',schema_version:2,data_directory:'test-data',onboarding_complete:false,
 documents:[],chapters:[],notes:[],topics:[],spent:0,key_configured:false,
 config:{base_url:'https://api.deepseek.com',model:'deepseek-flash',secondary_model:'',daily_budget:1,input_price:.3,output_price:1.2,secondary_input_price:1.32,secondary_output_price:3.96,max_output_tokens:2000}};
afterEach(()=>{cleanup();mock.rpc.mockReset();});

describe('StudyNote workspace',()=>{
 it('allows offline onboarding without entering a key',async()=>{
   let completed=false;mock.rpc.mockImplementation(async(method:string)=>method==='onboarding.complete'?(completed=true,{}):({...base,onboarding_complete:completed}));
   render(<App/>);expect(await screen.findByRole('dialog',{name:'欢迎来到 StudyNote'})).toBeTruthy();
   fireEvent.click(screen.getByRole('button',{name:'先离线使用'}));
   await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
   expect(screen.getByRole('heading',{name:'让每一次阅读，都有积累。'})).toBeTruthy();
   expect(mock.rpc).toHaveBeenCalledWith('onboarding.complete');
 });
 it('shows the requested later-stage exam boundary',async()=>{
   mock.rpc.mockResolvedValue({...base,onboarding_complete:true});render(<App/>);
   await screen.findByRole('heading',{name:'让每一次阅读，都有积累。'});
   fireEvent.click(screen.getByRole('button',{name:/试卷分析/}));
   expect(screen.getByText('这个页面暂不提供试卷分析操作。后端已保留基础导入与分析接口，后续加入 OCR 校对和结构化考点统计。')).toBeTruthy();
 });
 it('blocks navigation when a note has unsaved changes and the user cancels',async()=>{
   mock.rpc.mockResolvedValue({...base,onboarding_complete:true});vi.spyOn(window,'confirm').mockReturnValue(false);
   render(<App/>);await screen.findByRole('heading',{name:'让每一次阅读，都有积累。'});
   fireEvent.click(screen.getByRole('button',{name:'我的笔记'}));
   fireEvent.change(screen.getByRole('textbox',{name:'笔记标题'}),{target:{value:'未保存的理解'}});
   fireEvent.click(screen.getByRole('button',{name:'我的教材'}));
   expect(window.confirm).toHaveBeenCalled();expect(screen.getByRole('textbox',{name:'笔记标题'})).toBeTruthy();
 });
 it('does not expose a saved API key when opening settings',async()=>{
   mock.rpc.mockResolvedValue({...base,key_configured:true,onboarding_complete:true});render(<App/>);
   await screen.findByRole('heading',{name:'让每一次阅读，都有积累。'});
   fireEvent.click(screen.getByRole('button',{name:'AI 与模型'}));
   expect((screen.getByLabelText('API Key') as HTMLInputElement).value).toBe('');
 });
});
