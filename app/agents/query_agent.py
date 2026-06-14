from __future__ import annotations

from app.agents.base import AgentResult, BaseSubAgent
from app.core.llm_client import LLMClient
from app.core.session import SubAgentState, Message
from app.data.table_schemas import TABLE_SCHEMAS

QUERY_SYSTEM_PROMPT = f"""你是一个运营商数据分析专家。根据用户的自然语言问题，生成SQL查询。

可用表结构：
{TABLE_SCHEMAS}

工作流程：
1. 理解用户问题
2. 生成对应的SQL（使用标准SQL语法）
3. 注意：只生成SELECT查询，不允许INSERT/UPDATE/DELETE

请严格按以下JSON格式输出：
{{"sql": "SELECT ...", "explanation": "这条SQL的含义简要说明"}}"""

INTERPRET_SYSTEM_PROMPT = """你是一个数据分析专家。根据用户的问题和SQL查询结果，用自然语言给出清晰的解读。
要求：
- 直接回答用户问题
- 给出关键数据
- 如果合适，给出简要分析或趋势说明"""


class QueryAgent(BaseSubAgent):
    """问数SubAgent — SQL生成 + 执行 + 结果解读"""

    name = "query_agent"
    description = "查询运营商数据，如用户流量、费用、订购统计等"

    def __init__(self, llm: LLMClient):
        super().__init__(llm)

    async def execute(
        self, messages: list[Message], state: SubAgentState
    ) -> AgentResult:
        """执行问数流程：生成SQL → 执行查询 → 解读结果"""

        # Step 1: LLM根据用户问题和表结构生成SQL
        sql_result = await self.llm.chat_json(
            messages=messages, system_prompt=QUERY_SYSTEM_PROMPT
        )
        sql = sql_result.get("sql", "")
        explanation = sql_result.get("explanation", "")

        # Step 2: 执行SQL（当前为模拟，实际对接真实数据库）
        query_result = self._simulate_execute(sql)

        # Step 3: LLM解读查询结果，生成自然语言回答
        interpret_messages = messages + [
            Message(
                role="system",
                content=f"SQL: {sql}\n说明: {explanation}\n查询结果: {query_result}",
            )
        ]
        reply = await self.llm.chat(
            messages=interpret_messages, system_prompt=INTERPRET_SYSTEM_PROMPT
        )

        return AgentResult(
            reply=reply,
            data=query_result,
            metadata={"sql": sql, "explanation": explanation},
        )

    def _simulate_execute(self, sql: str) -> str:
        """模拟SQL执行 — 实际项目中替换为真实数据库查询"""
        sql_lower = sql.lower()
        if "monthly_data_gb" in sql_lower and "广东" in sql_lower:
            return "| province | user_type | avg_monthly_data_gb |\n| 广东 | 5G | 15.2 |"
        if "monthly_data_gb" in sql_lower:
            return "| province | user_type | avg_monthly_data_gb |\n| 全国 | 5G | 12.8 |\n| 全国 | 4G | 6.5 |"
        if "arpu" in sql_lower:
            return "| plan_type | avg_arpu |\n| 畅享套餐 | 128.5 |\n| 冰淇淋套餐 | 98.2 |"
        if "plan_subscription" in sql_lower:
            return "| plan_name | total_subscribers |\n| 5G畅享199 | 523000 |\n| 5G畅享129 | 891000 |"
        return "| result |\n| 暂无匹配数据，请检查查询条件 |"
