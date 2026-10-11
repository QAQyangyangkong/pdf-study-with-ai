import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react';
import { BookOpen, X } from 'lucide-react';

export function Empty({title,description,action}:{title:string;description:string;action?:ReactNode}) {
  return <div className="empty"><div className="empty-icon"><BookOpen size={30}/></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}) {
  return <div className="modal-scrim"><section role="dialog" aria-modal="true" aria-label={title} className="modal"><header><h2>{title}</h2><button className="icon-button" aria-label="关闭弹窗" onClick={onClose}><X size={20}/></button></header>{children}</section></div>;
}
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}) {
  const id=useId();
  return <div className="field"><label htmlFor={id}>{label}</label>{isValidElement(children)?cloneElement(children as ReactElement<{id?:string;'aria-describedby'?:string}>,{id,'aria-describedby':hint?id+'-hint':undefined}):children}{hint && <small id={id+'-hint'}>{hint}</small>}</div>;
}
export function SectionHeading({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
