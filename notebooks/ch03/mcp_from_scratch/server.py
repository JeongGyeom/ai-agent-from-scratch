"""학습용 MCP stdio 서버. 외부 패키지 없이 Tavily REST API를 호출한다."""

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# 학습을 위해 handshake가 있는 이 버전으로 고정한다.
PROTOCOL_VERSION = "2025-11-25"
SEARCH_TOOL = {
    "name": "tavily_search",
    "description": "Search the web with Tavily for current information and source URLs.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "description": "Search query"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["query", "max_results"],
        "additionalProperties": False,
    },
}


def search_tavily(arguments):
    """JSON Schema를 선언해도 실행 시 검증은 서버의 책임이다."""
    if not isinstance(arguments, dict) or set(arguments) != {"query", "max_results"}:
        raise ValueError("query와 max_results만 전달해야 합니다.")
    query, count = arguments["query"], arguments["max_results"]
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query는 비어 있지 않은 문자열이어야 합니다.")
    if type(count) is not int or not 1 <= count <= 5:
        raise ValueError("max_results는 1~5의 정수여야 합니다.")
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 환경 변수가 필요합니다.")

    request = Request(
        "https://api.tavily.com/search",
        data=json.dumps({
            "query": query,
            "max_results": count,
            "search_depth": "basic",
            "include_raw_content": False,
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    deadline = time.monotonic() + 35
    for attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Tavily 검색 재시도 제한 시간이 초과되었습니다.")
        try:
            with urlopen(request, timeout=min(30, remaining)) as response:
                data = json.load(response)
            break
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            print(f"Tavily HTTP error: {exc.code}; retry {attempt + 1}/2",
                  file=sys.stderr)
            exc.close()
            time.sleep(min(2 ** attempt, max(0, deadline - time.monotonic())))
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""),
         "content": r.get("content", "")}
        for r in data.get("results", [])
    ]


def tool_result(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def dispatch(method, params):
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [SEARCH_TOOL]}
    if method == "tools/call":
        if params.get("name") != SEARCH_TOOL["name"]:
            raise LookupError("Unknown tool")
        try:
            results = search_tavily(params.get("arguments"))
            return tool_result(json.dumps(results, ensure_ascii=False))
        except HTTPError as exc:
            # API 키나 응답 본문을 로그/모델에 노출하지 않는다.
            return tool_result(f"Tavily HTTP error: {exc.code}", True)
        except (ValueError, URLError, TimeoutError) as exc:
            return tool_result(str(exc), True)
    raise LookupError("Method not found")


def send(message):
    # stdout은 프로토콜 전용. 일반 로그는 반드시 stderr로 보낸다.
    print(json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False), flush=True)


def main():
    initialized = False
    ready = False
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            send({"id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)):
            send({"id": None, "error": {"code": -32600, "message": "Invalid Request"}})
            continue

        method = message["method"]
        # Notification에는 id가 없으며 응답도 보내지 않는다.
        if "id" not in message:
            if method == "notifications/initialized" and initialized:
                ready = True
            continue
        request_id = message["id"]
        params = message.get("params", {})
        try:
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
            if method == "initialize":
                if initialized:
                    raise ValueError("Already initialized")
                if not all(k in params for k in ("protocolVersion", "capabilities", "clientInfo")):
                    raise ValueError("Missing initialization parameters")
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tavily-from-scratch", "version": "0.1.0"},
                }
                initialized = True
            elif not ready and method != "ping":
                raise ValueError("Initialize first")
            else:
                result = dispatch(method, params)
            send({"id": request_id, "result": result})
        except (ValueError, LookupError) as exc:
            code = -32602 if isinstance(exc, ValueError) else -32601
            send({"id": request_id, "error": {"code": code, "message": str(exc)}})
        except Exception:
            print("Unexpected server error", file=sys.stderr)
            send({"id": request_id, "error": {"code": -32603, "message": "Internal error"}})


if __name__ == "__main__":
    main()
