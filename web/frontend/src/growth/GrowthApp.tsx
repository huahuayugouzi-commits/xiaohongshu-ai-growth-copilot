import { useCallback, useEffect, useRef, useState } from 'react';
import type { AccountPayload, GrowthState } from './api';
import { request } from './api';
import AccountPage from './AccountPage';
import Dashboard from './Dashboard';
import ResearchPage from './ResearchPage';
import TopicsPage from './TopicsPage';
import StudioPage from './StudioPage';
import './growth.css';

type Page = 'dashboard' | 'account' | 'research' | 'topics' | 'studio';
const pages: [Page, string, string][] = [['dashboard', 'Dashboard', '◈'], ['account', 'Account', '◎'], ['research', 'Research', '⌕'], ['topics', 'Topics', '◇'], ['studio', 'Studio', '▤']];
const pageSubtitles: Record<Page, string> = { dashboard: '工作台', account: '账号定位', research: '内容研究', topics: '智能选题', studio: '内容创作' };
function pageFromHash(): Page { const p = location.hash.replace('#/', ''); return pages.some(x => x[0] === p) ? p as Page : 'dashboard'; }
function savedAccount() { try { return localStorage.getItem('growth_account_id') || ''; } catch { return ''; } }

function NavigationIcon({ page }: { page: Page }) {
  const paths: Record<Page, string> = {
    dashboard: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
    account: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0M13 12a1 1 0 1 1-2 0 1 1 0 0 1 2 0',
    research: 'm2 7 10-5 10 5-10 5-10-5m0 5 10 5 10-5M2 17l10 5 10-5',
    topics: 'M9 18h6m-6 3h6M8 15a8 8 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3',
    studio: 'm4 16 12-12a2 2 0 0 1 4 4L8 20l-5 1 1-5m10-10 4 4M3 23h19',
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[page]} /></svg>;
}

