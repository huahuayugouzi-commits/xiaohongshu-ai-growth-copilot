# Growth Copilot

**小红书 AI 增长助手**

从真实账号背景出发，形成定位假设，由用户确认后再进入内容研究与创作。
Growth Copilot is built upon the open-source [Easel](https://github.com/ZJU-REAL/Easel) project.

## 当前阶段：Account + AI Diagnosis

- Account：新手 / 已有账号建档，SQLite 持久化和 Profile 版本。
- Diagnosis：真实兼容模型调用、结构化结果、Fact Lock 检查、人工确认。
- Dashboard：读取数据库中的账号、定位、版本和流程状态。
- Research / Topics / Studio：Coming Soon，尚未实现。

模型未配置时可保存资料；诊断显示配置错误，不使用模拟结果兜底。
AI 建议是待验证假设，不是效果承诺或已核实事实。

## 本地运行

环境基线：Python 3.12、Node 24；使用项目 `.venv`。依赖定义见 `pyproject.toml`。

```powershell
.\.venv\Scripts\python.exe -m easel.growth
.\.venv\Scripts\python.exe -m uvicorn web.app:app --host 127.0.0.1 --port 7860
```

前端位于 `web/frontend`，首次安装运行 `npm ci`，构建 `npm run build`。
构建后打开 `http://127.0.0.1:7860/`。开发模式在前端目录运行 `npm run dev -- --host 127.0.0.1`，
其 `/api` 代理指向本地 7860 后端。修改后端代码后需重启进程。

不要将本地单用户服务暴露到公网；原有主机/Origin 防护不是用户认证。

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

## 开源归属

保留原 Easel [Apache-2.0 License](LICENSE)、版权、归属声明及已有 notices。
内部 `easel` 包和原有能力保留，未因为产品品牌变更而重命名或移除。
上游 README 的完整内容归档保留；归档中的相对链接按原项目根目录解释。
