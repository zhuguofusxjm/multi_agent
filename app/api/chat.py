from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.config_agent import ConfigAgent
from app.agents.design_agent import DesignAgent
from app.agents.query_agent import QueryAgent
from app.core.llm_client import LLMClient
from app.core.session import SessionManager
from app.core.supervisor import Supervisor

router = APIRouter()

# ─── 初始化组件 ──────────────────────────────────────────────────────────────

llm = LLMClient()
session_manager = SessionManager()

sub_agents = {
    "query_agent": QueryAgent(llm),
    "design_agent": DesignAgent(llm),
    "config_agent": ConfigAgent(llm),
}

supervisor = Supervisor(llm=llm, sub_agents=sub_agents)


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """用户请求：消息 + 可选的session_id（多轮时传入）"""
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    """服务端响应：回复文本 + 可选的侧边栏 + 状态信息"""
    session_id: str
    reply: str
    side_panel: Any = None
    active_sub_agent: str | None = None
    metadata: dict[str, Any] = {}


# ─── 接口 ────────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """统一聊天入口：接收用户消息，经Supervisor调度后返回结果"""

    # 获取或创建会话（多轮时复用同一session_id）
    session = session_manager.get_or_create(request.session_id)

    # Supervisor处理完整流程：路由 → SubAgent执行 → 状态更新
    result = await supervisor.handle(session, request.message)

    return ChatResponse(
        session_id=session.session_id,
        reply=result.reply,
        side_panel=result.side_panel,
        active_sub_agent=session.active_sub_agent,
        metadata=result.metadata,
    )
