# Growth Copilot

**小红书 AI 增长助手**

面向知识型、经验型早期创作者的内容决策工具，帮助你更有依据地决定：**下一篇发什么，为什么值得发？**

结合账号背景、定位与手动导入的参考内容，提供 3 个可追溯依据的候选选题，并将选定方向转化为可编辑、可保存历史版本的草稿。适合职业转型、职场技能、学习方法、效率工具与专业知识分享等方向。

Evidence-based content planning for early-stage creators: account positioning → research → TOP 3 topics → editable drafts. Recommendations are hypotheses for human review, not predictions of viral performance.

从真实账号背景出发，形成定位假设，由用户确认后再进入内容研究与创作。
Growth Copilot is built upon the open-source [Easel](https://github.com/ZJU-REAL/Easel) project.

## V0.1 DEMO READY

- Account：新手 / 已有账号建档，SQLite 持久化和 Profile 版本。
- Diagnosis：真实兼容模型调用、结构化结果、Fact Lock 检查、人工确认。
- Dashboard：读取数据库中的账号、定位、版本和流程状态。
- Research：手动输入参考内容、真实 AI 分析、结构化研究卡与原文引用。
- Topics：基于当前已确认定位和 1–3 篇已分析/确认参考内容，生成 TOP 3 推荐与证据。
- Studio：选择 Topic 生成草稿，人工编辑创建新版本，保留 V1/V2 与来源快照。

模型未配置时可保存资料；诊断显示配置错误，不使用模拟结果兜底。
AI 建议是待验证假设，不是效果承诺或已核实事实。

## 产品定位、用户与痛点

面向不知道如何定位的新手创作者，以及缺少选题、产出低效的已有创作者。
回答“我适合写什么、为什么适合、依据是什么、怎样写成可编辑草稿”。
V0.1 已完成核心 Demo 闭环，并提供管理员开通账号的私有试用部署入口；不开放注册，不承诺流量、涨粉或变现。

## 核心业务与 AI 工作流

Account → Profile → Diagnosis → 人工确认定位 → Research Input → Research AI Analysis
→ Confirm Research → TOP 3 Topics → Evidence → Select Topic → Draft V1 → Edit → Draft V2。

每个 AI 节点：读取上下文 → running WorkflowRun → 真实模型 → JSON / Schema / 引用检查
→ 合法结果真实保存，或 failed 并显示错误。没有生产 Mock 成功兜底。
tokens/cost 仅记录服务商实际返回值。所有核心数据写入 SQLite，刷新及后端重启不清空。

## Evidence First 与 Fact / Hypothesis

- 用户资料是自述，不是外部认证；定位、研究解读、选题均为待验证假设。
- Research 引用原文；Topic 关联 Profile、Diagnosis、Research ID 和原文片段。
- DraftVersion 绑定 Topic，保留不可变来源快照；更新输入不覆盖历史证据。
- `null` 指标表示未知，`0` 表示已知为零，不能互换。
- 确认定位不等于效果验证。Studio 初稿采用中性方案，拒绝 AI 代写第一人称经历。
  用户可在核实后手动编辑，但人工修改不自动获得事实认证。
- 发布前检查草稿的待核实事项；Schema 合法和引用存在，不等于语义完全真实。

## Bad Case 与 AI Evaluation

明确区分确定性/Mock、真实模型、真实 HTTP E2E 和人工浏览器验收；skipped 不计通过。
最终回归 **526 passed、74 skipped、0 failed**；前端检查与构建通过。
独立测试账号全链路包含 6 个成功真实模型节点，无 Mock 替代。

关键 Bad Cases：Research/Topics 截断通过局部控制输出篇幅修复，未删除核心字段；
Studio 虚构用户经历增加中性方案约束及拒绝规则；保存无反馈改为就地提示实际版本与错误。
原先无法追溯原始响应的 Research 个例仍不能归因；最终 E2E 新复现的截断有明确完成原因，
同条重测通过，失败 Workflow 仍保留。详见 [最终验收报告](docs/v01-final-validation.md)。

## Demo 操作流程

1. Account 保存资料，生成 Diagnosis，阅读假设与缺失信息，确认定位。
2. Research 手动导入有权使用的参考内容；未知指标留空，明确零值填 0。
3. 逐篇分析、查看研究卡和引用，确认用于选题。
4. Topics 选择 1–3 篇已分析、已确认的参考内容，生成 TOP 3，检查“为什么现在适合”与来源证据。
5. Studio 选择当前定位对应的 Topic，生成 Draft V1，核实正文及来源。
6. 修改明显字段，保存为 V2；按钮旁显示实际版本号，切换查看 V1/V2。
7. 刷新确认数据保留。再次生成会另建草稿，不覆盖旧稿。

本机最终测试账号：`V0.1 Final Validation 20261013`。它不是仓库种子数据；新机器需自行建档。

## 本地运行

环境基线：Python 3.12、Node 24；使用项目 `.venv`。依赖定义见 `pyproject.toml`。
以下命令须在仓库根目录运行，无需激活虚拟环境。首次安装可运行
`python -m venv .venv` 和 `.\.venv\Scripts\python.exe -m pip install -e .`。

```powershell
.\.venv\Scripts\python.exe -m easel.growth
.\.venv\Scripts\python.exe -m uvicorn web.app:app --host 127.0.0.1 --port 7860
```

前端位于 `web/frontend`，首次安装运行 `npm ci`，构建 `npm run build`。
构建后打开 `http://127.0.0.1:7860/`。开发模式在前端目录运行 `npm run dev -- --host 127.0.0.1`，
其 `/api` 代理指向本地 7860 后端。修改后端代码后需重启进程。
看到 `Uvicorn running` 后保持窗口运行。PowerShell 出现 `>>` 时先 Ctrl+C，检查引号再重输；
连接被拒绝时先检查后端是否仍运行。只演示生产构建不必启动 5173。

不要将本地单用户服务暴露到公网；原有主机/Origin 防护不是用户认证。

## 私有试用与开源范围

`web/production.py` 提供管理员预置登录账号、用户数据隔离及服务端访问保护；Ubuntu 24.04 部署文件位于 `deploy/ubuntu24/`，采用 systemd、Caddy HTTPS 与持久化 SQLite。参见[部署说明](docs/deployment-ubuntu24.md)与[部署验证记录](docs/private-deployment-validation.md)；验证记录反映当时的本地验收范围，不代表所有部署环境已验收。

源码公开不等于线上服务开放注册，也不包含可用测试密码。API Key、`.env`、本地数据库、个人内容与原始模型响应不应提交到仓库。新部署使用独立数据目录，按部署说明配置凭据并验证备份。

私有部署准备阶段记录的完整回归为 **541 passed、74 skipped**，专用安全测试 **5 passed**；这是历史验证记录，本次文档更新未重跑测试，跳过项不计为通过。

## 模型配置

在项目根目录本地 `.env` 填写以下模型配置（文件已被 Git 忽略，勿分享 Key）：

- `GROWTH_LLM_BASE_URL`：包含 `/v1` 等接口前缀，不包含 `/chat/completions`。
- `GROWTH_LLM_MODEL`：接口支持的模型 ID。
- `GROWTH_LLM_API_KEY`：本地配置，不写入源码、README、日志或前端。
- `GROWTH_DB_PATH`：可选，默认 `data/growth.sqlite3`。

采用无工具的兼容 Chat Completions JSON 调用，不需要启动全能 Agent。
不自动读取旧 Easel 的凭证文件；不会将 `.env` Key 导出给子进程。配置后重启后端。
`GROWTH_DB_PATH` 仍通过进程环境变量设置；显式进程配置优先于 `.env`。
真实模型与确定性测试必须分别验收，不能把 Mock 测试当成真实模型质量结果。

## 测试与设计

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests skills/openclaw/skill-wechat-publisher/tests -q --tb=short -p no:cacheprovider
```

- [数据层](docs/growth-data-layer.md)
- [Phase 3 实现、验证与限制](docs/growth-phase3.md)
- [Diagnosis Skill](skills/growth/diagnosis/SKILL.md)
- [原 Easel 中文文档（归档）](docs/upstream-README.zh-CN.md)

## Known Limitations

- 本地入口是单用户 Demo，不应直接暴露公网；私有试用需使用受保护的生产入口，不是完整商业 SaaS。
- 不含自动抓取/发布、图片生成、QC、Metrics、Strategy Update 等 V0.2 功能。
- 参考内容与计数来自用户输入，不能核实来源真伪、授权、统计口径或实时平台趋势。
- 校验只能拦截已知风险，不保证零幻觉；AI 建议与人工编辑都需要审阅。
- 模型有费用、延迟、限流、偶发格式错误/截断；不能绕过校验强行保存。
- 不自动保存编辑；切换账号、草稿、版本或刷新前先保存。旧版本只读。
- 74 项 skipped 不代表通过；2 条上游 lint 警告非阻塞。外部平台测试依赖额外环境。

## 开源归属与许可证

保留原 Easel [Apache-2.0 License](LICENSE)、版权、归属声明及已有 notices。
内部 `easel` 包和原有能力保留，未因为产品品牌变更而重命名或移除。
上游 README 的完整内容归档保留；归档中的相对链接按原项目根目录解释。
