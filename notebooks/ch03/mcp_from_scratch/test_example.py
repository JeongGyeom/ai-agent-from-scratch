"""외부 API를 호출하지 않고 실제 stdio와 OpenAI SDK 직렬화를 검증한다."""

from contextlib import redirect_stderr
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError

import client
import server


class SearchTests(unittest.TestCase):
    def test_transient_http_error_is_retried(self):
        response = io.StringIO('{"results": []}')
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch.object(server, "urlopen") as urlopen, patch.object(server.time, "sleep") as sleep:
                urlopen.side_effect = [HTTPError("https://api.tavily.com/search", 500,
                                                "Server error", {}, None),
                                       urlopen.return_value]
                urlopen.return_value.__enter__.return_value = response
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(server.search_tavily({"query": "MCP", "max_results": 2}), [])
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_http_error_retry_limit_and_authentication_errors(self):
        for status, expected_attempts in ((500, 3), (429, 3), (401, 1)):
            with self.subTest(status=status), patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
                with patch.object(server, "urlopen") as urlopen, patch.object(server.time, "sleep"):
                    urlopen.side_effect = HTTPError("https://api.tavily.com/search", status,
                                                   "Error", {}, None)
                    with redirect_stderr(io.StringIO()):
                        result = server.dispatch("tools/call", {
                            "name": "tavily_search", "arguments": {"query": "MCP", "max_results": 2},
                        })
            self.assertEqual(urlopen.call_count, expected_attempts)
            self.assertEqual(result, server.tool_result(f"Tavily HTTP error: {status}", True))

    def test_tavily_request_and_result(self):
        payload = {"results": [{"title": "MCP", "url": "https://example.com", "content": "설명"}]}
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch.object(server, "urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = io.StringIO(json.dumps(payload))
                result = server.search_tavily({"query": "MCP", "max_results": 2})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.tavily.com/search")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(request.data)["max_results"], 2)
        self.assertEqual(result, payload["results"])

    def test_invalid_arguments_never_call_tavily(self):
        for arguments in ({"query": "", "max_results": 2},
                          {"query": "MCP", "max_results": True},
                          {"query": "MCP", "max_results": 6},
                          {"query": "MCP"}):
            with self.subTest(arguments=arguments), patch.object(server, "urlopen") as urlopen:
                result = server.dispatch("tools/call", {"name": "tavily_search", "arguments": arguments})
                self.assertTrue(result["isError"])
                urlopen.assert_not_called()


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_lifecycle_and_errors(self):
        # 자식 프로세스에도 API 키가 전달되지 않아 네트워크 호출이 일어나지 않는다.
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}), redirect_stderr(io.StringIO()):
            async with client.connect() as mcp:
                self.assertEqual(await mcp.request("ping"), {})
                tools = await mcp.request("tools/list")
                self.assertEqual(tools["tools"][0]["name"], "tavily_search")
                result = await mcp.request("tools/call", {
                    "name": "tavily_search", "arguments": {"query": "MCP", "max_results": 2},
                })
                self.assertTrue(result["isError"])
                self.assertIn("TAVILY_API_KEY", result["content"][0]["text"])
                with self.assertRaisesRegex(RuntimeError, "-32601"):
                    await mcp.request("unknown_method")
            self.assertEqual(mcp.process.returncode, 0)

    async def test_openai_sdk_to_mcp_round_trip(self):
        import httpx
        from openai import AsyncOpenAI

        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) == 1:
                output = [{"type": "function_call", "id": "fc_1", "call_id": "call_1",
                           "name": "tavily_search", "arguments": '{"query":"MCP","max_results":2}',
                           "status": "completed"}]
            else:
                output = [{"type": "message", "id": "msg_1", "role": "assistant",
                           "status": "completed", "content": [{"type": "output_text",
                           "text": "검색 키가 없어 검색하지 못했습니다.", "annotations": []}]}]
            return httpx.Response(200, json={
                "id": "resp_1", "object": "response", "created_at": 0,
                "model": "test-model", "status": "completed", "output": output,
            })

        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}), redirect_stderr(io.StringIO()):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
                async with AsyncOpenAI(api_key="test-key", http_client=http) as openai:
                    # SDK 2.x의 OS 감지용 백그라운드 스레드를 샌드박스 테스트에서 생략한다.
                    openai._platform = "Linux"
                    async with client.connect() as mcp:
                        with self.assertRaisesRegex(RuntimeError, "TAVILY_API_KEY"):
                            await client.ask(openai, mcp, "MCP 검색해줘", "test-model")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["tools"][0]["parameters"], server.SEARCH_TOOL["inputSchema"])
        history = requests[1]["input"]
        self.assertEqual(history[1]["type"], "function_call")
        self.assertEqual(history[2]["call_id"], "call_1")
        self.assertTrue(json.loads(history[2]["output"])["isError"])

    async def test_successful_search_returns_model_answer(self):
        call = SimpleNamespace(type="function_call", name="tavily_search",
                               arguments='{"query":"Model Context Protocol","max_results":2}',
                               call_id="call_1")
        openai = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(side_effect=[
            SimpleNamespace(output=[call]),
            SimpleNamespace(output=[], output_text="MCP 설명 https://example.com"),
        ])))
        mcp = SimpleNamespace(request=AsyncMock(side_effect=[
            {"tools": [server.SEARCH_TOOL]},
            server.tool_result('[{"url":"https://example.com","content":"MCP 설명"}]'),
        ]))
        self.assertEqual(await client.ask(openai, mcp, "MCP 검색해줘", "test-model"),
                         "MCP 설명 https://example.com")

    async def test_failed_search_does_not_return_speculative_answer(self):
        call = SimpleNamespace(type="function_call", name="tavily_search",
                               arguments='{"query":"MCP","max_results":2}', call_id="call_1")
        openai = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(side_effect=[
            SimpleNamespace(output=[call]),
            SimpleNamespace(output=[], output_text="MCP는 Microsoft Certified Professional입니다."),
        ])))
        mcp = SimpleNamespace(request=AsyncMock(side_effect=[
            {"tools": [server.SEARCH_TOOL]},
            server.tool_result("Tavily HTTP error: 500", True),
        ]))
        with self.assertRaisesRegex(RuntimeError, "Tavily HTTP error: 500"):
            await client.ask(openai, mcp, "MCP 검색해줘", "test-model")

    async def test_model_can_recover_from_failed_search(self):
        call = SimpleNamespace(type="function_call", name="tavily_search",
                               arguments='{"query":"MCP","max_results":2}', call_id="call_1")
        openai = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(side_effect=[
            SimpleNamespace(output=[call]),
            SimpleNamespace(output=[call]),
            SimpleNamespace(output=[], output_text="MCP 설명 https://example.com"),
        ])))
        mcp = SimpleNamespace(request=AsyncMock(side_effect=[
            {"tools": [server.SEARCH_TOOL]},
            server.tool_result("Tavily HTTP error: 500", True),
            server.tool_result('[{"url":"https://example.com","content":"MCP 설명"}]'),
        ]))
        self.assertEqual(await client.ask(openai, mcp, "MCP 검색해줘", "test-model"),
                         "MCP 설명 https://example.com")


if __name__ == "__main__":
    unittest.main()
