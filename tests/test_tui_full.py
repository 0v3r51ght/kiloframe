import asyncio
import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    from prompt_toolkit.document import Document
    from kiloframe.tui_full import KiloApp, STYLE as TUI_STYLE, _ChatLexer
except ModuleNotFoundError as exc:
    if exc.name != "prompt_toolkit":
        raise
    KiloApp = None
    Document = None


@unittest.skipIf(KiloApp is None, "prompt_toolkit is not installed in the raw source-test environment")
class FullTUIDirectChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_switch_uses_persisted_cloud_default_on_fresh_tui(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        app.client.request = AsyncMock(side_effect=[
            {"default": "groq"},
            {"model": "llama", "server": "cloud", "state": "ready"},
        ])
        await app._switch_route()
        self.assertTrue(app.cloud_active)
        self.assertEqual(app.cloud_provider, "groq")
        self.assertIn("switched to cloud · groq", app.output.buffer.text)

    async def test_local_load_calls_dedicated_rpc(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        app.client.request = AsyncMock(return_value={"ok": True, "model": "small:latest"})
        app._spawn = lambda coroutine: coroutine.close()
        await app._local_load("small:latest")
        self.assertEqual(app.client.request.await_args.kwargs, {"model": "small:latest"})
        self.assertIn("loaded small:latest", app.output.buffer.text)
    async def test_direct_local_select_accepts_number_from_displayed_model_list(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        app.app = SimpleNamespace(invalidate=lambda: None)
        app.client.request = AsyncMock(side_effect=[
            [
                {"name": "large:latest"},
                {"name": "small:latest"},
            ],
            {"ok": True, "model": "small:latest", "server": "test"},
            {"model": "small:latest", "server": "test", "state": "ready"},
        ])

        await app._local_select("2")

        self.assertIn("selected small:latest", app.output.buffer.text)
        self.assertEqual(
            app.client.request.await_args_list[1].kwargs,
            {"model": "small:latest"},
        )

    def test_command_panel_is_a_closed_readable_box(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        with patch("shutil.get_terminal_size", return_value=SimpleNamespace(columns=100, lines=30)):
            app._command_panel("Help", ["/local status", "/thinking on"])
        rendered = app.output.buffer.text
        self.assertIn("╭─ Help ", rendered)
        self.assertIn("│ /local status", rendered)
        self.assertIn("│ /thinking on", rendered)
        self.assertTrue(rendered.rstrip().endswith("╯"))

    def test_command_panel_wraps_at_word_boundaries(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        with patch("shutil.get_terminal_size", return_value=SimpleNamespace(columns=70, lines=30)):
            app._command_panel(
                "Commands",
                ["/agent             orchestrator research coding security math engineering systems private"],
            )
        rendered = app.output.buffer.text
        self.assertIn("engineering", rendered)
        self.assertNotIn("engin\neering", rendered)

    def test_narrow_header_keeps_the_wordmark_without_status_text_overwriting_it(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        with patch("shutil.get_terminal_size", return_value=SimpleNamespace(columns=80, lines=24)):
            text = "".join(value for _style, value in app._banner_text()).splitlines()[0]
        self.assertIn("██╗", text)
        self.assertNotIn("KILOFRAME  ", text)

    def test_credit_is_aligned_to_the_left_edge_of_the_wordmark(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        with patch("shutil.get_terminal_size", return_value=SimpleNamespace(columns=120, lines=36)):
            lines = "".join(value for _style, value in app._banner_text()).splitlines()
        self.assertEqual(lines[-1], "  Developed by Citadel Research")

    def test_unloaded_selected_model_is_not_labelled_ready(self):
        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        app.status = {"healthy": True, "model": "small:latest"}
        app._ollama_running = []
        rendered = "".join(value for _style, value in app._stats_bar())
        self.assertIn("model selected · not loaded", rendered)
        self.assertNotIn("model ready", rendered)
    def test_python_fence_receives_language_aware_syntax_styles(self):
        document = Document(
            "\u2502 ```python                         \u2502\n"
            "\u2502 def greet(name): return f'Hi {name}' \u2502\n"
            "\u2502 ```                               \u2502"
        )
        fragments = _ChatLexer().lex_document(document)(1)
        styles = {style for style, value in fragments if value.strip()}
        self.assertIn("class:pygments.keyword", styles)
        self.assertIn("class:pygments.name.function", styles)
        self.assertTrue(any(style.startswith("class:pygments.literal.string") for style in styles))
        keyword = TUI_STYLE.get_attrs_for_style_str("class:pygments.keyword")
        function = TUI_STYLE.get_attrs_for_style_str("class:pygments.name.function")
        self.assertNotEqual(keyword.color, function.color)
        self.assertTrue(keyword.bold)
        self.assertEqual("".join(value for _style, value in fragments), document.lines[1])

    async def test_old_live_work_and_response_share_the_same_kilo_box(self):
        events = [
            {"type": "session", "session_id": "direct-chat"},
            {"type": "agent", "profile": "research"},
            {"type": "thinking"},
            {"type": "runtime_status", "text": "GPU memory exhausted; retrying on CPU"},
            {"type": "tool_start", "name": "web_search", "arguments": {"query": "Kilo"}},
            {"type": "tool_end", "name": "web_search", "ok": True, "summary": "2 results"},
            {"type": "tool_start", "name": "web_fetch", "arguments": {"url": "https://example.com"}},
            {"type": "tool_end", "name": "web_fetch", "ok": True, "summary": "source opened"},
            {"type": "thinking"},
            {"type": "token", "text": "Verified answer with source."},
            {"type": "done", "usage": {"total_tokens": 42}},
        ]
        reader = asyncio.StreamReader()
        for event in events:
            reader.feed_data((json.dumps(event) + "\n").encode())
        reader.feed_eof()

        class Writer:
            def write(self, data):
                self.request = data

            async def drain(self):
                pass

            def close(self):
                pass

        writer = Writer()

        async def connect(path):
            del path
            return reader, writer

        app = KiloApp(SimpleNamespace(socket_path=Path("/tmp/in-memory.sock")))
        app.app = SimpleNamespace(invalidate=lambda: None)
        with patch("asyncio.open_unix_connection", side_effect=connect):
                await app._ask("research Kilo")

        rendered = app.output.buffer.text
        self.assertEqual(rendered.count("╭─ Kilo "), 1)
        self.assertNotIn("Live work", rendered)
        self.assertIn("◇ orchestrator → research agent", rendered)
        self.assertIn("◈ web_search query=Kilo", rendered)
        self.assertIn("web_search", rendered)
        self.assertIn("web_fetch", rendered)
        self.assertIn("Verified answer", rendered)
        top = rendered.index("╭─ Kilo ")
        bottom = rendered.index("╰", top)
        for expected in ("research agent", "retrying on CPU", "web_search", "web_fetch", "Verified answer"):
            self.assertLess(top, rendered.index(expected))
            self.assertLess(rendered.index(expected), bottom)


if __name__ == "__main__":
    unittest.main()
