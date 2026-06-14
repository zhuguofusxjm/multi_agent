from __future__ import annotations

from app.agents.base import AgentResult, BaseSubAgent
from app.core.llm_client import LLMClient
from app.core.session import SubAgentState, Message

# 配置步骤定义：按此顺序逐步完成
STEPS = ["basic_info", "tariff", "rental"]

STEP_LABELS = {
    "basic_info": "基本信息",
    "tariff": "资费信息",
    "rental": "租费信息",
}

CONFIG_SYSTEM_PROMPT_TEMPLATE = """你是一个运营商套餐配置专家。当前需要配置套餐的"{step_label}"。

{completed_info}

请根据用户的输入，生成该步骤的配置信息。严格按JSON格式输出：

当前步骤：{step_name}

如果是 basic_info，输出：
{{"套餐名称": "...", "套餐类型": "...", "生效日期": "...", "目标客户群": "...", "套餐描述": "..."}}

如果是 tariff，输出：
{{"月基本费": 0, "流量(GB)": 0, "语音(分钟)": 0, "短信(条)": 0, "超出流量单价(元/GB)": 0, "超出语音单价(元/分钟)": 0}}

如果是 rental，输出：
{{"合约期限(月)": 0, "预存话费": 0, "月返还金额": 0, "违约金": 0, "是否含设备": false}}"""


class ConfigAgent(BaseSubAgent):
    """配置SubAgent — 多步骤状态机，逐步填充套餐的完整配置"""

    name = "config_agent"
    description = "套餐配置，按步骤填充基本信息、资费、租费"

    def __init__(self, llm: LLMClient):
        super().__init__(llm)

    async def execute(
        self, messages: list[Message], state: SubAgentState
    ) -> AgentResult:
        """执行当前步骤的配置，完成后自动推进到下一步"""

        # 首次调用时初始化步骤
        if state.step is None:
            state.step = STEPS[0]

        current_step = state.step

        # 所有步骤已完成，返回汇总
        if current_step == "done":
            return self._build_summary(state)

        # 构造当前步骤的prompt（包含已完成的配置作为参考）
        completed_info = self._format_completed(state)
        prompt = CONFIG_SYSTEM_PROMPT_TEMPLATE.format(
            step_label=STEP_LABELS[current_step],
            step_name=current_step,
            completed_info=completed_info,
        )

        # LLM填充当前步骤的配置
        config = await self.llm.chat_json(messages=messages, system_prompt=prompt)
        state.context[current_step] = config

        # 推进到下一步骤
        current_idx = STEPS.index(current_step)
        if current_idx + 1 < len(STEPS):
            next_step = STEPS[current_idx + 1]
            state.step = next_step
            reply = (
                f"已完成 **{STEP_LABELS[current_step]}** 配置。\n\n"
                f"配置内容：\n{self._format_config(config)}\n\n"
                f"接下来配置 **{STEP_LABELS[next_step]}**，请描述相关需求，或输入'继续'使用默认值。"
            )
        else:
            # 最后一步完成
            state.step = "done"
            reply = (
                f"已完成 **{STEP_LABELS[current_step]}** 配置。\n\n"
                f"配置内容：\n{self._format_config(config)}\n\n"
                f"所有配置步骤已完成！以下是完整的套餐配置树。"
            )

        return AgentResult(
            reply=reply,
            side_panel={"type": "config_tree", "data": state.context},
            data=state.context,
            metadata={"current_step": state.step},
        )

    def _build_summary(self, state: SubAgentState) -> AgentResult:
        """所有步骤已完成时的汇总回复"""
        full_config = state.context
        reply = "套餐配置已全部完成。如需修改某个步骤，请直接说明（如'修改资费信息'）。"
        return AgentResult(
            reply=reply,
            side_panel={"type": "config_tree", "data": full_config},
            data=full_config,
        )

    def _format_completed(self, state: SubAgentState) -> str:
        """将已完成的步骤格式化为文本，供LLM参考"""
        if not state.context:
            return "尚无已完成的配置。"
        lines = ["已完成的配置："]
        for step_name, config in state.context.items():
            label = STEP_LABELS.get(step_name, step_name)
            lines.append(f"\n{label}：")
            for k, v in config.items():
                lines.append(f"  - {k}: {v}")
        return "\n".join(lines)

    def _format_config(self, config: dict) -> str:
        """将单步配置格式化为可读文本"""
        return "\n".join(f"- {k}: {v}" for k, v in config.items())
