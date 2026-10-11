import { FileCheck2, ScanText, TrendingUp } from 'lucide-react';
import { SectionHeading } from '../../components/ui';

export function Exams() {
  return <><SectionHeading eyebrow="COMING NEXT" title="试卷分析" description="按规划安排在后续阶段。当前先把教材、章节和笔记流程做稳。"/><section className="panel roadmap-panel"><span className="tag">后续功能</span><h2>让历年考题，成为复习的线索。</h2><p>这个页面暂不提供试卷分析操作。后端已保留基础导入与分析接口，后续加入 OCR 校对和结构化考点统计。</p><div className="roadmap-grid"><div><FileCheck2/><h3>历年试卷管理</h3><p>按课程、年份整理 PDF、Word 与图片材料。</p></div><div><ScanText/><h3>题目与证据</h3><p>提取题目，保留原文、页码和识别校对入口。</p></div><div><TrendingUp/><h3>考点与考情</h3><p>基于实际样本统计出现情况，形成复习清单。</p></div></div></section></>;
}
