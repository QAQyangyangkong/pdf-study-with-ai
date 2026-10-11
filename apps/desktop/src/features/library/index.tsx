import { useState } from 'react';
import { ArrowRight, BookOpen, Plus, Search } from 'lucide-react';
import type { Document } from '../../types';
import { Empty, Field, Modal, SectionHeading } from '../../components/ui';
import { pickFile, rpc } from '../../services/backend';

export function Library({documents,onRead,run}:{documents:Document[];onRead:(id:number)=>void;run:(work:()=>Promise<unknown>,message:string)=>Promise<void>}) {
  const [query,setQuery]=useState(''); const [importing,setImporting]=useState(false); const [path,setPath]=useState(''); const [course,setCourse]=useState('');
  const books=documents.filter(document=>document.kind==='textbook' && (document.title+document.course).toLowerCase().includes(query.toLowerCase()));
  async function choose() { const result=await pickFile(); if(result){setPath(result);setImporting(true);} }
  return <><SectionHeading eyebrow="TEXTBOOK LIBRARY" title="我的教材" description="把整本教材分成小章节，让阅读与笔记更轻松。" action={<button className="primary" onClick={()=>void run(choose,'') }><Plus size={18}/>导入教材</button>}/><div className="library-toolbar"><span className="filter-chip">全部教材 <b>{documents.filter(d=>d.kind==='textbook').length}</b></span><label className="search-input"><Search size={18}/><input aria-label="搜索教材" value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索教材或课程"/></label></div>
  {books.length ? <div className="book-grid">{books.map((book,index)=><article className="book-card" key={book.id}><div className={`book-cover cover-${index%3}`}><span>{book.course || '学习资料'}</span><BookOpen size={43}/><h3>{book.title}</h3><small>PDF · {book.pages} PAGES</small></div><div className="book-details"><h3>{book.title}</h3><p>{book.course || '未分类课程'} · {book.pages} 页</p><button className="text-button" onClick={()=>onRead(book.id)}>阅读与分章 <ArrowRight size={16}/></button></div></article>)}</div> : <section className="panel"><Empty title={query ? '没有匹配的教材' : '教材库还没有书'} description={query ? '换一个关键词试试看。' : '支持 PDF 文件。导入后原文件保持原样，资料存入本地工作区。'} action={!query && <button className="primary" onClick={()=>void run(choose,'') }><Plus size={17}/>导入第一本教材</button>}/></section>}
  {importing && <Modal title="导入教材" onClose={()=>setImporting(false)}><Field label="已选择文件"><input value={path} readOnly/></Field><Field label="课程名称" hint="相同课程的教材可以一起组织知识。"><input placeholder="例如：电路基础" value={course} onChange={e=>setCourse(e.target.value)}/></Field><div className="modal-actions"><button className="secondary" onClick={()=>setImporting(false)}>取消</button><button className="primary" onClick={()=>void run(async()=>{await rpc('documents.import',{path,kind:'textbook',course});setImporting(false);},'教材已导入')}>确认导入</button></div></Modal>}
  </>;
}
