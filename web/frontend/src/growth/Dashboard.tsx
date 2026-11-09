import { useEffect, useState } from 'react';
import { request } from './api';
import type { GrowthState } from './api';

interface Topic { id: string; recommendation_id: string; rank: number; content: { title: string; angle: string; evidence: { research_id: string; quote: string }[] } }
interface Source { id: string; title: string; analysis: { status: string } | null }
interface Overview { recommendations: { id: string; profile_version_id: string; diagnosis_id: string }[]; topics: Topic[]; research: Source[] }

export default function Dashboard({ state, goAccount }: { state: GrowthState; goAccount: () => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');
  const accountId = state.account?.id;
  useEffect(() => {
    let active = true;
    setData(null); setError('');
    if (accountId) request<Overview>(`/accounts/${accountId}/topics`).then(value => { if (active) setData(value); })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : '读取失败'); });
    return () => { active = false; };
  }, [accountId]);
  const diagnosis = state.current_diagnosis;
  const confirmed = diagnosis?.status === 'confirmed' && diagnosis.profile_version_id === state.current_profile?.id;
  const batch = data?.recommendations.find(r => r.profile_version_id === state.current_profile?.id && r.diagnosis_id === diagnosis?.id);
  const topics = confirmed ? data?.topics.filter(t => t.recommendation_id === batch?.id).sort((a, b) => a.rank - b.rank) || [] : [];
  const featured = topics[0];
  const sources = data?.research || [];
  const evidence = featured?.content.evidence || [];
  return <div className="gc-editorial-home">
    <section className="gc-creation-sheet">
      <header><span className="gc-editorial-kicker">WORKSPACE</span><h1>今日创作</h1><span className="gc-editorial-rule" /></header>
      <div className="gc-featured-topic"><span className="gc-badge gc-green">{featured ? '选题假设' : '定位假设'}</span><h2>{featured?.content.title || diagnosis?.result.positioning_hypothesis.positioning || '从你的真实背景，开始创作'}</h2><p>{featured?.content.angle || diagnosis?.result.positioning_hypothesis.core_value || '先建立账号资料，明确内容方向，再让每一次创作都有依据。'}</p></div>
      <div className="gc-home-evidence"><span>来源证据</span>
        {error ? <p role="alert" className="gc-error-text">{error}</p> : accountId && !data ? <p role="status">正在读取参考内容…</p> : evidence.length ? evidence.slice(0, 3).map((e, i) => <a href="#/topics" key={`${e.research_id}:${i}`}><span aria-hidden="true">↗</span><span>{sources.find(s => s.id === e.research_id)?.title || e.quote}</span></a>) : <p>尚无当前选题的来源证据。导入参考内容、完成分析后，在智能选题中生成有据可查的建议。</p>}
      </div>
      <div className="gc-home-action">{!confirmed ? <button className="gc-button-strong" onClick={goAccount}>{state.account ? '完善账号定位' : '开始账号建档'} <span aria-hidden="true">→</span></button> : <a className="gc-primary-link" href={featured ? '#/studio' : sources.length ? '#/topics' : '#/research'}>{featured ? '开始创作' : sources.length ? '生成智能选题' : '添加参考内容'} <span aria-hidden="true">→</span></a>}</div>
      <footer className="gc-sheet-footer"><div className="gc-alternative-topics">{topics.slice(1, 3).map((topic, i) => <a href="#/topics" key={topic.id}><span>✦</span><small>备选选题 {i + 1}</small><span>{topic.content.title}</span><span>›</span></a>)}{topics.length < 2 && <p>备选选题将在完成研究与推荐后显示。</p>}</div><a className="gc-continue-draft" href="#/studio"><strong>▤ &nbsp;继续编辑</strong><small>{state.counts.drafts ? `${state.counts.drafts} 篇已保存草稿` : '尚无草稿 · 从选题开始'}</small></a></footer>
    </section>
    <aside className="gc-research-rail"><div className="gc-silk" aria-hidden="true" /><h2>研究来源</h2><span className="gc-editorial-rule" /><p>来自当前账号已保存的参考内容</p>
      {sources.slice(-3).reverse().map((source, i) => <article className="gc-source-preview" key={source.id}><div className={`gc-source-cover gc-source-cover-${i}`} aria-hidden="true"><span>REFERENCE</span><b>0{i + 1}</b></div><div><h3>{source.title}</h3><p>{source.analysis?.status === 'succeeded' ? '已完成分析 · 结论仍需实际验证' : '已保存的参考内容'}</p><a href="#/research">查看来源 ↗</a></div></article>)}
      {!sources.length && <div className="gc-source-empty"><p>{error ? '参考内容暂时无法读取。' : accountId && !data ? '正在加载研究来源…' : '还没有参考内容。添加第一篇，开始积累你的创作依据。'}</p><a href={accountId ? '#/research' : '#/account'}>{accountId ? '前往内容研究 ↗' : '先创建账号 ↗'}</a></div>}
    </aside>
  </div>;
}
