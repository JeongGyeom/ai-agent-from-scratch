"""4장 ReAct 루프와 구조화 응답을 구현한다."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from .llm import LlmRequest, LlmResponse, Model
from .types import Event, Message, ToolCall, ToolResult
from .base import BaseTool, FunctionTool
from .tool_schema import format_tool_definition
from .context import AgentResult, ExecutionContext


class Agent:
    """Tool-calling agent with ReAct loop."""

    def __init__(
        self,
        model: Model,
        tools: List[BaseTool] | None = None,
        instructions: str = "",
        max_steps: int = 10,
        name: str = "agent",
        output_type: type[BaseModel] | None = None,
    ):
        self.model = model
        self.instructions = instructions
        self.max_steps = max_steps
        self.name = name
        self.output_type = output_type
        self.output_tool_name: str | None = None
        self.tools = self._setup_tools(tools or [])

    # ------------------------------------------------------------------ #
    # Core loop
    # ------------------------------------------------------------------ #

    async def run(
        self,
        user_input: str | None = None,
        context: ExecutionContext | None = None,
    ) -> AgentResult:
        """Execute the agent."""
        if context is None:
            context = ExecutionContext()

        if user_input:
            user_event = Event(
                execution_id=context.execution_id,
                author="user",
                content=[Message(role="user", content=user_input)],
            )
            context.add_event(user_event)

        while context.final_result is None and context.current_step < self.max_steps:
            await self.step(context)

            if context.events:
                last_event = context.events[-1]
                if self._is_final_response(last_event):
                    context.final_result = self._extract_final_result(last_event)

        return AgentResult(output=context.final_result, context=context)

    async def step(self, context: ExecutionContext) -> None:
        """Perform one think-act cycle."""
        # 이전 단계의 도구 결과까지 포함한 이력을 모델에 전달한다.
        llm_request = self._prepare_llm_request(context)
        llm_response = await self.think(llm_request)

        if llm_response.error_message is not None:
            raise RuntimeError(f"LLM request failed: {llm_response.error_message}")

        response_event = Event(
            execution_id=context.execution_id,
            author=self.name,
            content=llm_response.content,
        )
        context.add_event(response_event)

        tool_calls = [c for c in llm_response.content if isinstance(c, ToolCall)]
        if tool_calls:
            await self.act(context, tool_calls)

        context.increment_step()

    async def think(self, llm_request: LlmRequest) -> LlmResponse:
        """Call the LLM to decide the next action."""
        return await self.model.generate(llm_request)

    async def act(
        self,
        context: ExecutionContext,
        tool_calls: List[ToolCall],
    ) -> None:
        """Execute the tools requested by the LLM."""
        tools_dict = {t.name: t for t in self.tools}
        results = []

        for tool_call in tool_calls:
            if tool_call.name not in tools_dict:
                results.append(ToolResult(
                    tool_call_id=tool_call.tool_call_id,
                    name=tool_call.name,
                    status="error",
                    content=[f"Tool '{tool_call.name}' not found"],
                ))
                continue

            tool_obj = tools_dict[tool_call.name]

            try:
                output = await tool_obj(context, **tool_call.arguments)
                results.append(ToolResult(
                    tool_call_id=tool_call.tool_call_id,
                    name=tool_call.name,
                    status="success",
                    content=[output],
                ))
            except Exception as e:
                results.append(ToolResult(
                    tool_call_id=tool_call.tool_call_id,
                    name=tool_call.name,
                    status="error",
                    content=[str(e)],
                ))

        # 이번 단계의 도구 결과를 다음 요청에서 모델이 읽을 수 있게 기록한다.
        if results:
            tool_event = Event(
                execution_id=context.execution_id,
                author=self.name,
                content=results,
            )
            context.add_event(tool_event)

    # ------------------------------------------------------------------ #
    # Internal methods
    # ------------------------------------------------------------------ #

    def _prepare_llm_request(self, context: ExecutionContext) -> LlmRequest:
        """Build an LlmRequest from the current context."""
        flat_contents = []
        for event in context.events:
            flat_contents.extend(event.content)

        instructions = []
        if self.instructions:
            instructions.append(self.instructions)

        if self.output_tool_name:
            tool_choice = "required"
        elif self.tools:
            tool_choice = "auto"
        else:
            tool_choice = None

        return LlmRequest(
            instructions=instructions,
            contents=flat_contents,
            tools=self.tools,
            tool_choice=tool_choice,
        )

    def _is_final_response(self, event: Event) -> bool:
        """Check if this event contains a final response."""
        if self.output_tool_name:
            for item in event.content:
                if (
                    isinstance(item, ToolResult)
                    and item.name == self.output_tool_name
                    and item.status == "success"
                ):
                    return True
            return False

        has_tool_calls = any(isinstance(c, ToolCall) for c in event.content)
        has_tool_results = any(isinstance(c, ToolResult) for c in event.content)
        return not has_tool_calls and not has_tool_results

    def _extract_final_result(self, event: Event) -> str | BaseModel | None:
        """Extract the final result from an event."""
        if self.output_tool_name:
            for item in event.content:
                if (
                    isinstance(item, ToolResult)
                    and item.name == self.output_tool_name
                    and item.status == "success"
                    and item.content
                ):
                    return item.content[0]

        for item in event.content:
            if isinstance(item, Message) and item.role == "assistant":
                return item.content
        return None

    def _setup_tools(self, tools: List[BaseTool]) -> List[BaseTool]:
        """Prepare the tools list, including dynamic tools."""
        tools = list(tools)

        if self.output_type is not None:
            output_schema = self.output_type.model_json_schema()
            output_schema.pop("title", None)
            definitions = output_schema.pop("$defs", None)

            tool_definition = format_tool_definition(
                "final_answer",
                "Return the final structured answer matching the required schema.",
                {
                    "type": "object",
                    "properties": {"output": output_schema},
                    "required": ["output"],
                    **({"$defs": definitions} if definitions else {}),
                },
            )

            captured_type = self.output_type

            def _parse_output(output: dict) -> BaseModel:
                return captured_type.model_validate(output)

            final_answer_tool = FunctionTool(
                func=_parse_output,
                name="final_answer",
                description="Return the final structured answer matching the required schema.",
                tool_definition=tool_definition,
            )
            tools.append(final_answer_tool)
            self.output_tool_name = "final_answer"

        return tools
