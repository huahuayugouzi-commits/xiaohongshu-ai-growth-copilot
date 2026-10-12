export interface Insight { hypothesis: string; evidence: { field: string; quote: string }[] }
export interface Analysis {
  schema_version: number; status: 'running' | 'failed' | 'succeeded'; run_id: string;
  research_id: string; error: string | null;
  result: ({ missing_information: string[] } & Record<string, Insight[] | string[]>) | null;
}
const sections = [['title_analysis', '标题'], ['hook', 'Hook'], ['content_structure', '内容结构'],
  ['keywords', '关键词'], ['comment_feedback', '评论反馈'], ['audience_pain_points', '用户痛点'],
  ['popularity_hypotheses', '可能吸引互动的原因（未验证）'], ['reusable_patterns', '可借鉴模式']];

export default function ResearchCard({ analysis }: { analysis: Analysis | null }) {
  if (!analysis) return null;
  if (analysis.status === 'running') return <p role="status">分析处理中；刷新后可查看状态。异常中断时可手动标记失败。</p>;
  if (analysis.status === 'failed') return <div className="gc-error" role="alert">{analysis.error || '分析失败，请重试。'}</div>;
  if (!analysis.result) return null;
  return <section aria-label="Structured Research Card">
    <h3>Structured Research Card</h3><p className="gc-small">AI HYPOTHESIS：单篇分析不证明爆款原因或增长效果。引用来自手动录入，未经外部核验。</p>
    {sections.map(([key, title]) => <div key={key}><h4>{title}</h4>
      {(analysis.result![key] as Insight[]).length ? (analysis.result![key] as Insight[]).map((item, i) => <div key={i}>
        <p><span className="gc-badge gc-orange">假设</span> {item.hypothesis}</p>
        {item.evidence.map((ref, j) => <blockquote key={j}><span className="gc-badge gc-green">原文引用 · {ref.field}</span> {ref.quote}</blockquote>)}
      </div>) : <p>未提供足够依据，暂不判断。</p>}
    </div>)}
    <div className="gc-notice"><h4>Missing Information</h4><ul>{analysis.result.missing_information.map((v, i) => <li key={i}>{v}</li>)}</ul></div>
    <p className="gc-small">ResearchItem: {analysis.research_id} · Workflow: {analysis.run_id}</p>
  </section>;
}
