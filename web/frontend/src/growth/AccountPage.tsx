import { useState } from 'react';
import type { AccountPayload, CreatorType, GrowthState, ProfileFields } from './api';
import { emptyProfile } from './api';
import DiagnosisCards from './DiagnosisCards';

const baseFields: [keyof ProfileFields, string, string][] = [
  ['occupation', '职业 / 当前身份', '你目前正在做什么？'], ['experience', '相关经历', '只填写真实经历；没有也可以留空'],
  ['skills', '技能与专长', '你能具体帮助别人解决什么问题？'], ['interests', '兴趣方向', '你愿意长期探索什么？'],
  ['creator_goal', '创作目标', '你希望通过内容实现什么？这是目标，不是既有成绩'], ['target_audience', '目标用户', '你希望帮助谁？不确定可以留空'],
  ['content_assets', '可用内容素材', '已有作品、笔记、案例或可分享的日常素材'],
];
const existingFields: [keyof ProfileFields, string, string][] = [
  ['bio', '账号简介', '当前公开简介'], ['current_positioning', '当前定位', '你现在主要分享什么？'],
  ['operation_duration', '运营时长', '如实填写'], ['current_problem', '当前问题 / 创作约束', '例如选题困难、不露脸、不分享个人经历'],
];

export default function AccountPage({ state, newMode, busy, onSave, onGenerate, onConfirm }: {
  state: GrowthState; newMode: boolean; busy: boolean;
  onSave: (data: AccountPayload) => void; onGenerate: () => void; onConfirm: (id: string) => void;
}) {
  const account = newMode ? null : state.account;
  const profile = newMode ? null : state.current_profile;
  const initial = { ...emptyProfile, ...(profile?.raw_input.fields || profile?.raw_input || {}) } as ProfileFields;
  const [name, setName] = useState(account?.name || '');
  const [type, setType] = useState<CreatorType>(account?.creator_type || 'new');
  const [fields, setFields] = useState<ProfileFields>(initial);
  const dirty = name !== (account?.name || '') || type !== (account?.creator_type || 'new') || JSON.stringify(fields) !== JSON.stringify(initial);
  return <>
    <div className="gc-page-heading"><span className="gc-eyebrow">01 / ACCOUNT CONTEXT</span><h1>Account<span className="gc-title-subtitle" lang="zh-CN">账号定位</span></h1><p>让增长，从了解你开始。记录真实背景与创作目标，形成一个可以不断验证的定位假设。</p></div>
    <div className="gc-account-layout">
      <form className="gc-card gc-profile-form" onSubmit={e => { e.preventDefault(); if (account && name.trim() !== account.name && !window.confirm('这只会修改当前账号名称，历史内容仍属于此账号，不会创建独立账号。如需另一个账号，请取消并点击「＋ 新建账号」。继续改名？')) return; onSave({ name: name.trim(), creator_type: type, profile: fields, expected_current_id: profile?.id || null }); }}>
        <p className="gc-notice">{account ? '正在编辑当前账号；保存会创建资料版本，不会创建另一个账号。独立运营账号请使用「＋ 新建账号」。' : '正在创建独立账号；不会继承其他账号的参考内容、选题或草稿。'} New Creator / Existing Creator 仅表示创作者类型。</p>
        <div className="gc-card-top"><h2>账号资料</h2><span className="gc-badge gc-green">FACT · 用户自述</span></div>
        <fieldset disabled={busy}><legend className="gc-sr-only">创作者资料</legend>
          <div className="gc-creator-types">
            <button type="button" aria-pressed={type === 'new'} onClick={() => setType('new')}><strong>New Creator</strong><span>新手创作者 · 从零探索方向</span></button>
            <button type="button" aria-pressed={type === 'existing'} onClick={() => setType('existing')}><strong>Existing Creator</strong><span>已有账号 · 重新梳理定位</span></button>
          </div>
          <label>账号名称 <span className="gc-required">*</span><input required maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="给你的创作账号起个名字" /></label>
          <div className="gc-form-grid">{[...baseFields, ...(type === 'existing' ? existingFields : [])].map(([key, title, placeholder]) => <label key={key}>{title}<textarea rows={3} maxLength={3000} value={fields[key]} placeholder={placeholder} onChange={e => setFields(p => ({ ...p, [key]: e.target.value }))} /></label>)}</div>
          <p className="gc-small">可留空。不填写不代表你不具备；目标不会被当作已经实现的事实。</p>
          <div className="gc-form-actions"><span className="gc-muted">{profile ? `当前 Profile V${profile.version} · ${dirty ? '有未保存修改' : '资料已保存'}` : '尚未保存至数据库'}</span><button className="gc-button-strong" type="submit" disabled={!name.trim() || busy}>{busy ? '处理中…' : account ? '保存当前账号的新版本' : '创建独立账号'}</button></div>
        </fieldset>
      </form>
      <aside className="gc-card gc-guide"><span className="gc-eyebrow">EVIDENCE FIRST</span><h2>好的定位，<br />不是一个标签。</h2><p>它是你的真实经历、可提供的价值与目标用户需求之间，一个值得验证的交集。</p>
        <div className="gc-guide-step"><span>01</span><div><strong>写下真实的自己</strong><p>不必包装成专家，未知可以留空。</p></div></div>
        <div className="gc-guide-step"><span>02</span><div><strong>让 AI 提出假设</strong><p>建议、缺失和风险会分开展示。</p></div></div>
        <div className="gc-guide-step"><span>03</span><div><strong>由你决定方向</strong><p>确认是假设的起点，不是增长证明。</p></div></div>
        <button disabled={busy || !profile || dirty} onClick={onGenerate}>{busy ? '诊断处理中…' : '生成账号诊断'}</button>
        {dirty && profile && <p className="gc-small">请先保存修改，再基于新版本生成诊断。</p>}
        {!state.model_configured && <p className="gc-notice">真实模型尚未配置。资料仍可保存；诊断调用将明确报错，不会生成示例结果。</p>}
        <p className="gc-small">生成诊断会把当前账号资料发送给你配置的模型服务。</p>
      </aside>
    </div>
    {!newMode && <DiagnosisCards state={state} busy={busy} confirm={onConfirm} />}
  </>;
}
