"""OpenAI Responses API 도구 호출을 JSON으로 관찰하는 학습용 에이전트."""

import argparse
from copy import deepcopy
from datetime import datetime
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_QUESTION = "19,800원짜리 책 3권의 합계를 구하고, 그 결과에 10% 할인을 적용해줘. 각 계산에 도구를 사용해줘."
DEFAULT_LOG_DIR = Path(__file__).resolve().with_name("log")
TOOLS = [
    {
        "type": "function",
        "name": "calculator",
        "description": "두 수의 사칙연산을 수행합니다. 계산이 필요할 때 사용하세요.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                },
                "a": {"type": "number", "description": "첫 번째 수"},
                "b": {"type": "number", "description": "두 번째 수"},
            },
            "required": ["operation", "a", "b"],
            "additionalProperties": False,
        },
    }
]


def load_settings():
    # 실행 위치에 관계없이 이 저장소 루트의 .env를 읽습니다.
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env", override=False)
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError(f"{root / '.env'}에 OPENAI_API_KEY를 설정하세요.")
    return os.getenv("OPENAI_MODEL") or "gpt-6-luna"


def calculator(operation, a, b):
    # strict 스키마와 별개로, 실제 실행 경계에서도 입력을 검사합니다.
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in (a, b)):
        raise ValueError("a와 b는 유한한 숫자여야 합니다.")
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("0으로 나눌 수 없습니다.")
        result = a / b
    else:
        raise ValueError(f"지원하지 않는 연산: {operation}")
    if not math.isfinite(result):
        raise ValueError("계산 결과가 유한한 숫자 범위를 벗어났습니다.")
    return {"operation": operation, "a": a, "b": b, "result": result}


def execute_tool(name, arguments):
    # 모델이 보낸 이름을 임의 코드로 실행하지 않고 허용한 함수만 실행합니다.
    try:
        if name != "calculator":
            raise ValueError(f"등록되지 않은 도구: {name}")
        if not isinstance(arguments, dict):
            raise ValueError("인자는 JSON 객체여야 합니다.")
        return {"ok": True, **calculator(**arguments)}
    except (TypeError, ValueError, OverflowError) as exc:
        return {"ok": False, "error": str(exc)}


def run_agent(client, question, model, log_dir=DEFAULT_LOG_DIR, max_turns=8):
    """모델 → 함수 실행 → 결과 전달을 반복하고 답변과 전체 기록을 반환합니다."""
    if max_turns < 1:
        raise ValueError("max_turns는 1 이상이어야 합니다.")
    # 실행마다 한국 시간(KST) 기준 폴더를 생성합니다. 소수점 이하는 마이크로초입니다.
    timestamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d_%H-%M-%S.%f_KST")
    run_dir = Path(log_dir).resolve() / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"JSON 저장 폴더: {run_dir}", flush=True)
    history = [{"role": "user", "content": question}]
    events = []

    def show(kind, data, turn):
        # history가 다음 단계에서 변경되어도 이전 요청 기록은 유지합니다.
        event = deepcopy({"turn": turn, "kind": kind, "data": data})
        events.append(event)
        print(f"\n--- {turn}단계 / {kind} ---", flush=True)
        print(json.dumps(event["data"], ensure_ascii=False, indent=2, allow_nan=False))
        # 파일 순번과 종류는 파일명에만 표시하고 본문에는 해당 JSON만 저장합니다.
        path = run_dir / f"{len(events):03d}_{kind}.json"
        path.write_text(
            json.dumps(event["data"], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    for turn in range(1, max_turns + 1):
        request = {
            "model": model,
            "instructions": (
                "한국어로 답하세요. 계산은 반드시 calculator로 수행하세요. "
                "이전 계산 결과가 필요하면 결과를 받은 뒤 다음 도구를 호출하세요. "
                "도구 결과의 오류를 확인하고, 충분한 결과를 얻으면 최종 답변을 하세요."
            ),
            "input": history,
            "tools": TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "store": False,
            # 추론 모델을 선택해도 다음 요청에 필요한 추론 항목을 보존합니다.
            "include": ["reasoning.encrypted_content"],
        }
        show("request", request, turn)
        response = client.responses.create(**request)
        show("response", response.model_dump(mode="json"), turn)

        if response.status != "completed":
            raise RuntimeError(f"응답이 완료되지 않았습니다: {response.status}")

        # 함수 호출 외에 reasoning 등 다른 출력 항목도 함께 보존합니다.
        history.extend(item.model_dump(mode="json") for item in response.output)
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not response.output_text:
                raise RuntimeError("도구 호출이나 최종 답변이 없습니다. response JSON을 확인하세요.")
            return response.output_text, events

        for call in calls:
            try:
                # arguments는 JSON 객체가 아니라 JSON을 담은 문자열입니다.
                arguments = json.loads(call.arguments)
            except (json.JSONDecodeError, TypeError) as exc:
                result = {"ok": False, "error": f"도구 인자 JSON 파싱 실패: {exc}"}
            else:
                result = execute_tool(call.name, arguments)

            tool_output = {
                "type": "function_call_output",
                # item.id가 아닌 call_id로 모델의 호출과 실행 결과를 연결합니다.
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False, allow_nan=False),
            }
            history.append(tool_output)

    raise RuntimeError(f"{max_turns}회 제한에 도달했습니다. JSON 기록을 확인하세요.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--model", help="OPENAI_MODEL 환경변수보다 우선 적용")
    parser.add_argument(
        "--log-dir", type=Path, default=DEFAULT_LOG_DIR,
        help="실행 시각별 JSON 폴더를 생성할 위치 (기본: 예제 폴더의 log/)",
    )
    args = parser.parse_args()
    model = load_settings()
    with OpenAI(timeout=60, max_retries=0) as client:
        run_agent(client, args.question, args.model or model, args.log_dir)


if __name__ == "__main__":
    main()
