# OpenAI SDK + Tavily로 MCP 직접 구현하기

학습용으로 MCP 서버와 클라이언트를 직접 구현한 예제입니다. 실행에 필요한 외부
패키지는 `openai`와 `.env` 로딩용 `python-dotenv`입니다.
Tavily는 `urllib.request`로 REST API를 호출합니다.
Python 3.11 이상이 필요합니다.

```text
사용자 질문
  → client.py → OpenAI Responses API (어떤 도구를 쓸지 결정)
  ← function_call(name, arguments, call_id)
  → server.py (stdio JSON-RPC의 tools/call)
  → Tavily Search REST API
  ← 검색 결과 (MCP의 content)
  → OpenAI Responses API (function_call_output)
  ← 출처를 포함한 최종 답변
```

OpenAI SDK는 모델 요청을 담당합니다. MCP 통신과 도구 실행은 우리가 작성한 코드가
담당합니다. 모델이 직접 파이썬 함수를 실행하는 것이 아닙니다.

## 실행

아래 명령은 `notebooks/ch03`에서 실행합니다. 이 저장소의 가상 환경에 OpenAI SDK가
와 `python-dotenv`가 이미 있으면 설치 단계는 생략할 수 있습니다.

```bash
python3 -m venv mcp_from_scratch/.venv
source mcp_from_scratch/.venv/bin/activate
python -m pip install openai python-dotenv

# 저장소 루트의 .env에 아래 값을 설정합니다.
# OPENAI_API_KEY=your-openai-api-key
# TAVILY_API_KEY=your-tavily-api-key
# OPENAI_MODEL=gpt-4.1-mini  # 선택: 계정에서 사용 가능한 모델

python mcp_from_scratch/client.py 'MCP의 tools/list와 tools/call 차이를 검색해서 설명해줘'
```

실행 시 예제 폴더부터 상위로 올라가며 가장 가까운 `.env`를 자동으로 읽습니다.
따라서 저장소 루트의 기존 `.env`를 사용할 수 있으며, 실행하는 작업 디렉터리와
무관하게 같은 탐색 규칙을 사용합니다. 이미 셸에 설정된 환경 변수는 우선합니다.
로드한 키는 서버 프로세스에도 환경 변수로 전달됩니다.
전체 실행은 OpenAI와 Tavily의 API를
사용하므로 각 서비스의 사용량이 발생합니다. 실제 JSON 메시지와 검색 결과는
터미널의 stderr에, 최종 답변은 stdout에 출력됩니다. 요청 헤더와 API 키는 출력하지
않지만, 검색어와 검색 결과가 로그에 포함됩니다.

다음 순서로 나누어 실행하면 경계를 이해하기 쉽습니다.

```bash
# 1. 키와 OpenAI 패키지 없이: 초기화, 준비 알림, 도구 목록 확인
python3 mcp_from_scratch/client.py --inspect

# 2. Tavily 키만 필요: 모델 없이 MCP 도구를 직접 호출
python3 mcp_from_scratch/client.py --search-only 'Model Context Protocol'

# 3. 두 키 필요: 모델이 검색 도구를 선택하고 결과를 읽어 답변
python3 mcp_from_scratch/client.py 'MCP가 무엇인지 검색해서 알려줘'
```

## 직접 Tool 호출과 MCP 호출을 한 번에 비교

`tool_and_mcp.py` 하나를 실행하면 같은 질문으로 다음 두 경로를 차례로 실행합니다.

1. **직접 Tool 호출**: Chat Completions의 `tool_calls`를 받아 `search_tavily()`를
   직접 실행하고, `role="tool"` 결과를 `tool_call_id`로 연결해 최종 답변을 받습니다.
2. **MCP 호출**: 기존 `client.py`로 서버를 초기화하고 도구를 발견한 뒤,
   `tools/call`로 같은 검색 함수를 서버에서 실행합니다. 결과는 Responses API의
   `function_call_output`으로 전달합니다.

```powershell
# 저장소 루트에서 Windows 가상 환경의 Python으로 실행
.\.venv\Scripts\python.exe -X utf8 notebooks\ch03\mcp_from_scratch\tool_and_mcp.py "MCP tools를 검색하고 출처와 함께 설명해줘."
```

기존 `client.py`와 `server.py`를 재사용하는 단일 실행 파일입니다. 두 API 키와
기존 의존성만 필요하며 `.env` 탐색 규칙도 같습니다. 두 경로 모두 실제 검색과
모델 API를 호출하므로 각각 사용량이 발생합니다. 도구 요청과 결과는 stderr,
두 최종 답변은 stdout으로 출력합니다. 검색 결과와 모델 답변은 실행마다 달라질
수 있으며 두 답변이 같아야 하는 것은 아닙니다. 직접 호출도 최대 6번의 모델
요청으로 제한하고, 모든 검색이 실패하면 추측성 답변 대신 오류로 종료합니다.

