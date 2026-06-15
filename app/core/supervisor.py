from __future__ import annotations

from app.agents.base import AgentResult, BaseSubAgent
from app.core.llm_client import LLMClient
from app.core.session import SubAgentState, Message, Session

SUPERVISOR_SYSTEM_PROMPT = """你是一个运营商智能助手的调度员。根据用户的最新消息和对话历史，判断应该由哪个专家处理。

可用专家：
1. query_agent — 查询数据、统计分析（如：某省用户流量、收入、用量统计等）
2. design_agent — 套餐设计（如：帮我设计一个XX套餐、给出套餐建议等）
3. config_agent — 套餐配置（如：帮我配置XX套餐的资费/租费信息等）

判断规则：
- 如果用户的请求包含多个步骤（如"先查数据再设计套餐"），每次只输出当前应该执行的下一步
- 如果所有步骤都已完成，target_agent设为"done"
- 如果用户明确在追问或修改上一轮结果，is_followup=true，target_agent保持不变
- 如果用户话题切换到新领域，is_followup=false
- 如果无法判断属于哪个专家（如闲聊、问好），target_agent设为"general"

请严格按以下JSON格式输出，不要输出其他内容：
{
  "target_agent": "query_agent或design_agent或config_agent或general或done",
  "is_followup": true或false,
  "context_summary": "用一句话概括用户需求和需要传递给子Agent的关键上下文"
}"""

# 防止死循环的最大迭代次数
MAX_LOOP_ITERATIONS = 3


class Supervisor:
    """调度员（主Agent）— 意图路由 + 上下文裁剪 + 结果整合（Loop模式）"""

    def __init__(self, llm: LLMClient, sub_agents: dict[str, BaseSubAgent]):
        self.llm = llm
        self.sub_agents = sub_agents

    async def handle(self, session: Session, user_message: str) -> AgentResult:
        """
        处理一次用户请求的完整流程（Loop模式）：
        支持一句话触发多个SubAgent串联执行，如"查完数据再帮我设计套餐"
        """

        # ── 1.记录用户输入 ──
        session.global_history.append(Message(role="user", content=user_message))

        # ── 2.Loop：反复路由直到任务完成或达到最大次数 ──
        final_result: AgentResult | None = None
        accumulated_replies: list[str] = []

        for iteration in range(MAX_LOOP_ITERATIONS):

            # 路由决策：LLM判断下一步应交给哪个SubAgent
            routing = await self._route(session)
            target = routing.get("target_agent", "general")

            # 终止条件：所有步骤已完成
            if target == "done":
                break

            # 兜底：无法路由时直接回复
            if target == "general":
                final_result = await self._general_reply(session)
                break

            sub_agent = self.sub_agents.get(target)
            if not sub_agent:
                final_result = await self._general_reply(session)
                break

            # ── 3.准备 & 执行当前SubAgent ──
            sub_agent_state = session.get_sub_agent_state(target)
            sub_agent_messages = self._prepare_sub_agent_input(session, sub_agent_state, routing)
            result = await sub_agent.execute(sub_agent_messages, sub_agent_state)

            # ── 4.更新状态 ──
            self._update_session(session, target, result, routing)
            self._update_sub_agent_state(sub_agent_state, user_message, result)

            # 将中间结果记入全局历史，供下一轮路由参考
            session.global_history.append(Message(role="assistant", content=result.reply))

            accumulated_replies.append(result.reply)
            final_result = result

        # ── 5.组装最终回复 ──
        if final_result is None:
            final_result = await self._general_reply(session)
        elif len(accumulated_replies) > 1:
            # 多个SubAgent串联执行时，合并所有回复
            final_result = AgentResult(
                reply="\n\n---\n\n".join(accumulated_replies),
                side_panel=final_result.side_panel,
                data=final_result.data,
                metadata={"loop_iterations": len(accumulated_replies)},
            )
        else:
            # 单次执行时，global_history已在loop内追加，无需重复
            pass

        return final_result

    async def _route(self, session: Session) -> dict:
        """意图路由：取最近10轮历史，让LLM判断下一步应交给哪个SubAgent"""
        recent_history = session.global_history[-10:]
        try:
            return await self.llm.chat_json(
                messages=recent_history,
                system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            )
        except Exception:
            return {"target_agent": "general", "is_followup": False, "context_summary": ""}

    def _prepare_sub_agent_input(
        self, session: Session, sub_agent_state: SubAgentState, routing: dict
    ) -> list[Message]:
        """为目标SubAgent裁剪和组装输入上下文，避免传入无关信息"""
        messages: list[Message] = []

        # 1) 注入其他SubAgent的输出数据，供跨Agent引用
        if session.global_sub_agent_output_data:
            context_str = "\n".join(
                f"- {k}: {v}" for k, v in session.global_sub_agent_output_data.items()
            )
            messages.append(Message(role="system", content=f"参考信息：\n{context_str}"))

        # 2) 该SubAgent自己的最近6轮对话历史
        messages.extend(sub_agent_state.history[-6:])

        # 3) Supervisor提炼的本次意图摘要
        if summary := routing.get("context_summary"):
            messages.append(Message(role="system", content=f"用户意图补充：{summary}"))

        # 4) 当前用户消息
        messages.append(session.global_history[-1])

        return messages

    def _update_session(
        self,
        session: Session,
        target: str,
        result: AgentResult,
        routing: dict,
    ):
        """更新全局Session：标记活跃SubAgent + 存储输出数据供跨Agent引用"""
        session.active_sub_agent = target

        if result.data:
            summary = routing.get("context_summary", "")
            session.global_sub_agent_output_data[f"{target}_latest"] = {
                "summary": summary,
                "data": str(result.data)[:500],
            }

    def _update_sub_agent_state(
        self,
        sub_agent_state: SubAgentState,
        user_message: str,
        result: AgentResult,
    ):
        """更新SubAgent局部状态：将本轮对话追加到该SubAgent自己的历史"""
        sub_agent_state.history.append(Message(role="user", content=user_message))
        sub_agent_state.history.append(Message(role="assistant", content=result.reply))

    async def _general_reply(self, session: Session) -> AgentResult:
        """兜底回复：无法路由时作为通用助手回答，并引导用户明确需求"""
        reply = await self.llm.chat(
            messages=session.global_history[-6:],
            system_prompt="你是一个运营商智能助手。如果用户的问题不明确，请友好地引导他们说明需求（查数据、设计套餐、配置套餐）。",
        )
        session.global_history.append(Message(role="assistant", content=reply))
        return AgentResult(reply=reply)
