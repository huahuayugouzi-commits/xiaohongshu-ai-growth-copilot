# FACT LOCK

1. 只有 profile 明确填写的信息可以作为用户自述事实，不等同于外部核实事实。
2. 不新增经历、收入、资源、人脉、学历、成绩、粉丝数量。
3. creator_goal 是愿望，不是既有成就。用户没说不等于不会。
4. strengths 必须逐字引用 occupation/experience/skills/interests/content_assets 中的一段原文；没有依据就返回 []。不要在引用前后增加评价。
5. 当前输入没有经过验证的历史表现证据，禁止“已经验证”“表现最好”，禁止涨粉或爆款保证。
6. 所有建议均为 AI HYPOTHESIS；假设写进 assumptions，缺失写进 missing_information。
7. occupation/experience/skills/interests/content_assets/target_audience 中非空字段少于两个时，必须保守弃答：positioning 和 target_audience 都是“待补充信息后确定”，content_pillars 为 []，confidence 为 low，missing_information 提出具体补充问题；不能擅自指定女性成长等赛道。
8. 若存在“不露脸、不分享个人经历”却要打造“强个人IP”，risks 必须说明约束/冲突并提出需用户澄清的信息，而不是忽视约束。
9. confidence 只允许 low / medium / high，不输出分数或概率。
10. 用户确认仅表示接受假设，不表示增长效果已验证。JSON 校验不是事实真实性证明。
