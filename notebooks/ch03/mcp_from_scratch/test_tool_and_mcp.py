"""직접 Tool 호출의 SDK 메시지와 두 실행 경로의 순서를 검증한다."""

from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.error import HTTPError

import httpx
from openai import AsyncOpenAI

import server
import tool_and_mcp


class DirectToolTests(unittest.IsolatedAsyncioTestCase):
    async def run_direct(self, search, tool_name="tavily_search"):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            message = (
                {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call_search_1", "type": "function",
                    "function": {"name": tool_name,
                                 "arguments": '{"query":"MCP tools","max_results":3}'},
                }]}
                if len(requests) == 1 else
                {"role": "assistant", "content": "MCP 설명 https://example.com"}
            )
            return httpx.Response(200, json={
                "id": "chat_1", "object": "chat.completion", "created": 0,
                "model": "test-model",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            })

        with patch.object(tool_and_mcp, "search_tavily", search):
            with redirect_stderr(io.StringIO()):
                async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
                    async with AsyncOpenAI(api_key="test-key", http_client=http) as openai:
                        answer = await tool_and_mcp.ask_direct(openai, "MCP 검색해줘", "test-model")
        return answer, requests

    async def test_sdk_tool_round_trip(self):
        results = [{"title": "MCP", "url": "https://example.com", "content": "설명"}]
        search = Mock(return_value=results)
        answer, requests = await self.run_direct(search)
        self.assertEqual(answer, "MCP 설명 https://example.com")
        search.assert_called_once_with({"query": "MCP tools", "max_results": 3})
        self.assertEqual(requests[0]["tool_choice"], "required")
        definition = requests[0]["tools"][0]["function"]
        self.assertEqual(definition["parameters"], server.SEARCH_TOOL["inputSchema"])
        history = requests[1]["messages"]
        self.assertEqual(history[2]["tool_calls"][0]["id"], history[3]["tool_call_id"])
        self.assertEqual(json.loads(history[3]["content"]), results)

    async def test_failed_search_never_returns_speculative_answer(self):
        def fail(arguments):
            raise HTTPError("https://api.tavily.com/search", 401, "Unauthorized", {}, None)

        with self.assertRaisesRegex(RuntimeError, "Tavily HTTP error: 401"):
            await self.run_direct(fail)

    async def test_unknown_tool_is_not_executed(self):
        search = Mock()
        with self.assertRaisesRegex(RuntimeError, "알 수 없는 도구"):
            await self.run_direct(search, tool_name="unknown_tool")
        search.assert_not_called()

    async def test_missing_tool_call_is_rejected(self):
        openai = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(tool_calls=None, content="추측 답변")),
            ])),
        )))
        with self.assertRaisesRegex(RuntimeError, "검색 도구를 호출하지"):
            await tool_and_mcp.ask_direct(openai, "MCP 검색해줘", "test-model")


class EntryPointTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_then_mcp_with_same_question_and_model(self):
        events = []
        mcp = object()

        async def direct(openai, question, model):
            events.append(("direct", question, model))
            return "직접 검색 답변"

        @asynccontextmanager
        async def connect():
            events.append(("connect",))
            yield mcp
            events.append(("close",))

        async def ask(openai, connection, question, model):
            self.assertIs(connection, mcp)
            events.append(("mcp", question, model))
            return "MCP 검색 답변"

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key", "TAVILY_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
        }), patch.object(tool_and_mcp, "load_environment"):
            with patch("sys.argv", ["tool_and_mcp.py", "MCP tools"]):
                with patch.object(tool_and_mcp, "ask_direct", direct), \
                     patch.object(tool_and_mcp, "connect", connect), \
                     patch.object(tool_and_mcp, "ask", ask):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        await tool_and_mcp.main()
        self.assertEqual(events, [
            ("direct", "MCP tools", "test-model"), ("connect",),
            ("mcp", "MCP tools", "test-model"), ("close",),
        ])
        self.assertIn("직접 검색 답변", output.getvalue())
        self.assertIn("MCP 검색 답변", output.getvalue())


if __name__ == "__main__":
    unittest.main()
