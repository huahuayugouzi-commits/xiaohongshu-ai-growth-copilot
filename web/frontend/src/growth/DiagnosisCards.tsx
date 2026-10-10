import { useState } from 'react';
import type { Diagnosis, GrowthState } from './api';

function Items({ values, empty = '暂无；不代表不存在。' }: { values: string[]; empty?: string }) {
  return values.length ? <ul className="gc-list">{values.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="gc-muted">{empty}</p>;
}

export default function DiagnosisCards({ state, busy, confirm }: { state: GrowthState; busy: boolean; confirm: (id: string) => void }) {
  const [selected, setSelected] = useState('');
  const diagnosis: Diagnosis | undefined = state.diagnoses.find(d => d.id === selected) || state.current_diagnosis || state.diagnoses[0];
  if (!diagnosis) return <section className="gc-card gc-empty"><span className="gc-eyebrow">AI HYPOTHESIS</span><h2>先了解你，再提出定位假设</h2><p>保存账号资料后生成诊断。没有模型结果时，这里不会展示示例策略。</p></section>;
  const result = diagnosis.result;
  const current = state.current_diagnosis?.id === diagnosis.id;
  const profile = state.profiles.find(p => p.id === diagnosis.profile_version_id);
  return <section className="gc-diagnosis" aria-label="结构化诊断结果">
    <div className="gc-section-heading"><div><span className="gc-eyebrow">YOUR POSITIONING, NOT A PROMISE</span><h2>账号诊断</h2></div>
      <label className="gc-inline-label">版本记录<select aria-label="诊断版本" value={diagnosis.id} onChange={e => setSelected(e.target.value)}>
        {state.diagnoses.map((d, index) => <option key={d.id} value={d.id}>Profile V{state.profiles.find(p => p.id === d.profile_version_id)?.version ?? '?'} · 诊断 {state.diagnoses.length - index} · {d.status === 'confirmed' ? '已确认' : '待确认'}</option>)}
      </select></label>
    </div>
    {!current && <div className="gc-notice">正在查看历史诊断，不能作为当前 Profile 的新策略确认。</div>}
    <article className="gc-card gc-hypothesis">
      <div className="gc-card-top"><span className="gc-badge gc-orange">AI HYPOTHESIS · 定位假设</span><span className="gc-badge">Confidence · {result.confidence[0].toUpperCase() + result.confidence.slice(1)}</span></div>
      <h2>{result.positioning_hypothesis.positioning}</h2>
      <div className="gc-grid-3">
        <div><h3>目标用户</h3><p>{result.positioning_hypothesis.target_audience}</p></div>
        <div><h3>核心价值</h3><p>{result.positioning_hypothesis.core_value}</p></div>
        <div><h3>差异化</h3><p>{result.positioning_hypothesis.differentiation}</p></div>
      </div>
      <div className="gc-card-footer"><span>基于 Profile V{profile?.version ?? '?'} · 需要内容实验验证，不承诺涨粉</span>
        {current && diagnosis.status === 'pending' && <button disabled={busy} onClick={() => confirm(diagnosis.id)}>确认定位</button>}
        {diagnosis.status === 'confirmed' && <span className="gc-badge gc-green">已确认假设 · 非效果验证</span>}
      </div>
    </article>
    <div className="gc-grid-2">
      <article className="gc-card"><span className="gc-eyebrow">AI HYPOTHESIS</span><h3>内容支柱</h3>{result.content_pillars.length ? result.content_pillars.map((p, i) => <div className="gc-pillar" key={i}><strong>{p.name}</strong><p>{p.reason}</p></div>) : <p className="gc-muted">信息不足，暂不确定内容支柱。</p>}</article>
      <article className="gc-card"><span className="gc-badge gc-green">FACT · 用户自述引用</span><h3>可用优势 / 素材</h3><Items values={result.strengths} /><p className="gc-small">仅引用你填写的资料，未经外部核验。</p></article>
      <article className="gc-card"><span className="gc-eyebrow">AI HYPOTHESIS</span><h3>风险与约束</h3><Items values={result.risks} /><h3>Assumptions · 待验证推测</h3><Items values={result.assumptions} /></article>
      <article className="gc-card gc-missing"><span className="gc-badge gc-orange">MISSING INFORMATION</span><h3>需要补充的信息</h3><Items values={result.missing_information} empty="本次模型未列出补充项，不代表资料完整。" /></article>
    </div>
  </section>;
}
