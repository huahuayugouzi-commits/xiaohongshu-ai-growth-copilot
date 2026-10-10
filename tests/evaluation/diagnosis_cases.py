"""Labeled fixtures, never production diagnosis fallbacks."""

from copy import deepcopy


def valid_result():
    return {
        "positioning_hypothesis": {"positioning": "可尝试面向家长的学习方法分享", "target_audience": "需要陪伴孩子学习的家长",
                                   "core_value": "探索把教学经验转成可操作的建议", "differentiation": "有待通过内容反馈验证"},
        "content_pillars": [{"name": "学习方法", "reason": "可基于用户提供的教学经历开展实验"}],
        "strengths": ["小学教师"], "risks": ["定位尚未验证"], "missing_information": ["可分享的具体素材有哪些？"],
        "assumptions": ["假设目标受众对学习方法有需求，需研究确认"], "confidence": "medium",
    }


PROFILE = {"occupation": "小学教师", "experience": "有课堂教学经历", "skills": "课程设计", "interests": "学习方法", "creator_goal": "希望转型成为教育内容创作者"}


def cases():
    result = []
    good = valid_result()
    bad = deepcopy(good); bad["strengths"] = ["已经成为成功的教育内容创作者"]
    result.append(("D01", PROFILE, good, bad))
    sparse = {"creator_goal": "我想做小红书，但不知道做什么。"}
    good = {"positioning_hypothesis": {"positioning": "待补充信息后确定", "target_audience": "待补充信息后确定", "core_value": "需要了解个人经验", "differentiation": "暂不判断"},
            "content_pillars": [], "strengths": [], "risks": ["信息不足"], "missing_information": ["请补充经验、兴趣和素材"], "assumptions": [], "confidence": "low"}
    bad = deepcopy(good); bad["positioning_hypothesis"]["positioning"] = "女性成长赛道"
    result.append(("D02", sparse, good, bad))
    conflict = {**PROFILE, "current_problem": "不露脸、不分享个人经历", "creator_goal": "希望打造强个人IP"}
    good = valid_result(); good["risks"] = ["不露脸、不分享个人经历与强个人IP目标存在约束冲突，需要先明确表达方式"]
    bad = deepcopy(good); bad["risks"] = []
    result.append(("D03", conflict, good, bad))
    good = valid_result(); bad = deepcopy(good); bad["positioning_hypothesis"]["differentiation"] = "你是硕士，月入10万，有10万粉丝"
    result.append(("D04", PROFILE, good, bad))
    good = valid_result(); bad = deepcopy(good); bad["positioning_hypothesis"]["positioning"] = "该定位已经验证，该方向表现最好"
    result.append(("D05", PROFILE, good, bad))
    return result
