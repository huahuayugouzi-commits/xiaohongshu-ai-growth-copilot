import { useEffect, useState } from 'react';
import { request } from './api';
import type { Run } from './api';
interface Content { title: string; hook: string; body: string; cta: string; tags: string[]; cover_text: string; visual_suggestions: string[]; facts_to_verify: string[] }
interface Topic { id: string; rank: number; content: { title: string } }
interface Draft { id: string; topic_id: string; latest_version_id: string }
interface Version { id: string; draft_id: string; version: number; content: Content; source_evidence: { profile_version_id: string; diagnosis_id: string; topic_id: string; research_snapshots: { id: string; title: string; body: string; source_url: string | null; likes: number | null; collects: number | null; comments: number | null }[] } }
interface State { topics: Topic[]; drafts: Draft[]; versions: Version[]; runs: Run[]; created_draft_id?: string }
export default function StudioPage({ accountId }: { accountId: string | null }) {
  const [data, setData] = useState<State | null>(null);
  const [topicId, setTopicId] = useState('');
  const [draftId, setDraftId] = useState('');
  const [versionId, setVersionId] = useState('');
  const [content, setContent] = useState<Content | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const path = `/accounts/${accountId}/studio`;
  useEffect(() => {
    if (!accountId) return;
    let active = true;
    request<State>(path).then(value => { if (active) { setData(value); setTopicId(value.topics[0]?.id || ''); } }).catch(e => { if (active) setError(e instanceof Error ? e.message : '读取失败'); });
    return () => { active = false; };
  }, [accountId, path]);
  const drafts = data?.drafts.filter(d => d.topic_id === topicId) || [];
  const draft = drafts.find(d => d.id === draftId) || drafts[0];
  const versions = data?.versions.filter(v => v.draft_id === draft?.id).sort((a, b) => b.version - a.version) || [];
  const version = versions.find(v => v.id === versionId) || versions[0];
  useEffect(() => { setContent(version?.content || null); }, [version]);
  if (!accountId) return <section className="gc-card"><h1>Studio</h1><a href="#/account">请先建立账号</a></section>;
  const running = data?.runs.some(r => r.status === 'running');
  const historical = !!version && version.id !== draft?.latest_version_id;
  const refresh = async () => { setData(await request<State>(path)); };
  const generate = async (retryOf?: string) => {
    setBusy(true); setError(''); setNotice('');
    try { const value = await request<State>(`${path}/drafts`, 'POST', { topic_id: topicId, retry_of: retryOf || null }); setData(value); setDraftId(value.created_draft_id || ''); setVersionId(''); setNotice('AI 草稿已保存为 V1，请核实后编辑。'); }
    catch (e) { setError(e instanceof Error ? e.message : '生成失败'); await refresh().catch(() => undefined); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!draft || !content) return;
    setBusy(true); setError(''); setNotice('');
    try { setData(await request<State>(`${path}/drafts/${draft.id}/versions`, 'POST', { content, expected_latest_id: draft.latest_version_id })); setVersionId(''); setNotice('已保存新版本，旧版本保留。'); }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
    finally { setBusy(false); }
  };
  const edit = (field: keyof Content, value: string) => setContent(v => v ? { ...v, [field]: ['tags', 'visual_suggestions', 'facts_to_verify'].includes(field) ? value.split('\n') : value } : v);
  return <>
    <div className="gc-page-heading"><h1>Studio Draft</h1><p>选题 → AI 草稿 → 人工核实与编辑 → 新版本。不自动发布。</p></div>
    {error && <div className="gc-error" role="alert">{error}</div>}{notice && <div className="gc-success" role="status">{notice}</div>}
    {!data && !error && <p role="status">正在读取草稿…</p>}
    <section className="gc-card"><label>选择 Topic<select aria-label="选择 Topic" disabled={busy || !!running} value={topicId} onChange={e => { setTopicId(e.target.value); setDraftId(''); setVersionId(''); setNotice(''); }}><option value="">请选择</option>{data?.topics.map(t => <option key={t.id} value={t.id}>TOP {t.rank} · {t.content.title} · {t.id.slice(0, 6)}</option>)}</select></label>
      {!data?.topics.length && <p>暂无选题，请先完成 <a href="#/topics">Topics</a>。</p>}
      <p>仅为当前已确认定位的选题生成草稿；模型会收到该选题及其来源快照。再次生成会新建一份草稿，不覆盖旧稿。</p>
      <button disabled={!topicId || busy || !!running} onClick={() => { void generate(); }}>{busy ? '处理中…' : '生成 AI 草稿'}</button>
      <button disabled={busy || !!content} onClick={() => { void refresh().catch(() => setError('读取失败')); }}>刷新状态</button>
    </section>
    {data?.runs.slice(0, 3).map(run => <section className="gc-card" key={run.id}><p>草稿任务：{run.status} · 重试 {run.retry_count} · tokens {run.tokens ?? '未知'} · cost {run.cost ?? '未知'}</p>{run.error && <p role="alert">{run.error}</p>}
      {run.status === 'failed' && <button disabled={!topicId || busy || !!running} onClick={() => { void generate(run.id); }}>用当前选题重试</button>}
      {run.status === 'running' && <button disabled={busy} onClick={() => { if (window.confirm('标记失败？晚到结果将被拒绝保存。')) { setBusy(true); void request<State>(`${path}/runs/${run.id}/interrupt`, 'POST').then(setData).catch(() => setError('中断失败')).finally(() => setBusy(false)); } }}>标记已中断</button>}
    </section>)}
    {draft && <section className="gc-card"><label>草稿<select disabled={busy} value={draft.id} onChange={e => { setDraftId(e.target.value); setVersionId(''); }}>{drafts.map(d => <option key={d.id} value={d.id}>{d.id.slice(0, 8)}</option>)}</select></label><label>版本<select disabled={busy} value={version?.id || ''} onChange={e => setVersionId(e.target.value)}>{versions.map(v => <option key={v.id} value={v.id}>V{v.version}{v.id === draft.latest_version_id ? ' · 最新' : ' · 历史只读'}</option>)}</select></label></section>}
    {version && content && <section className="gc-card"><span className="gc-badge gc-orange">AI 草稿 / 人工编辑 · 未验证，不是事实认证</span><p>修改不会自动保存。切换选题、版本或刷新前，请先保存。人工修改不会自动通过事实校验。</p>
      {([['title', '标题'], ['hook', 'Hook'], ['body', '正文'], ['cta', '结尾引导'], ['tags', '标签（每行一个）'], ['cover_text', '封面文字'], ['visual_suggestions', '图片建议（每行一个）'], ['facts_to_verify', '发布前待核实（每行一个）']] as [keyof Content, string][]).map(([field, label]) => <label key={field} style={{ display: 'block' }}>{label}<textarea style={{ width: '100%' }} rows={field === 'body' ? 12 : 2} disabled={busy || historical} value={Array.isArray(content[field]) ? (content[field] as string[]).join('\n') : content[field]} onChange={e => edit(field, e.target.value)} /></label>)}
      <button disabled={busy || historical} onClick={() => { void save(); }}>保存为新版本</button>
      <details><summary>来源证据 · 生成时快照</summary><p>Topic {version.source_evidence.topic_id}</p><p>Profile {version.source_evidence.profile_version_id} · Diagnosis {version.source_evidence.diagnosis_id}</p>{version.source_evidence.research_snapshots.map(s => <article key={s.id}><h3>{s.title}</h3><p>{s.source_url || '未提供 URL'}</p><p>点赞 {s.likes ?? '未知'} · 收藏 {s.collects ?? '未知'} · 评论 {s.comments ?? '未知'}</p><p style={{ whiteSpace: 'pre-wrap' }}>{s.body}</p></article>)}</details>
    </section>}
    {data && topicId && !draft && <p>该选题暂无草稿，不展示示例内容。</p>}
  </>;
}