## 코드를 읽는 순서

1. `server.py`의 `SEARCH_TOOL`: 도구 이름, 설명, 입력 JSON Schema.
2. `server.py`의 `search_tavily()`: 평범한 HTTP 요청. MCP와 무관한 검색 로직.
3. `server.py`의 `main()`과 `dispatch()`: 초기화 상태 관리와 JSON-RPC 메서드 분기.
4. `client.py`의 `connect()`와 `MCPClient.request()`: 서버 프로세스 실행과 통신.
5. `client.py`의 `to_openai_tool()`과 `ask()`: 스키마 변환과 모델 도구 호출 루프.

## 실제로 오가는 메시지

stdio에서는 JSON 객체 하나를 **한 줄**로 보내고 끝에 개행을 붙입니다.
서버 stdout에 일반 `print()` 로그가 섞이면 프로토콜이 깨집니다.

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"learning-client","version":"0.1.0"}}}
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"tavily-from-scratch","version":"0.1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

`tools/list` 결과에서 받은 `inputSchema`를 OpenAI의 `parameters`에 넣습니다.
OpenAI의 Responses API는 함수 정의를 다음처럼 받습니다.

```python
{
    "type": "function",
    "name": tool["name"],
    "description": tool["description"],
    "parameters": tool["inputSchema"],
    "strict": True,
}
```

이 예제는 모든 입력 필드를 필수로 선언하고 `additionalProperties: false`를 넣어
strict 모드에 맞춥니다. 임의의 MCP 서버 스키마가 항상 OpenAI strict 모드에
호환되는 것은 아니므로 이 변환 함수는 이 예제 서버를 대상으로 합니다.

모델이 반환한 `function_call`을 받으면 클라이언트가 다음 요청을 만듭니다.

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"tavily_search","arguments":{"query":"Model Context Protocol","max_results":3}}}
```

서버 응답은 `result.content`에 텍스트 블록을 담습니다. 클라이언트는 이 결과를
문자열로 직렬화해서 OpenAI의 `function_call_output.output`에 넣습니다.
**MCP의 `id`**는 JSON-RPC 요청과 응답을, **OpenAI의 `call_id`**는 모델의 도구 호출과
실행 결과를 연결합니다. 두 ID는 서로 다른 역할을 합니다.

잘못된 메서드 등 통신 오류는 JSON-RPC `error`로 반환합니다. 검색 실패나 잘못된
검색 인자는 `result.isError: true`로 반환하므로 모델도 실패를 보고 다시 검색할 수 있습니다.
Tavily의 일시적인 HTTP 오류(429, 500, 502, 503, 504)는 서버에서 최대 2번 재시도하며,
대기 시간을 포함한 재시도 예산은 35초입니다. 인증 오류(401 등)는 재시도하지 않습니다.
모든 검색이 실패하면 클라이언트는 추측성 답변 대신 원래 검색 오류를 포함한 예외로
종료합니다. 이 예제에서 별도 맥락 없이 질문하는 MCP는 Model Context Protocol을 뜻합니다.
서버는 UTF-8 모드로 실행하므로 Windows에서도 한글 JSON 메시지를 주고받을 수 있습니다.
첫 모델 요청은 `tool_choice="required"`로 검색을 요청하고, 이후에는 모델이 추가
검색 여부를 결정합니다. 총 모델 요청은 최대 6번이며 마지막에는 최종 답변을 요청합니다.

## 검증과 범위

```bash
cd mcp_from_scratch
python -m unittest -v
```

테스트는 키 없이 동작합니다. 실제 서버 프로세스를 띄워 초기화와 도구 호출을 검증하고,
Tavily HTTP 응답 및 OpenAI HTTP 응답만 대체합니다. 따라서 외부 API의 실제 검색
성공이나 모델의 답변 품질까지 검증하는 것은 아닙니다.

이 코드는 handshake를 학습하기 위해 MCP **2025-11-25**에 고정한 최소 구현입니다.
최신 프로토콜 전체 구현이나 범용 MCP 클라이언트가 아닙니다. stdio, 텍스트 검색 도구
하나, 순차 요청만 다룹니다. HTTP 전송, 취소, 페이지네이션, resources/prompts 등은
구현하지 않습니다. 기존 챕터 노트북과 독립적으로 실행할 수 있습니다.

공식 참고 자료:

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [MCP lifecycle (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
