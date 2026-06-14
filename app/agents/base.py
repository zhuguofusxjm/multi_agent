from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.llm_client import LLMClient
from app.core.session import SubAgentState, Message


# ─── Skill 层 ────────────────────────────────────────────────────────────────


@dataclass
class SkillInput:
    """Skill的输入：对话上下文 + 前序Skill的输出"""
    messages: list[Message]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillOutput:
    """Skill的输出：结果数据 + 简短摘要"""
    result: Any
    summary: str


class Skill(ABC):
    """Skill基类 — SubAgent内部的原子能力单元"""

    name: str
    description: str

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @abstractmethod
    async def run(self, input: SkillInput) -> SkillOutput:
        """执行该Skill的具体逻辑，返回结果"""
        ...


# ─── SubAgent 层 ─────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    """SubAgent的统一返回结构"""
    reply: str                                           # 主聊天区文本回复
    side_panel: Any = None                               # 右侧面板内容（案例/配置树/图表）
    data: Any = None                                     # 原始数据（供跨SubAgent引用）
    metadata: dict[str, Any] = field(default_factory=dict)  # 元信息（如SQL、标签等）


class BaseSubAgent(ABC):
    """SubAgent基类 — 领域专家，由Supervisor调度执行"""

    name: str
    description: str

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @abstractmethod
    async def execute(
        self, messages: list[Message], state: SubAgentState
    ) -> AgentResult:
        """执行SubAgent的核心逻辑，接收裁剪后的上下文和局部状态"""
        ...
