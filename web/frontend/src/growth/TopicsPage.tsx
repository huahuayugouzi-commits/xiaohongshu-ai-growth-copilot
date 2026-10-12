import { useEffect, useState } from 'react';
import { request } from './api';
import type { Run } from './api';
interface Source { id: string; title: string; source_url: string | null; likes: number | null; collects: number | null; comments: number | null; confirmed_for_topic: boolean; analysis: { status: string } | null }
interface Topic { id: string; recommendation_id: string; rank: number; content: { title: string; target_audience: string; angle: string; hook: string; why_now: string; priority_reason: string; profile_basis: { field: string; quote: string }[]; evidence: { research_id: string; field: string; quote: string }[]; assumptions: string[]; risks: string[] } }
interface Batch { id: string; profile_version_id: string; diagnosis_id: string; created_at: string; not_recommended: string[] }
interface State { recommendations: Batch[]; topics: Topic[]; research: Source[]; runs: Run[] }
interface Evidence { topic_id: string; account_id: string; diagnosis_id: string; profile: { version: number }; research_snapshots: Source[] }

export default function TopicsPage({ accountId, profileId, diagnosisId, confirmed }: { accountId: string | null; profileId?: string; diagnosisId?: string; confirmed: boolean }) {
  const [data, setData] = useState<State | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [batchId, setBatchId] = useState('');
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const path = `/accounts/${accountId}/topics`;
  useEffect(() => {
    if (!accountId) return;
    let active = true;
    request<State>(path).then(value => { if (active) { setData(value); setSelected(value.research.filter(r => r.confirmed_for_topic && r.analysis?.status === 'succeeded').slice(0, 5).map(r => r.id)); } })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : '读取失败'); });
    return () => { active = false; };
  }, [accountId, path]);
  if (!accountId) return <section className="gc-card"><h1>TOP 3 Topics</h1><p>请先建立账号。</p><a href="#/account">前往 Account</a></section>;
  const refresh = async () => { setData(await request<State>(path)); };
  const generate = async (retryOf?: string) => {
    setBusy(true); setError(''); setEvidence(null);
    try { const value = await request<State>(`${path}/recommendations`, 'POST', { research_ids: selected, retry_of: retryOf || null }); setData(value); setBatchId(value.recommendations[0]?.id || ''); }
    catch (e) { setError(e instanceof Error ? e.message : '生成失败'); await refresh().catch(() => undefined); }
    finally { setBusy(false); }
  };
  const showEvidence = async (topic: Topic) => {
    setBusy(true); setError(''); setEvidence(null);
    try { setEvidence(await request<Evidence>(`${path}/${topic.id}/evidence`)); }
    catch (e) { setError(e instanceof Error ? e.message : '证据读取失败'); }
    finally { setBusy(false); }
  };
  const batch = data?.recommendations.find(r => r.id === batchId) || data?.recommendations[0];
  const topics = data?.topics.filter(t => t.recommendation_id === batch?.id).sort((a, b) => a.rank - b.rank) || [];
  const eligible = data?.research.filter(r => r.confirmed_for_topic && r.analysis?.status === 'succeeded') || [];
  const running = data?.runs.some(r => r.status === 'running');
  const ready = confirmed && selected.length >= 3 && selected.length <= 5 && !running;
  return <>
    <div className="gc-page-heading"><h1>TOP 3 Topics</h1><p>为什么这个账号现在适合做？基于定位与所选证据提出待验证选题，不保证流量或增长。</p></div>
    {error && <div className="gc-error" role="alert">{error}</div>}
    {!data && !error && <p role="status">正在读取选题…</p>}
    {!confirmed && <div className="gc-notice">请先确认当前 Profile 的最新诊断。<a href="#/account">前往 Account</a></div>}
    <section className="gc-card"><h2>选择 3–5 篇已分析、已确认的参考内容</h2>
      {eligible.length < 3 && <p>当前仅 {eligible.length} 篇可用。请在 <a href="#/research">Research</a> 完成分析并确认至少 3 篇。</p>}
      {eligible.map(r => <label key={r.id} style={{ display: 'block' }}><input type="checkbox" checked={selected.includes(r.id)} disabled={busy || !!running || (!selected.includes(r.id) && selected.length >= 5)} onChange={e => setSelected(v => e.target.checked ? [...v, r.id] : v.filter(id => id !== r.id))} /> {r.title}</label>)}
      <p>已选 {selected.length} 篇；生成会将 Profile、诊断和所选参考内容发送至配置的模型。</p>
      <button disabled={!ready || busy} onClick={() => { void generate(); }}>{busy ? '处理中…' : '生成 TOP 3 选题'}</button>
      <button disabled={busy} onClick={() => { void refresh().catch(() => setError('刷新失败')); }}>刷新状态</button>
    </section>
    {data?.runs.slice(0, 3).map(run => <section className="gc-card" key={run.id}>
      <p>选题任务：{run.status} · 重试 {run.retry_count} · tokens {run.tokens ?? '未知'} · cost {run.cost ?? '未知'}</p>{run.error && <p role="alert">{run.error}</p>}
      {run.status === 'failed' && <button disabled={!ready || busy} onClick={() => { void generate(run.id); }}>重新尝试</button>}
      {run.status === 'running' && <button disabled={busy} onClick={() => { if (window.confirm('标记失败并允许重试？原请求返回的结果将被拒绝。')) { setBusy(true); void request<State>(`${path}/runs/${run.id}/interrupt`, 'POST').then(setData).catch(() => setError('中断失败')).finally(() => setBusy(false)); } }}>标记已中断</button>}
    </section>)}
    {batch && <><label>推荐批次<select aria-label="推荐批次" value={batch.id} onChange={e => { setBatchId(e.target.value); setEvidence(null); }}>{data!.recommendations.map(r => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString()} · {r.id.slice(0, 8)}</option>)}</select></label>
      {(batch.profile_version_id !== profileId || batch.diagnosis_id !== diagnosisId) && <p className="gc-notice">历史推荐：对应旧 Profile / Diagnosis，不代表当前策略。</p>}
      {topics.map(topic => <article className="gc-card" key={topic.id}>
        <span className="gc-badge gc-orange">TOP {topic.rank} · AI HYPOTHESIS</span><h2>{topic.content.title}</h2>
        <h3>为什么现在适合</h3><p>{topic.content.why_now}</p><p>优先级理由：{topic.content.priority_reason}</p>
        <p>目标用户：{topic.content.target_audience}</p><p>内容角度：{topic.content.angle}</p><p>Hook：{topic.content.hook}</p>
        <h3>账号依据 · 用户自述引用</h3>{topic.content.profile_basis.map((v, i) => <blockquote key={i}>{v.field}：{v.quote}</blockquote>)}
        <h3>待验证假设</h3><ul>{topic.content.assumptions.map((v, i) => <li key={i}>{v}</li>)}</ul><h3>风险</h3><ul>{topic.content.risks.map((v, i) => <li key={i}>{v}</li>)}</ul>
        <button disabled={busy} onClick={() => { void showEvidence(topic); }}>查看来源证据</button>
        {evidence?.topic_id === topic.id && <section aria-label="选题证据" className="gc-notice"><button onClick={() => setEvidence(null)}>关闭证据</button>
          <p>Profile V{evidence.profile.version} · Diagnosis {evidence.diagnosis_id}</p><p>以下为推荐时的不可变快照。</p>
          {topic.content.evidence.map((ref, i) => { const source = evidence.research_snapshots.find(r => r.id === ref.research_id); return <div key={i}><h4>{source?.title || ref.research_id}</h4><blockquote>{ref.field}：{ref.quote}</blockquote><p>来源：{source?.source_url || '未提供 URL'}</p><p>点赞 {source?.likes ?? '未知'} · 收藏 {source?.collects ?? '未知'} · 评论 {source?.comments ?? '未知'}</p></div>; })}
          <p>Account {evidence.account_id} · Topic {evidence.topic_id}</p></section>}
      </article>)}
      {!!batch.not_recommended.length && <section className="gc-card"><h3>当前不建议优先做</h3><ul>{batch.not_recommended.map((v, i) => <li key={i}>{v}</li>)}</ul></section>}
    </>}
    {data && !batch && <p>尚无推荐，不会展示示例选题。</p>}
  </>;
}