export default function GrowthApp() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [accountId, setAccountId] = useState(savedAccount);
  const [state, setState] = useState<GrowthState | null>(null);
  const [newMode, setNewMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const accountEpoch = useRef(0);
  const go = (next: Page) => { location.hash = `/${next}`; setPage(next); };
  useEffect(() => { const change = () => setPage(pageFromHash()); window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change); }, []);
  const refresh = useCallback(async () => {
    const epoch = accountEpoch.current;
    const data = await request<GrowthState>(`/state${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ''}`);
    if (epoch === accountEpoch.current && (!accountId || data.account?.id === accountId)) setState(data);
    return data;
  }, [accountId]);
  useEffect(() => { let active = true; request<GrowthState>(`/state${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ''}`).then(data => { if (active) { setState(data); setError(''); } }).catch(e => { if (active) setError(e instanceof Error ? e.message : '无法读取账号。'); }); return () => { active = false; }; }, [accountId]);
  const selectAccount = (id: string) => { accountEpoch.current += 1; setAccountId(id); setNewMode(false); setState(null); setError(''); setNotice(''); try { localStorage.setItem('growth_account_id', id); } catch { /* preference only */ } };
  const mutate = async (operation: () => Promise<GrowthState>, success: string) => {
    const epoch = accountEpoch.current;
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await operation();
      if (epoch !== accountEpoch.current) return null;
      setState(previous => ({ ...data, model_configured: previous?.model_configured }));
      setNotice(success); return data;
    } catch (e) {
      if (epoch !== accountEpoch.current) return null;
      setError(e instanceof Error ? e.message : '操作失败，请重试。');
      await refresh().catch(() => undefined); return null;
    } finally { setBusy(false); }
  };
  const save = async (payload: AccountPayload) => {
    const currentId = !newMode ? state?.account?.id : null;
    const data = await mutate(() => request<GrowthState>(currentId ? `/accounts/${currentId}/profile` : '/accounts', currentId ? 'PUT' : 'POST', payload), '账号资料已保存至数据库。');
    if (data?.account) { accountEpoch.current += 1; setNewMode(false); setAccountId(data.account.id); try { localStorage.setItem('growth_account_id', data.account.id); } catch { /* preference only */ } }
  };
  const generate = async (retryOf?: string) => {
    if (newMode || !state?.account || !state.current_profile) return;
    await mutate(() => request<GrowthState>(`/accounts/${state.account!.id}/diagnoses`, 'POST', { profile_version_id: state.current_profile!.id, retry_of: retryOf || null }), '诊断已生成，等待你确认定位。');
  };
  const confirm = async (id: string) => { if (state?.account) await mutate(() => request<GrowthState>(`/accounts/${state.account!.id}/diagnoses/${id}/confirm`, 'POST'), '已确认定位假设。它仍需要实际内容实验验证。'); };
  const currentProjectionFailed = !newMode && state?.projections.some(p => p.profile_version_id === state.current_profile?.id && p.status === 'failed');
  return <div className={`gc-shell gc-editorial-shell${page === 'dashboard' ? ' gc-home-shell' : ''}`}>
    <aside className="gc-sidebar"><a className="gc-brand" href="#/dashboard"><span className="gc-logo">g<span>↗</span></span><span>Growth Copilot<small>小红书 AI 增长助手</small></span></a>
      <div className="gc-sidebar-account">{state && state.accounts.length > 0 && <select aria-label="当前账号" disabled={busy} value={state.account?.id || ''} onChange={e => selectAccount(e.target.value)}>{state.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select>}</div>
      <nav aria-label="主导航">{pages.map(([key, title]) => <a href={`#/${key}`} title={title} aria-current={page === key ? 'page' : undefined} className={page === key ? 'active' : ''} key={key}><span className="gc-nav-icon" aria-hidden="true"><NavigationIcon page={key} /></span><span className="gc-nav-text">{pageSubtitles[key]}</span></a>)}</nav>
      <div className="gc-sidebar-note"><span className="gc-eyebrow">GROWTH, WITH CONTEXT.</span><p>不是多生成一些内容，<br />而是知道为什么创作。</p></div><div className="gc-sidebar-footer"><span className="gc-status-dot" />Local workspace · Phase 3</div>
    </aside>
    <div className="gc-main"><header className="gc-header"><span>Workspace <span className="gc-separator">/</span> <strong>{pages.find(p => p[0] === page)?.[1]}</strong></span><div className="gc-header-actions">
      <span className="gc-badge">小红书 AI 增长助手</span></div></header>
      <main className="gc-content">
        {error && <div className="gc-error" role="alert"><strong>操作未完成</strong><p>{error}</p><button onClick={() => { void refresh().then(() => setError('')).catch(() => undefined); }}>刷新状态</button>{!state && <button onClick={() => selectAccount('')}>返回账号列表</button>}</div>}
        {notice && <div className="gc-success" role="status">{notice}</div>}
        {!state && !error && <div className="gc-card" role="status">正在读取本地数据…</div>}
        {state && (!accountId || state.account?.id === accountId) && <>
          {newMode && page !== 'account' && <section className="gc-card"><p>新账号尚未保存，请先完成建档。旧账号数据已保留。</p><button onClick={() => go('account')}>返回账号建档</button></section>}
          {currentProjectionFailed && <div className="gc-notice" role="alert">资料已保存，但 Persona 画像同步失败。<button disabled={busy} onClick={() => { void mutate(() => request<GrowthState>(`/accounts/${state.account!.id}/projection/retry`, 'POST'), '已重试同步，请查看状态。'); }}>重试同步</button></div>}
          {!newMode && page === 'dashboard' && <Dashboard key={state.account?.id || 'none'} state={state} goAccount={() => go('account')} />}
          {page === 'account' && <><div className="gc-page-tools"><button disabled={busy} onClick={() => { setNewMode(true); setNotice(''); }}>＋ 新建账号</button>{newMode && state.account && <button onClick={() => setNewMode(false)}>取消新建</button>}</div><AccountPage key={`${state.account?.id}:${newMode}`} state={state} newMode={newMode} busy={busy} onSave={data => { void save(data); }} onGenerate={() => { void generate(); }} onConfirm={id => { void confirm(id); }} /></>}
          {!newMode && <>
          {page === 'research' && <ResearchPage key={`${state.account?.id}:${state.current_diagnosis?.status}`} accountId={state.account?.id || null} diagnosisConfirmed={state.current_diagnosis?.status === 'confirmed' && state.current_diagnosis.profile_version_id === state.current_profile?.id} />}
          {page === 'topics' && <TopicsPage key={state.account?.id || 'none'} accountId={state.account?.id || null} profileId={state.current_profile?.id} diagnosisId={state.current_diagnosis?.id} confirmed={state.current_diagnosis?.status === 'confirmed' && state.current_diagnosis.profile_version_id === state.current_profile?.id} />}
          {page === 'studio' && <StudioPage key={state.account?.id || 'none'} accountId={state.account?.id || null} />}
          {['dashboard', 'account'].includes(page) && state.runs.filter(r => r.stage === 'diagnosis').length > 0 && <section className="gc-card gc-runs"><div className="gc-card-top"><h2>最近诊断任务</h2><button disabled={busy} onClick={() => { void refresh().catch(() => setError('刷新失败')); }}>刷新任务状态</button></div>{state.runs.filter(r => r.stage === 'diagnosis').slice(0, 5).map((run, index) => <div className="gc-run" key={run.id}><div><span className={`gc-badge ${run.status === 'succeeded' ? 'gc-green' : run.status === 'failed' ? 'gc-orange' : ''}`}>{run.status === 'succeeded' ? '已生成 · 非已确认' : run.status === 'failed' ? '失败' : '处理中 / 等待恢复'}</span><p>{new Date(run.started_at).toLocaleString()} · 重试 {run.retry_count} 次 · tokens {run.tokens ?? '未知'} · cost {run.cost ?? '未知'}</p>{run.error && <p className="gc-error-text">{run.error}</p>}</div>
            {run.status === 'failed' && index === 0 && <button disabled={busy} onClick={() => { void generate(run.id); }}>重试诊断</button>}
            {run.status === 'running' && <button disabled={busy} onClick={() => { if (window.confirm('将任务标记为失败？模型请求可能仍在服务端运行，其返回结果将被拒绝保存。')) void mutate(() => request<GrowthState>(`/accounts/${state.account!.id}/runs/${run.id}/interrupt`, 'POST'), '已标记为中断，可重新生成诊断。'); }}>标记为已中断</button>}
          </div>)}</section>}
          </>}
        </>}
        <footer className="gc-content-footer">Growth Copilot · 以证据为起点，以验证为下一步。</footer>
      </main>
    </div>
  </div>;
}
