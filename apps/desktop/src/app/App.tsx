import { useEffect, useRef, useState } from 'react';
import { BookOpen, Check, ChevronRight, CircleHelp, FileText, FolderOpen, Home, LibraryBig, LoaderCircle, Network, Settings2, ShieldCheck, Sparkles } from 'lucide-react';
import type { Page, Prepared, Task } from '../types';
import { useWorkspace } from '../hooks/useWorkspace';
import { rpc } from '../services/backend';
import { NavigationContext } from '../stores/navigation';
import { Modal } from '../components/ui';
import { Dashboard } from '../features/dashboard';
import { Library } from '../features/library';
import { Reader } from '../features/reader';
import { Notes } from '../features/notes';
import { Knowledge } from '../features/knowledge';
import { Exams } from '../features/exams';
import { AISettings } from '../features/ai-settings';
import { Backup } from '../features/backup';
import { Onboarding } from '../features/onboarding';
import { invoke, isTauri } from '@tauri-apps/api/core';

const pages:{id:Page;label:string;icon:typeof Home;group?:boolean}[]=[
 {id:'dashboard',label:'今日工作台',icon:Home},{id:'library',label:'我的教材',icon:LibraryBig},
 {id:'reader',label:'阅读与分章',icon:BookOpen},{id:'notes',label:'我的笔记',icon:FileText},
 {id:'knowledge',label:'知识体系',icon:Network},{id:'exams',label:'试卷分析',icon:FolderOpen},
 {id:'ai-settings',label:'AI 与模型',icon:Settings2,group:true},{id:'backup',label:'备份与导出',icon:ShieldCheck},
];

