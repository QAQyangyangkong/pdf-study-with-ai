import { useEffect, useRef, useState } from 'react';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;

export function PdfPage({url}:{url:string}) {
 const canvas=useRef<HTMLCanvasElement>(null);const [failure,setFailure]=useState('');
 useEffect(()=>{setFailure('');let stopped=false;const loading=getDocument({url});let renderTask:{cancel:()=>void}|null=null;
   void loading.promise.then(async document=>{const page=await document.getPage(1);if(stopped||!canvas.current)return;const width=canvas.current.parentElement?.clientWidth||600;const base=page.getViewport({scale:1});const viewport=page.getViewport({scale:Math.min(2,(width-25)/base.width)});canvas.current.width=viewport.width;canvas.current.height=viewport.height;const task=page.render({canvas:canvas.current,viewport});renderTask=task;await task.promise;}).catch(()=>{if(!stopped)setFailure('页面暂时无法渲染，请尝试其他页。');});
   return()=>{stopped=true;renderTask?.cancel();void loading.destroy();};
 },[url]);
 return failure?<p className="notice">{failure}</p>:<canvas ref={canvas} aria-label="PDF 页面预览" className="pdf-canvas"/>;
}
