"""LLM communication layer for the scratch_agents framework."""

from __future__ import annotations

import json
from typing import List, Protocol

from pydantic import BaseModel, Field

from .types import ContentItem, Message, ToolCall, ToolResult
from .base import BaseTool


class LlmRequest(BaseModel):
    """Request object for LLM calls."""
    model_config = {"arbitrary_types_allowed": True}

    instructions: List[str] = Field(default_factory=list)
    contents: List[ContentItem] = Field(default_factory=list)
    tools: List[BaseTool] = Field(default_factory=list)
    tool_choice: str | None = None


class LlmResponse(BaseModel):
    """Response object from LLM calls."""
    content: List[ContentItem] = Field(default_factory=list)
    error_message: str | None = None


def build_messages(request: LlmRequest) -> List[dict]:
    """Convert LlmRequest to API message format."""
    messages = []

    for instruction in request.instructions:
        messages.append({"role": "system", "content": instruction})

    for item in request.contents:
        if isinstance(item, Message):
            messages.append({"role": item.role, "content": item.content})

        elif isinstance(item, ToolCall):
            tool_call_dict = {
                "id": item.tool_call_id,
                "type": "function",
                "function": {
                    "name": item.name,
                    "arguments": json.dumps(item.arguments),
                },
            }
            if messages and messages[-1]["role"] == "assistant":
                messages[-1].setdefault("tool_calls", []).append(tool_call_dict)
            else:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call_dict],
                })

        elif isinstance(item, ToolResult):
            messages.append({
                "role": "tool",
                "tool_call_id": item.tool_call_id,
                "content": str(item.content[0]) if item.content else "",
            })

    return messages


class Model(Protocol):
    async def generate(self, request: LlmRequest) -> LlmResponse: ...


class LlmClient:
    """Client for LLM API calls using LiteLLM."""

    def __init__(self, model: str, **config):
        self.model = model
        self.config = config

    async def generate(self, request: LlmRequest) -> LlmResponse:
        """Generate a response from the LLM."""
        from litellm import acompletion

        try:
            messages = build_messages(request)
            tools = [t.tool_definition for t in request.tools] if request.tools else None

            response = await acompletion(
                model=self.model,
                messages=messages,
                tools=tools,
                **({"tool_choice": request.tool_choice} if request.tool_choice else {}),
                **self.config,
            )

            return self._parse_response(response)
        except Exception as e:
            return LlmResponse(error_message=str(e))

    def _parse_response(self, response) -> LlmResponse:
        """Convert API response to LlmResponse."""
        choice = response.choices[0]
        content_items = []

        if choice.message.content:
            content_items.append(Message(
                role="assistant",
                content=choice.message.content,
            ))

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                content_items.append(ToolCall(
                    tool_call_id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return LlmResponse(content=content_items)
