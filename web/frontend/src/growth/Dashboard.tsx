import type { GrowthState } from './api';

export default function Dashboard({ state, goAccount }: { state: GrowthState; goAccount: () => void }) {
  const diagnosis = state.current_diagnosis;
  const confirmed = diagnosis?.status === 'confirmed';
  const stages = [
    ['Account', Boolean(state.current_profile), '真实背景'], ['Diagnosis', confirmed, '定位假设'],
    ['Research', state.counts.research > 0, '研究依据'], ['Topics', state.counts.topics > 0, '有据选题'], ['Draft', state.counts.drafts > 0, '内容草稿'],
  ] as const;
  return <>
    <div className="gc-page-heading"><span className="gc-eyebrow">YOUR GROWTH WORKSPACE</span><h1>每一步创作，都更有依据。</h1><p>从账号定位开始，把想法变成值得验证的内容方向。</p></div>
    <section className="gc-card gc-dashboard-hero"><div><span className="gc-eyebrow">NEXT BEST STEP</span><h2>{state.next_step}</h2><p>{confirmed ? '你的定位假设已确认。研究、选题与内容工作台将在后续阶段开放。' : '先建立真实的账号上下文，再让 AI 提出定位建议。你始终拥有最终决定权。'}</p>
      <button onClick={goAccount}>{confirmed ? '查看账号定位' : state.account ? '继续完善账号 →' : '开始账号建档 →'}</button></div>
      <div className="gc-orbit" aria-hidden="true"><div className="gc-orbit-core">G<span>GROW WITH EVIDENCE</span></div><span className="gc-orbit-tag gc-orbit-tag-a">Account Context</span><span className="gc-orbit-tag gc-orbit-tag-b">Human Confirmation</span></div>
    </section>
    <div className="gc-grid-3 gc-stats">
      <article className="gc-card"><span className="gc-eyebrow">CURRENT ACCOUNT</span><h2>{state.account?.name || '尚未建档'}</h2><p>{state.account ? state.account.creator_type === 'new' ? 'New Creator · 新手创作者' : 'Existing Creator · 已有账号' : '你的增长旅程从这里开始'}</p></article>
      <article className="gc-card"><span className="gc-eyebrow">PROFILE VERSION</span><h2>{state.current_profile ? `V${state.current_profile.version}` : '—'}</h2><p>每次实质修改保留一个新版本</p></article>
      <article className="gc-card"><span className="gc-eyebrow">DIAGNOSIS STATUS</span><h2>{confirmed ? '已确认假设' : diagnosis ? '等待你确认' : '尚未生成'}</h2><p>{confirmed ? '已确认不代表增长效果已验证' : 'AI 结果不会自动成为账号策略'}</p></article>
    </div>
    <section className="gc-card"><div className="gc-card-top"><h2>你的创作路径</h2><span className="gc-muted">从定位到内容 · 一步一步来</span></div><ol className="gc-workflow">{stages.map(([name, done, label], i) => <li key={name}><span className={`gc-step-dot ${done ? 'is-done' : ''}`}>{done ? '✓' : '○'}</span><strong>{name}</strong><small>{label}{i > 1 ? ' · Coming Soon' : ''}</small></li>)}</ol></section>
    <section className="gc-card gc-hypothesis"><span className="gc-badge gc-orange">CURRENT POSITIONING HYPOTHESIS</span><h2>{diagnosis?.result.positioning_hypothesis.positioning || '尚未形成定位假设'}</h2><p>{diagnosis ? diagnosis.result.positioning_hypothesis.core_value : '我们不会替你编造背景。保存资料并运行诊断后，这里将显示真实的模型结果。'}</p></section>
  </>;
}
