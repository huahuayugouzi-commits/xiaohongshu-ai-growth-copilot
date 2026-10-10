---
name: growth-diagnosis
description: 用于 Growth Copilot 用户建档后的定位假设诊断；仅依据用户输入，不采集、不发布。
layer: plan
---

# Growth Diagnosis

当用户保存 Account/Profile 并明确请求“生成账号诊断”时，由 Growth 工作流调用。

输入：Account 的名称、creator_type 与当前 ProfileVersion 的用户原始字段。
输入合约：`easel.growth.diagnosis_schema.ProfileFields`（Pydantic JSON Schema 可导出）。
输出合约：`easel.growth.diagnosis_schema.DiagnosisResult`（唯一 schema 真相源）。

执行顺序：读取 [Prompt](prompt.md)、[Rules](rules.md)、[Examples](examples.json)，
调用无工具的模型接口，执行 JSON/Schema/Fact Lock 验证，事务保存 pending Diagnosis 与成功 WorkflowRun。
只有用户主动确认后才能标记 confirmed。失败必须显式记录，禁止生成默认诊断兜底。

复用 Easel 的独立 SKILL.md + 规则/参考资产组织方式，但不调用原全能 Agent 的采集、发布工具。
前端不得包含 Prompt。实现与 schema 位于 `easel/growth/`，不加入多 Agent 或新平台工具。
