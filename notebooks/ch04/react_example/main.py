"""계산기 도구를 사용하는 4장 ReAct 예제."""

import argparse
import asyncio

from pydantic import BaseModel

from react_agent.agent import Agent
from react_agent.calculator import calculator
from react_agent.llm import LlmClient, LlmRequest, LlmResponse, build_messages
from react_agent.types import Message, ToolCall, ToolResult


DEFAULT_PROMPT = "1234 곱하기 5678은 얼마야?"


class CalculationAnswer(BaseModel):
    """4.7절의 final_answer 도구가 반환하는 결과 형식."""

    result: float
    explanation: str


class DemoModel:
    """고정 질문을 사용해 모델의 tool calling 응답을 재현한다."""

    async def generate(self, request: LlmRequest) -> LlmResponse:
        # 실제 API에 전달하는 형식과 같게 변환해, 결과가 되돌아오는 길도 보여준다.
        last_message = build_messages(request)[-1]

        if last_message["role"] == "user":
            return LlmResponse(content=[ToolCall(
                tool_call_id="demo-calculation",
                name="calculator",
                arguments={
                    "operator": "multiply",
                    "first_number": 1234,
                    "second_number": 5678,
                },
            )])

        if last_message["role"] == "tool" and last_message["tool_call_id"] == "demo-calculation":
            result = last_message["content"]
            if request.tool_choice == "required":
                return LlmResponse(content=[ToolCall(
                    tool_call_id="demo-final",
                    name="final_answer",
                    arguments={"output": {
                        "result": float(result),
                        "explanation": "계산기로 1234와 5678을 곱했습니다.",
                    }},
                )])
            return LlmResponse(content=[Message(
                role="assistant",
                content=f"1234 × 5678 = {result}",
            )])

        return LlmResponse(error_message="데모가 예상한 메시지 순서와 다릅니다.")


async def run(prompt: str, model_name: str | None, structured: bool) -> None:
    model = LlmClient(model=model_name) if model_name else DemoModel()
    agent = Agent(
        model=model,
        tools=[calculator],
        instructions="산술 계산에는 calculator 도구를 사용하세요.",
        output_type=CalculationAnswer if structured else None,
    )
    result = await agent.run(prompt)

    for event in result.context.events:
        for item in event.content:
            if isinstance(item, Message):
                print(f"[{item.role}] {item.content}")
            elif isinstance(item, ToolCall):
                print(f"[think] {item.name}({item.arguments})")
            elif isinstance(item, ToolResult):
                print(f"[act → observe] {item.name} ({item.status}) → {item.content[0]}")

    print(f"실행 단계: {result.context.current_step}")
    if isinstance(result.output, CalculationAnswer):
        print(result.output.model_dump_json(indent=2))
    elif result.output is None:
        print("최대 단계에 도달했습니다. 최종 응답이 없습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", help="실제 모델에 보낼 질문")
    parser.add_argument("--model", help="LiteLLM에 전달할 모델 이름")
    parser.add_argument("--structured", action="store_true", help="4.7절 구조화 응답")
    args = parser.parse_args()

    if args.prompt is not None and args.model is None:
        parser.error("직접 입력한 질문을 사용하려면 --model을 지정하세요.")

    try:
        asyncio.run(run(args.prompt or DEFAULT_PROMPT, args.model, args.structured))
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
