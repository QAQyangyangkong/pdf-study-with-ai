import { BookOpen, FilePenLine, Network } from 'lucide-react';
import { Modal } from '../../components/ui';

export function Onboarding({complete,settings}:{complete:()=>void;settings:()=>void}) {
  return <Modal title="欢迎来到 StudyNote" onClose={complete}>
    <p className="lead">从一本教材开始，把零散的阅读整理成可以复习的知识。</p>
    <div className="onboarding-steps">
      <div><BookOpen/><h3>01 · 导入教材</h3><p>选择本机 PDF，按章节拆分，核对原始页码。</p></div>
      <div><FilePenLine/><h3>02 · 生成笔记</h3><p>配置自己的 AI 模型，按学习偏好生成，也可以手动写。</p></div>
      <div><Network/><h3>03 · 连接知识</h3><p>通过共同主题连接不同教材，导出到 Obsidian。</p></div>
    </div>
    <div className="notice">教材和笔记保存在本机。确认 AI 请求后，才会发送你预览过的文字。</div>
    <div className="modal-actions"><button className="secondary" onClick={complete}>先离线使用</button><button className="primary" onClick={settings}>配置我的 AI</button></div>
  </Modal>;
}
