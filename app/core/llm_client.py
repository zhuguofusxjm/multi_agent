from __future__ import annotations

import json
import os
from typing import Any

from openai import AsyncOpenAI

from app.core.session import Message


class LLMClient:
    """DeepSeek API 封装，使用 OpenAI 兼容接口"""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model = "deepseek-chat"

    async def chat(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """普通对话调用，返回LLM生成的文本"""
        api_messages = self._build_messages(messages, system_prompt)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
        )
        return response.choices[0].message.content

    async def chat_json(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """结构化输出调用，强制LLM返回JSON，解析为dict"""
        api_messages = self._build_messages(messages, system_prompt)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    def _build_messages(
        self, messages: list[Message], system_prompt: str | None
    ) -> list[dict]:
        """将内部Message对象转换为OpenAI API所需的dict格式"""
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        return api_messages
