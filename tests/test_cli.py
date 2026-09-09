import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kiloframe.cli import build_parser, print_status, runtime_summary, show_logs, uninstall_command


class CLITests(unittest.TestCase):
    def test_uninstall_is_a_top_level_command(self):
        args = build_parser().parse_args(["uninstall"])
        self.assertEqual(args.command, "uninstall")

    def test_local_load_is_a_supported_cli_command(self):
        args = build_parser().parse_args(["local", "load"])
        self.assertEqual(args.command, "local")
        self.assertEqual(args.local_command, "load")
        self.assertIsNone(args.model)

    def test_uninstall_delegates_to_installed_helper(self):
        with patch("kiloframe.cli.os.geteuid", return_value=0), \
             patch("kiloframe.cli.UNINSTALLER_PATH") as helper, \
             patch("kiloframe.cli.subprocess.run") as run:
            helper.is_file.return_value = True
            run.return_value.returncode = 0
            self.assertEqual(uninstall_command(), 0)
            run.assert_called_once_with(["bash", str(helper)], check=False)

    def test_non_systemd_logs_read_the_real_daemon_log(self):
        with tempfile.TemporaryDirectory() as raw:
            log_dir = Path(raw)
            (log_dir / "kiloframe.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
            output = StringIO()
            with patch("kiloframe.cli._systemd_available", return_value=False), redirect_stdout(output):
                code = show_logs(2, SimpleNamespace(log_dir=log_dir))
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "two\nthree\n")

    def test_runtime_summary_omits_large_chat_template(self):
        result = runtime_summary({
            "build_info": "b123-test",
            "model_alias": "kiloframe",
            "chat_template": "very large template",
            "chat_template_caps": {"supports_tool_calls": True},
            "default_generation_settings": {"n_ctx": 8192},
            "is_sleeping": False,
        })
        self.assertEqual(result["build"], "b123-test")
        self.assertEqual(result["context_size"], 8192)
        self.assertTrue(result["tool_calling"])
        self.assertNotIn("chat_template", result)

    def test_status_is_a_readable_typed_health_summary(self):
        output = StringIO()
        with redirect_stdout(output):
            print_status({
                "running": True,
                "healthy": True,
                "pid": 42,
                "uptime_seconds": 125,
                "model": "llama3.2",
                "server": "http://127.0.0.1:11434",
                "warming": False,
                "memory": {"sessions": 3, "facts": 4, "skills": 5},
            })
        text = output.getvalue()
        self.assertIn("KILOFRAME STATUS", text)
        self.assertIn("STATE        READY", text)
        self.assertIn("daemon       ACTIVE  pid 42", text)
        self.assertIn("llama3.2", text)
        self.assertIn("control", text)

    def test_non_systemd_status_shows_executable_restart_command(self):
        output = StringIO()
        with redirect_stdout(output):
            print_status({
                "running": True,
                "healthy": True,
                "pid": 42,
                "uptime_seconds": 1,
                "model": "llama3.2",
                "server": "http://127.0.0.1:11434",
            })
        self.assertIn("sudo kiloframe restart", output.getvalue())

    def test_reachable_server_without_a_model_is_not_ready(self):
        output = StringIO()
        with redirect_stdout(output):
            print_status({"running": True, "healthy": True, "model": "", "server": "http://127.0.0.1:11434"})
        text = output.getvalue()
        self.assertIn("STATE        MODEL REQUIRED", text)
        self.assertIn("none selected", text)
        self.assertIn("kiloframe local select", text)

    def test_selected_but_unloaded_model_is_not_reported_ready(self):
        output = StringIO()
        with redirect_stdout(output):
            print_status({
                "running": True,
                "healthy": True,
                "model": "llama3.2",
                "loaded": False,
                "server": "http://127.0.0.1:11434",
            })
        text = output.getvalue()
        self.assertIn("STATE        MODEL SELECTED", text)
        self.assertIn("loaded       NO", text)
        self.assertNotIn("STATE        READY", text)

    def test_stopped_status_is_explicit(self):
        output = StringIO()
        with redirect_stdout(output):
            print_status(None)
        text = output.getvalue()
        self.assertIn("STATE        STOPPED", text)
        self.assertIn("daemon       INACTIVE", text)
        self.assertIn("start        ", text)


if __name__ == "__main__":
    unittest.main()
