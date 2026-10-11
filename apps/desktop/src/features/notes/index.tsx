import { useEffect, useState } from 'react';
import { FileText, History, Plus, Save, Search } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Note } from '../../types';
import { Empty, Field, Modal, SectionHeading } from '../../components/ui';
import { Button } from '../../components/ui/button';
import { Input, Textarea } from '../../components/ui/input';
import { rpc } from '../../services/backend';
import { RichTextEditor } from './RichTextEditor';
import { needsSourceEditing } from './markdown';

type Version = { id: number; title: string; body: string; created_at: string };
type Mode = 'rich' | 'source' | 'preview';
type Props = {
  notes: Note[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onDirty: (dirty: boolean) => void;
  run: (work: () => Promise<unknown>, message: string) => Promise<void>;
};

export function Notes({ notes, selectedId, onSelect, onDirty, run }: Props) {
  const [query, setQuery] = useState('');
  const [topic, setTopic] = useState('');
  const [results, setResults] = useState<Note[]>(notes);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [tags, setTags] = useState('');
  const [mode, setMode] = useState<Mode>('rich');
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [baseline, setBaseline] = useState('');
  const note = notes.find(item => item.id === selectedId);
  const dirty = JSON.stringify([title, body, tags]) !== baseline;
  const sourceOnly = needsSourceEditing(body);

  useEffect(() => {
    const values = [note?.title || '', note?.body || '', note?.tags.join(', ') || ''];
    setTitle(values[0]); setBody(values[1]); setTags(values[2]);
    setBaseline(JSON.stringify(values));
    onDirty(false);
  }, [selectedId, note?.updated_at, note?.title, note?.body, note?.tags.join(', ')]);

  useEffect(() => { onDirty(dirty); }, [dirty]);

  useEffect(() => {
    let current = true;
    if (!query.trim() && !topic) {
      setResults(notes); setSearching(false); setSearchError('');
      return;
    }
    setSearching(true); setSearchError('');
    const timer = window.setTimeout(() => {
      void rpc<{ notes: Note[] }>('notes.search', { query: query.trim(), topic }).then(response => {
        if (current) { setResults(response.notes); setSearching(false); }
      }).catch(error => {
        if (current) { setSearchError(error instanceof Error ? error.message : '搜索未完成'); setSearching(false); }
      });
    }, 250);
    return () => { current = false; window.clearTimeout(timer); };
  }, [query, topic, notes]);

  function newNote() {
    if (selectedId !== null) { onSelect(null); return; }
    if (dirty && !window.confirm('丢弃当前未保存的新笔记？')) return;
    setTitle(''); setBody(''); setTags(''); setBaseline(JSON.stringify(['', '', '']));
    onDirty(false);
  }

  async function saveNote() {
    const result = await rpc<{ note_id: number }>('notes.save', {
      note_id: selectedId, title, body,
      tags: tags.replaceAll('，', ',').split(',').map(tag => tag.trim()).filter(Boolean),
    });
    setBaseline(JSON.stringify([title, body, tags])); onDirty(false); onSelect(result.note_id);
  }

  return <>
    <SectionHeading eyebrow="MAKE IT YOUR OWN" title="我的笔记" description="记录理解，而不只是复制。编辑、补充，再把相关知识连接起来。" action={<Button onClick={newNote}><Plus size={17} />新建笔记</Button>} />
    <div className="notes-layout">
      <aside className="panel notes-list">
        <label className="search-input"><Search size={17} /><input aria-label="搜索笔记" placeholder="全文搜索笔记" value={query} onChange={event => setQuery(event.target.value)} /></label>
        <select className="topic-filter" aria-label="知识主题筛选" value={topic} onChange={event => setTopic(event.target.value)}><option value="">全部知识主题</option>{[...new Set(notes.flatMap(item => item.tags))].sort().map(tag => <option key={tag} value={tag}>{tag}</option>)}</select>
        {searching && <p className="muted" role="status">正在搜索本地笔记…</p>}
        {searchError && <p className="danger" role="alert">{searchError}</p>}
        {!searching && !searchError && results.map(item => <button className={`note-row ${item.id === selectedId ? 'selected' : ''}`} key={item.id} onClick={() => onSelect(item.id)}><div><FileText size={16} /><h3>{item.title}</h3></div><p>{item.body.replace(/[#*`]/g, '').slice(0, 65)}</p><span>{item.tags.slice(0, 2).join(' · ') || '未设置知识主题'}</span></button>)}
        {!searching && !searchError && !results.length && <Empty title={query || topic ? '没有匹配的笔记' : '写下第一条理解'} description={query || topic ? '试试其他关键词，或更改知识主题筛选。' : '创建手动笔记，或从教材章节生成。'} />}
      </aside>
      <section className="panel note-editor">
        <div className="editor-toolbar"><span className="tag">{note ? '学习笔记' : '新笔记'}</span>{note && <Button variant="ghost" size="sm" onClick={() => void run(async () => { setVersions((await rpc<{ versions: Version[] }>('notes.versions', { note_id: note.id })).versions); }, '')}><History size={16} />历史版本</Button>}</div>
        <Field label="笔记标题"><Input className="note-title-input" aria-label="笔记标题" placeholder="为这篇笔记起个名字" value={title} onChange={event => setTitle(event.target.value)} /></Field>
        <Field label="知识主题" hint="用逗号分隔。相同主题可以连接不同教材的笔记。"><Input aria-label="知识主题" placeholder="例如：电路, 欧姆定律" value={tags} onChange={event => setTags(event.target.value)} /></Field>
        <div className="mb-3 flex flex-wrap items-center gap-1" role="group" aria-label="笔记编辑模式">
          {([['rich', '富文本'], ['source', 'Markdown 原文'], ['preview', '阅读预览']] as const).map(([value, label]) => <Button key={value} variant={mode === value ? 'secondary' : 'ghost'} size="sm" aria-pressed={mode === value} onClick={() => setMode(value)}>{label}</Button>)}
          <span className="ml-auto text-[10px] text-muted-foreground">正文以 Markdown 保存</span>
        </div>
        {mode === 'preview' ? <div className="markdown-preview"><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={{img: ({alt})=><span className="note-image-reference">图片：{alt || '附件'}（原文保留链接）</span>}}>{body || '暂无正文。'}</ReactMarkdown></div>
          : mode === 'source' || sourceOnly ? <>{sourceOnly && mode === 'rich' && <p className="notice mb-3">正文含公式、HTML 或 Obsidian 扩展语法，当前使用原文编辑以保留这些内容。</p>}<Textarea className="markdown-editor" aria-label="笔记正文" value={body} onChange={event => setBody(event.target.value)} placeholder="用 Markdown 记下概念、例子和你的思考…" /></>
          : <RichTextEditor value={body} onChange={setBody} />}
        <div className="source-label"><b>材料来源</b><p>{note?.sources.join('；') || '手动创建的笔记'}</p></div>
        <div className="editor-bottom"><span className="muted">{dirty ? '有未保存的修改 · ' : ''}保存时自动保留历史版本</span><Button onClick={() => void run(saveNote, '笔记已保存')}><Save size={16} />保存笔记</Button></div>
      </section>
    </div>
    {versions && <Modal title="笔记历史版本" onClose={() => setVersions(null)}><div className="versions-list">{versions.map(version => <div key={version.id}><div><b>{version.title}</b><p>{version.created_at}</p></div><Button variant="outline" onClick={() => {
      if (window.confirm('恢复这个版本？未保存的修改将被替换，当前已保存的内容会保留在历史中。')) void run(async () => { await rpc('notes.restore', { note_id: selectedId, version_id: version.id }); setVersions(null); onDirty(false); }, '已恢复笔记版本');
    }}>恢复此版本</Button></div>)}</div></Modal>}
  </>;
}
