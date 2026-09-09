"""Fresh acceptance regressions for live rendering and real process visibility."""
import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from prompt_toolkit.application import Application
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from kiloframe.activity import running_processes
from kiloframe.tui_full import KiloApp

class Client:
    async def request(self, command, **kwargs):
        if command == "status":
            return {"healthy": True, "model": "own-model", "server": "http://ollama", "server_name": "test",
                    "processes": running_processes()}
        if command == "provider_info":
            return {"default": kwargs.get("name", "cloud"), "model": "remote-model"}
        if command == "ollama_running":
            return []
        return {}

class LiveUI(unittest.IsolatedAsyncioTestCase):
    async def test_each_partial_chunk_is_visible_once_and_final_text_is_not_duplicated(self):
        app = KiloApp(Client())
        app._open_box()
        for chunk in ("Hello", " from", " your", " model"):
            app._stream_boxed(chunk)
            self.assertIn("Hello", app.output.text)
        self.assertIn("Hello from your model", app.output.text)
        app._flush_boxed()
        self.assertEqual(app.output.text.count("Hello from your model"), 1)
        self.assertIsNone(app._preview_start)

    async def test_actual_render_follows_new_answer_with_input_focused(self):
        with create_pipe_input() as pipe:
            app = KiloApp(Client())
            app.app = Application(layout=app.layout, input=pipe, output=DummyOutput(),
                                  full_screen=True)
            runner = asyncio.create_task(app.app.run_async())
            try:
                await asyncio.sleep(.05)
                for n in range(90):
                    app._append(f"older transcript line {n}\n")
                app._append("LATEST RESPONSE VISIBLE\n")
                await asyncio.sleep(.15)
                info = app.output.window.render_info
                self.assertIsNotNone(info)
                self.assertGreater(app.output.window.vertical_scroll, 60)
                self.assertTrue(app.layout.has_focus(app.input))
                app._scroll_to(2)
                app._append("do not steal scroll\n")
                self.assertFalse(app._follow_output)
                self.assertEqual(app.output.buffer.document.cursor_position_row, 2)
                app._queue = asyncio.Queue()
                app._enqueue("new human question")
                self.assertTrue(app._follow_output)
                await asyncio.sleep(.1)
                self.assertGreater(app.output.window.vertical_scroll, 60)
            finally:
                app.app.exit()
                await runner

    async def test_boxed_reply_tracks_allocated_output_width(self):
        """A resized/split TUI must keep borders inside the output pane."""
        with create_pipe_input() as pipe:
            app = KiloApp(Client())
            app.app = Application(layout=app.layout, input=pipe, output=DummyOutput(),
                                  full_screen=True)
            runner = asyncio.create_task(app.app.run_async())
            try:
                await asyncio.sleep(.1)
                width = app.output.window.render_info.window_width
                app._open_box()
                app._stream_boxed("word " * 200)
                app._flush_boxed()
                lines = app.output.buffer.document.lines
                self.assertTrue(lines)
                self.assertLessEqual(max(len(line) for line in lines), width)
                self.assertTrue(all(line.startswith("│ ") or line.startswith(("╭", "╰", "│"))
                                    or len(line) <= width for line in lines))
            finally:
                app.app.exit()
                await runner

    async def test_cloud_state_is_independent_of_ollama_and_poll_uses_selected_provider(self):
        app = KiloApp(Client())
        app.status = {"healthy": False}
        app.cloud_active = True
        app.cloud_provider = "chosen"
        await app._refresh_model_label()
        self.assertEqual(app.model_name, "chosen:remote-model")
        self.assertNotIn("Ollama offline", app._route_state())
        self.assertIn("CLOUD INFERENCE", "".join(t for _,t in app._sidebar_text()))
        self.assertNotIn("background", "".join(t for _,t in app._stats_bar()))
        app.cloud_active = False
        self.assertEqual(app._route_state(), "Ollama offline")

    async def test_banner_columns_align_and_do_not_wrap(self):
        app = KiloApp(Client())
        app.model_name = "a" * 180
        app.server_name = "b" * 180
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((150,40))):
            lines = "".join(t for _,t in app._banner_text()).splitlines()
            self.assertTrue(all(len(line) <= 150 for line in lines))
            positions = [lines[i].find(label) for i,label in [(2,"model"),(3,"route"),(4,"work")]]
            self.assertEqual(len(set(positions)),1)

    async def test_sidebar_uses_ollama_destination_instead_of_internal_server_label(self):
        app = KiloApp(Client())
        app.status.update({"server": "http://192.168.1.172:11434", "server_name": "ceo-test"})
        text = "".join(value for _style, value in app._sidebar_text())
        self.assertIn("Ollama · 192.168.1.172", text)
        self.assertNotIn("ceo-test", text)

    async def test_real_child_process_appears_and_disappears(self):
        process = subprocess.Popen(["sleep","10"])
        try:
            self.assertIn(process.pid, {row["pid"] for row in running_processes()})
        finally:
            process.terminate()
            process.wait()
        self.assertNotIn(process.pid, {row["pid"] for row in running_processes()})