export function App(){
 const {workspace,refresh,error}=useWorkspace();const [page,setPage]=useState<Page>('dashboard');const [bookId,setBookId]=useState<number|null>(null);const [noteId,setNoteId]=useState<number|null>(null);const dirty=useRef(false);const running=useRef(false);
 const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [failure,setFailure]=useState('');const [prepared,setPrepared]=useState<Prepared|null>(null);const [taskId,setTaskId]=useState<string|null>(null);
 useEffect(()=>{if(workspace&&isTauri())void invoke('frontend_ready',{report:{version:workspace.version,schema_version:workspace.schema_version}}).catch(()=>{});},[workspace?.version]);
 function discard(){if(!dirty.current)return true;if(window.confirm('当前笔记有未保存的修改，离开会丢弃这些修改。是否继续？')){dirty.current=false;return true;}return false;}
 function navigate(next:Page){if(next!==page && !discard())return;setPage(next);setFailure('');}
 function selectNote(id:number|null){if(!discard())return;setNoteId(id);setPage('notes');}
 async function run(work:()=>Promise<unknown>,message:string){if(running.current){setFailure('当前操作尚未完成，请稍后再试。');return;}running.current=true;setBusy(true);setFailure('');try{await work();await refresh();if(message)setNotice(message);}catch(error){setFailure(error instanceof Error?error.message:'操作未完成。');}finally{running.current=false;setBusy(false);}}
 async function prepare(kind:'chapter'|'connection',params:Record<string,unknown>={}){if(taskId){setFailure('上一项生成任务尚未完成。');return;}await run(async()=>setPrepared(await rpc<Prepared>('generation.prepare',{kind,...params})),'');}
 useEffect(()=>{const onUnload=(event:BeforeUnloadEvent)=>{if(dirty.current||taskId){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',onUnload);return()=>window.removeEventListener('beforeunload',onUnload);},[taskId]);
 useEffect(()=>{if(!taskId)return;let stopped=false;const timer=window.setInterval(()=>{void rpc<Task>('tasks.get',{task_id:taskId}).then(async task=>{if(stopped)return;if(task.status==='completed'){setTaskId(null);setNotice(task.result?.cached?'已使用本地缓存，本次没有调用费用。':'生成已完成，结果已保存。');await refresh();if(task.result?.note_id&&!dirty.current){setNoteId(task.result.note_id);setPage('notes');}}else if(task.status==='failed'){setTaskId(null);setFailure(task.error||'生成未完成。');await refresh();}}).catch(error=>{if(!stopped){setTaskId(null);setFailure(error.message);}});},700);return()=>{stopped=true;window.clearInterval(timer);};},[taskId,refresh]);
 if(!workspace)return <div className="startup"><div className="brand-icon"><BookOpen/></div><h1>StudyNote</h1><p>{error||'正在打开本地学习工作区…'}</p>{error&&<button className="primary" onClick={()=>void refresh()}>重新连接</button>}</div>;
 const nav=pages.find(item=>item.id===page)!;
 return <NavigationContext.Provider value={navigate}><div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-icon"><BookOpen size={25}/></div><div><strong>StudyNote</strong><span>把知识留在自己手中</span></div></div><div className="sidebar-heading">学习空间</div><nav aria-label="主导航">{pages.map(item=><button key={item.id} disabled={busy} className={`${page===item.id?'active':''} ${item.group?'nav-divider':''}`} onClick={()=>navigate(item.id)}><item.icon size={19}/><span>{item.label}</span>{item.id==='exams'&&<small>稍后</small>}</button>)}</nav><div className="sidebar-bottom"><div className="local-badge"><span/>本地工作区 <ShieldCheck size={15}/></div><p>资料保存在本机<br/>按自己的节奏学习</p><button className="text-button" onClick={()=>window.alert('先导入教材，拆分小章节并核对文字。配置自己的 AI 后，预览材料再生成笔记；也可以完全离线编辑与导出。')}><CircleHelp size={15}/>使用提示</button></div></aside><div className="main-shell"><header className="topbar"><span>我的工作区 <ChevronRight size={14}/><b>{nav.label}</b></span><div><span className="topbar-local"><span/>本地保存</span><div className="avatar">学</div></div></header><main><fieldset className="work-content" disabled={busy}>{page==='dashboard'&&<Dashboard workspace={workspace} navigate={navigate}/>} {page==='library'&&<Library documents={workspace.documents} run={run} onRead={id=>{setBookId(id);navigate('reader');}}/>} {page==='reader'&&<Reader documents={workspace.documents} chapters={workspace.chapters} selectedId={bookId} onSelect={setBookId} run={run} onGenerate={(chapter_id,preference,secondary)=>prepare('chapter',{chapter_id,preference,secondary})}/>} {page==='notes'&&<Notes notes={workspace.notes} selectedId={noteId} onSelect={selectNote} onDirty={value=>{dirty.current=value;}} run={run}/>} {page==='knowledge'&&<Knowledge workspace={workspace} onNote={selectNote}/>} {page==='exams'&&<Exams/>} {page==='ai-settings'&&<AISettings key={workspace.config.model+workspace.key_configured} config={workspace.config} keyConfigured={workspace.key_configured} run={run} onTest={secondary=>prepare('connection',{secondary})}/>} {page==='backup'&&<Backup directory={workspace.data_directory} run={run}/>}</fieldset></main><footer className="statusbar" role="status"><span>{busy||taskId?<LoaderCircle className="spin" size={15}/>:<Check size={14}/>} {taskId?'AI 正在生成，完成后会保存到笔记库。':busy?'正在处理…':notice||'准备就绪 · 本地优先，按章节学习'}</span><span>StudyNote {workspace.version}</span></footer></div>{(failure||error)&&<div className="error-toast" role="alert"><span>{failure||error}</span><button className="text-button" onClick={()=>setFailure('')}>知道了</button></div>}{!workspace.onboarding_complete&&<Onboarding complete={()=>void run(()=>rpc('onboarding.complete'),'欢迎开始学习')} settings={()=>void run(async()=>{await rpc('onboarding.complete');setPage('ai-settings');},'')}/>} {prepared&&<Modal title={prepared.cached?'使用已生成的内容':'确认生成笔记'} onClose={()=>setPrepared(null)}><div className="request-summary"><Sparkles size={23}/><div><b>{prepared.model}</b><p>{prepared.cached?'命中本地缓存，无需联网':`费用保守估算 $${prepared.amount.toFixed(5)} USD`}</p></div></div><p className="muted">{prepared.cached?'本次不会发送资料。':`将以下文字发送至 ${prepared.endpoint}`}</p><pre className="request-preview">{prepared.prompt}</pre><div className="notice">只发送预览中的文字与学习偏好。扫描件、公式和复杂排版请先核对。</div><div className="modal-actions"><button className="secondary" onClick={()=>setPrepared(null)}>取消</button><button className="primary" onClick={()=>void run(async()=>{const result=await rpc<{task_id:string}>('generation.start',{token:prepared.token});setTaskId(result.task_id);setPrepared(null);},'')}>{prepared.cached?'使用缓存':'确认生成'}</button></div></Modal>}</div></NavigationContext.Provider>;
}
