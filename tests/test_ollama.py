import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from kiloframe.ollama import OllamaClient, OllamaConfig, OllamaError


class OllamaProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_tool_calls_keep_distinct_indices(self):
        calls = [{"function": {"name": name, "arguments": {"path": name}}}
                 for name in ("read_file", "list_files")]
        response = io.BytesIO((json.dumps({"message": {"tool_calls": calls}})
                               + '\n{"done":true}\n').encode())
        with patch("urllib.request.urlopen", return_value=response):
            events = [e async for e in OllamaClient("http://localhost:11434").chat_stream("test", [])]
        converted = [c for e in events for c in e.get("delta", {}).get("tool_calls", [])]
        self.assertEqual([c["index"] for c in converted], [0, 1])
        self.assertEqual([c["function"]["name"] for c in converted], ["read_file", "list_files"])

    async def test_tool_history_is_converted_to_native_ollama_format(self):
        captured = []
        def open_request(request, **kwargs):
            captured.append(json.loads(request.data))
            return io.BytesIO(b'{"done":true}\n')
        messages = [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-1", "type": "function", "function": {
                "name": "read_file", "arguments": '{"path":"a"}'}}]},
            {"role": "tool", "name": "read_file", "tool_call_id": "call-1", "content": "text"}]
        with patch("urllib.request.urlopen", side_effect=open_request):
            _ = [e async for e in OllamaClient("http://localhost:11434").chat_stream("test", messages)]
        self.assertEqual(captured[0]["messages"][0]["tool_calls"][0]["function"]["arguments"], {"path": "a"})
        self.assertEqual(captured[0]["messages"][1]["tool_name"], "read_file")
        self.assertEqual(messages[0]["tool_calls"][0]["function"]["arguments"], '{"path":"a"}')

    async def test_pull_uses_timeout_keyword_and_requires_success(self):
        def open_request(request, data=None, *, timeout=None):
            self.assertIsNone(data, "timeout must not overwrite the request body")
            self.assertEqual(timeout, 30)
            return io.BytesIO(b'{"status":"pulling manifest"}\n')
        with patch("urllib.request.urlopen", side_effect=open_request):
            with self.assertRaises(OllamaError):
                _ = [s async for s in OllamaClient("http://localhost:11434").pull("test")]

    async def test_chat_truncation_is_failure_not_completed_answer(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"message":{"content":"partial"}}\n')):
            with self.assertRaises(OllamaError):
                _ = [e async for e in OllamaClient("http://localhost:11434").chat_stream("test", [])]


class OllamaConfigurationTests(unittest.TestCase):
    def test_invalid_server_does_not_overwrite_existing_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ollama.json"
            config = OllamaConfig(path)
            config.add_server("local", "http://127.0.0.1:11434")
            before = path.read_bytes()
            with self.assertRaises((ValueError, OllamaError)):
                config.add_server("broken", "file:///etc/passwd")
            self.assertEqual(path.read_bytes(), before)

    def test_updating_server_preserves_selected_model(self):
        with tempfile.TemporaryDirectory() as directory:
            config = OllamaConfig(Path(directory) / "ollama.json")
            config.add_server("local", "http://127.0.0.1:11434")
            config.set_model("local", "llama3.2")
            config.add_server("local", "http://127.0.0.1:11434")
            self.assertEqual(config.active().model, "llama3.2")

    def test_unreachable_version_raises(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with self.assertRaises(OllamaError):
                OllamaClient("http://localhost:11434").version()
