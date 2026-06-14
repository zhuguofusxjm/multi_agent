from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """一条对话消息"""
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class SubAgentState:
    """单个子Agent的局部状态"""
    name: str
    history: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    step: str | None = None


@dataclass
class Session:
    """一次用户会话的完整状态"""
    session_id: str
    global_history: list[Message] = field(default_factory=list)                  # 全局对话历史
    global_sub_agent_output_data: dict[str, Any] = field(default_factory=dict)   # 全局子Agent输出数据（跨Agent共享）
    active_sub_agent: str | None = None                                          # 当前活跃子Agent
    sub_agent_states: dict[str, SubAgentState] = field(default_factory=dict)     # 各子Agent局部状态


    def get_sub_agent_state(self, agent_name: str) -> SubAgentState:
        """获取指定子Agent的局部状态，不存在则自动创建"""
        if agent_name not in self.sub_agent_states:
            self.sub_agent_states[agent_name] = SubAgentState(name=agent_name)
        return self.sub_agent_states[agent_name]


class SessionManager:
    """会话管理器 — 内存存储，预留持久化接口"""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None = None) -> Session:
        """根据session_id获取已有会话，或创建新会话"""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        new_id = session_id or str(uuid.uuid4())
        session = Session(session_id=new_id)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """根据session_id查找会话，不存在返回None"""
        return self._sessions.get(session_id)
