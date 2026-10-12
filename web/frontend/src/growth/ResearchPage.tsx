import { useEffect, useState } from 'react';
import { request } from './api';

interface ResearchItem {
  id: string; account_id: string; source_url: string | null; title: string; body: string;
  likes: number | null; collects: number | null; comments: number | null;
  comment_samples: string[]; confirmed_for_topic: boolean;
}
const empty = { source_url: '', title: '', body: '', likes: '', collects: '', comments: '', comment_samples: '' };
function count(value: string) {
  if (!value.trim()) return null;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 0) throw new Error('互动数据必须为非负整数；未知请留空。');
  return number;
}

export default function ResearchPage({ accountId }: { accountId: string | null }) {
  const [form, setForm] = useState(empty);
  const [items, setItems] = useState<ResearchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const path = `/accounts/${accountId}/research`;
  useEffect(() => {
    if (!accountId) { setLoading(false); return; }
    let active = true;
    request<ResearchItem[]>(path).then(data => { if (active) setItems(data); })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : '读取失败'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accountId, path]);
  if (!accountId) return <section className="gc-card gc-empty"><h1>Research</h1><p>请先创建或选择账号。</p><a href="#/account">前往 Account</a></section>;
  const save = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const item = await request<ResearchItem>(path, 'POST', { ...form,
        source_url: form.source_url.trim() || null, title: form.title.trim(), body: form.body.trim(),
        likes: count(form.likes), collects: count(form.collects), comments: count(form.comments),
        comment_samples: form.comment_samples.split('\n').map(v => v.trim()).filter(Boolean) });
      setItems(previous => [...previous, item]); setForm(empty); setNotice('参考内容已保存到当前账号。');
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
    finally { setBusy(false); }
  };
  const confirm = async (item: ResearchItem) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const updated = await request<ResearchItem>(`${path}/${item.id}/confirmation`, 'PATCH', { confirmed_for_topic: !item.confirmed_for_topic });
      setItems(previous => previous.map(v => v.id === updated.id ? updated : v));
      setNotice('选题参考标记已保存。');
    } catch (e) { setError(e instanceof Error ? e.message : '标记失败'); }
    finally { setBusy(false); }
  };
  return <>
    <div className="gc-page-heading"><span className="gc-eyebrow">RESEARCH · MANUAL INPUT</span><h1>保存值得研究的参考内容</h1><p>仅保存你手动提供的资料，不抓取、不执行 AI 分析。未知互动数据请留空，已知为零请填 0。</p></div>
    {error && <div className="gc-error" role="alert">{error}<button onClick={() => window.location.reload()}>刷新重试</button></div>}
    {notice && <div className="gc-success" role="status">{notice}</div>}
    <form className="gc-card gc-profile-form" onSubmit={e => { e.preventDefault(); void save(); }}>
      <fieldset disabled={busy || loading}><legend>手动录入一篇参考内容</legend>
        <label>来源 URL<input type="url" maxLength={2048} value={form.source_url} onChange={e => setForm({ ...form, source_url: e.target.value })} /></label>
        <label>标题<input required maxLength={300} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></label>
        <label>正文<textarea required rows={7} maxLength={50000} value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} /></label>
        <div className="gc-form-grid">{(['likes', 'collects', 'comments'] as const).map((key, i) => <label key={key}>{['点赞', '收藏', '评论数'][i]}<input type="number" min={0} step={1} placeholder="未知（留空）" value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}</div>
        <label>评论样本（每行一条，最多 100 条）<textarea rows={4} value={form.comment_samples} onChange={e => setForm({ ...form, comment_samples: e.target.value })} /></label>
        <button type="submit" disabled={busy || !form.title.trim() || !form.body.trim()}>{busy ? '保存中…' : '保存参考内容'}</button>
      </fieldset>
    </form>
    <section aria-label="已保存参考内容"><h2>已保存参考内容</h2>
      {loading ? <p role="status">正在读取…</p> : !items.length && <p>尚无参考内容。先手动保存一篇。</p>}
      {items.map(item => <article className="gc-card" key={item.id}>
        <div className="gc-card-top"><h3>{item.title}</h3><span className="gc-badge">{item.confirmed_for_topic ? '已确认用于选题' : '未确认用于选题'}</span></div>
        {item.source_url && <p>来源：{item.source_url}</p>}
        <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.body}</p>
        <p>点赞：{item.likes ?? '未知'} · 收藏：{item.collects ?? '未知'} · 评论：{item.comments ?? '未知'}</p>
        <h4>评论样本</h4>{item.comment_samples.length ? <ul>{item.comment_samples.map((v, i) => <li key={i}>{v}</li>)}</ul> : <p>未提供评论样本</p>}
        <button disabled={busy} onClick={() => { void confirm(item); }}>{item.confirmed_for_topic ? '取消用于选题' : '确认用于选题'}</button>
      </article>)}
    </section>
  </>;
}
