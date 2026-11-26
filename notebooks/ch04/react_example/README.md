# 4장 ReAct 파이썬 예제

계산 질문 하나를 가지고 모델 호출(Think), 도구 실행(Act), 도구 결과 전달(Observe), 최종 응답까지 따라간다. 기본 실행은 정해진 응답을 내는 데모 모델을 사용한다. 계산기 실행과 이벤트 기록, 다음 요청에 도구 결과를 넣는 과정은 실제 모델 연결 때와 같다.

## 폴더에서 실행하기

이 폴더를 복사해도 아래 명령으로 실행할 수 있다. 프로젝트와 같은 Python 3.13 환경을 기준으로 한다.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python main.py --structured
```

기본 실행에서는 모델이 `calculator` 호출을 요청하고 Python이 `7006652`를 계산한다. 다음 단계에서 모델이 도구 결과를 읽고 최종 문장을 반환한다. `--structured`를 붙이면 두 번째 단계에서 모델이 `final_answer` 도구를 호출하고, 에이전트가 결과를 `CalculationAnswer`로 검증해 JSON으로 출력한다(4.7절).

실제 모델로 질문하려면 공급자 API 키를 셸 환경 변수에 설정하고 아래처럼 실행한다. 이 예제의 키 변수는 `OPENAI_API_KEY`다.

```sh
python -m pip install -r requirements-live.txt
python main.py --model gpt-5.4-mini "37 곱하기 48은 얼마야?"
```

## 코드 읽는 순서

| 파일 | 읽어 볼 부분 |
| --- | --- |
| `main.py` | 도구 등록과 실행, 데모 모델이 읽는 메시지, 이벤트 출력 |
| `react_agent/agent.py` | `run()`이 반복하고, `step()`에서 `think()`와 `act()`를 실행하는 과정 |
| `react_agent/context.py`, `types.py` | `Message`, `ToolCall`, `ToolResult`를 `Event`에 담아 보관하는 방식 |
| `react_agent/llm.py` | `build_messages()`가 이력을 API 형식으로 바꾸고, `LlmClient`가 응답을 파싱하는 방식 |
| `react_agent/calculator.py`, `base.py`, `tool_schema.py` | `@tool`이 함수를 감싸고 타입 힌트로 도구 스키마를 만드는 방식 |

`agent.py`, `context.py`, `base.py`는 4장 구현에서 가져왔다. 메시지 타입, LLM 연결, 도구 스키마, 계산기는 `scratch_agents`에서 필요한 부분을 옮겼다. 모든 내부 import는 이 폴더의 로컬 패키지를 가리킨다.
