from __future__ import annotations

from app.agents.base import (
    AgentResult,
    BaseSubAgent,
    Skill,
    SkillInput,
    SkillOutput,
)
from app.core.llm_client import LLMClient
from app.core.session import SubAgentState, Message
from app.data.case_store import search_cases
from app.data.tag_library import TAG_LIBRARY_TEXT


# ─── Skills ──────────────────────────────────────────────────────────────────


class TagReasoningSkill(Skill):
    """标签推理Skill — 从用户需求中推理出最匹配的Top10标签"""

    name = "tag_reasoning"
    description = "根据套餐设计需求，从标签库中推理最匹配的Top10标签并给出理由"

    async def run(self, input: SkillInput) -> SkillOutput:
        """调用LLM从标签库中选出最匹配的标签"""
        prompt = f"""标签库：
{TAG_LIBRARY_TEXT}

请根据用户的套餐设计需求，从以上标签库中选出最匹配的标签（最多10个）。
输出JSON格式：
{{"tags": [{{"id": "T001", "name": "高流量", "reason": "选择理由"}}]}}"""

        result = await self.llm.chat_json(messages=input.messages, system_prompt=prompt)
        tags = result.get("tags", [])
        return SkillOutput(
            result=tags,
            summary=f"推荐{len(tags)}个标签：{', '.join(t['name'] for t in tags[:5])}...",
        )


class DesignSuggestionSkill(Skill):
    """设计建议Skill — 基于标签发散补充套餐设计建议"""

    name = "design_suggestion"
    description = "基于已选标签，补充价格策略、差异化卖点、目标人群等设计建议"

    async def run(self, input: SkillInput) -> SkillOutput:
        """引用前序TagReasoningSkill的输出标签，让LLM补充设计建议"""
        tags = input.context.get("tag_reasoning", [])
        tag_names = ", ".join(t["name"] for t in tags) if tags else "未知"

        prompt = f"""你是运营商套餐设计专家。基于以下推荐标签，补充套餐设计建议。

推荐标签：{tag_names}

请从以下维度给出建议：
1. 定价策略
2. 流量/语音/短信配置
3. 差异化卖点
4. 目标人群画像
5. 竞争优势

用清晰的结构化文本回答。"""

        suggestions = await self.llm.chat(messages=input.messages, system_prompt=prompt)
        return SkillOutput(result=suggestions, summary="设计建议已生成")


class CaseMatchingSkill(Skill):
    """案例匹配Skill — 用标签检索最匹配的历史案例"""

    name = "case_matching"
    description = "根据推荐标签在案例库中检索最匹配的历史套餐案例"

    async def run(self, input: SkillInput) -> SkillOutput:
        """引用前序TagReasoningSkill的输出标签，在案例库中做相似匹配"""
        tags = input.context.get("tag_reasoning", [])
        tag_ids = [t["id"] for t in tags] if tags else []
        cases = search_cases(tag_ids, top_k=3)
        return SkillOutput(
            result=cases,
            summary=f"匹配到{len(cases)}个历史案例",
        )


# ─── SubAgent ────────────────────────────────────────────────────────────────


class DesignAgent(BaseSubAgent):
    """设计SubAgent — 通过Skill流水线完成：标签推理 → 设计建议 → 案例匹配"""

    name = "design_agent"
    description = "运营商套餐设计，推荐标签、给出建议、匹配案例"

    # Skill执行顺序：前一个Skill的输出可被后续Skill通过context引用
    skill_pipeline = ["tag_reasoning", "design_suggestion", "case_matching"]

    def __init__(self, llm: LLMClient):
        super().__init__(llm)
        self.skills: dict[str, Skill] = {
            "tag_reasoning": TagReasoningSkill(llm),
            "design_suggestion": DesignSuggestionSkill(llm),
            "case_matching": CaseMatchingSkill(llm),
        }

    async def execute(
        self, messages: list[Message], state: SubAgentState
    ) -> AgentResult:
        """按流水线顺序执行各Skill，前序输出通过context传递给后续Skill"""

        # context在流水线中逐步积累各Skill的输出
        context: dict = {}

        for skill_name in self.skill_pipeline:
            skill = self.skills[skill_name]
            output = await skill.run(SkillInput(messages=messages, context=context))
            context[skill_name] = output.result

        # 从context中提取各Skill的结果
        tags = context["tag_reasoning"]
        suggestions = context["design_suggestion"]
        cases = context["case_matching"]

        return AgentResult(
            reply=f"**推荐标签：**\n"
            + "\n".join(f"- {t['name']}：{t['reason']}" for t in tags)
            + f"\n\n**设计建议：**\n{suggestions}",
            side_panel={"type": "cases", "data": cases},
            data={"tags": tags, "suggestions": suggestions},
            metadata={"matched_cases": len(cases)},
        )
