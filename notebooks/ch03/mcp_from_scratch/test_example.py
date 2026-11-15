"""외부 API를 호출하지 않고 실제 stdio와 OpenAI SDK 직렬화를 검증한다."""

from contextlib import redirect_stderr
import io
import json
import os
import unittest
from unittest.mock import patch

import client
import server


class SearchTests(unittest.TestCase):
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
                        answer = await client.ask(openai, mcp, "MCP 검색해줘", "test-model")
        self.assertIn("검색하지 못했습니다", answer)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["tools"][0]["parameters"], server.SEARCH_TOOL["inputSchema"])
        history = requests[1]["input"]
        self.assertEqual(history[1]["type"], "function_call")
        self.assertEqual(history[2]["call_id"], "call_1")
        self.assertTrue(json.loads(history[2]["output"])["isError"])


if __name__ == "__main__":
    unittest.main()
