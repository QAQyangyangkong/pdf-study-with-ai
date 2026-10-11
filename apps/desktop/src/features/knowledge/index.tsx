import { ArrowRight, Network } from 'lucide-react';
import type { Workspace } from '../../types';
import { Empty, SectionHeading } from '../../components/ui';

export function Knowledge({workspace,onNote}:{workspace:Workspace;onNote:(id:number)=>void}) {
  return <><SectionHeading eyebrow="CONNECT THE DOTS" title="知识体系" description="同一概念可以出现在不同教材中。用共同主题，让它们在这里相遇。"/>{workspace.topics.length?<div className="topic-grid">{workspace.topics.map(topic=><section className="panel topic-card" key={topic.id}><div className="panel-heading"><h2><Network size={20}/>{topic.name}</h2><span className="tag">{topic.note_count} 篇笔记</span></div>{workspace.notes.filter(note=>note.tags.includes(topic.name)).map(note=><button className="topic-note" key={note.id} onClick={()=>onNote(note.id)}><div><b>{note.title}</b><p>{note.sources[0]||'手动笔记'}</p></div><ArrowRight size={16}/></button>)}</section>)}</div>:<section className="panel"><Empty title="让知识从一篇笔记延伸出去" description="在笔记中填写知识主题，相同主题下的不同教材笔记会聚合在这里。"/></section>}</>;
}
