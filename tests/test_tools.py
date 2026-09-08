import tempfile
import unittest
from pathlib import Path

from kiloframe.config import Settings
from kiloframe.errors import SecurityError, ToolError
from kiloframe.memory import MemoryStore
from kiloframe.security import PermissionManager
from kiloframe.tools import ToolContext, ToolRegistry


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root)
        self.memory = MemoryStore(root / "memory.db")
        self.tools = ToolRegistry(self.settings, self.memory, PermissionManager(root / "policy.json"))
        self.session = self.memory.new_session()
        self.context = ToolContext(self.session, root)

    async def asyncTearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    async def test_read_list_and_command(self):
        path = Path(self.tmp.name) / "hello.txt"
        path.write_text("hello KiloFrame", encoding="utf-8")
        result = await self.tools.execute("read_file", {"path": str(path)}, self.context)
        self.assertEqual(result["content"], "hello KiloFrame")
        command = await self.tools.execute("run_command", {"command": "/usr/bin/printf okay"}, self.context)
        self.assertEqual(command["stdout"], "okay")

    async def test_remote_commands_and_writes_use_the_approval_callback(self):
        names = {item["function"]["name"] for item in self.tools.schemas(remote=True)}
        self.assertIn("write_file", names)
        self.assertIn("run_command", names)
        approvals = []

        async def approve(capability, detail, risk):
            approvals.append((capability, detail, risk.value))
            return True

        context = ToolContext(
            self.session, Path(self.tmp.name), remote=True, permission_callback=approve
        )
        command = await self.tools.execute(
            "run_command", {"command": "/usr/bin/printf remote-ok"}, context
        )
        self.assertEqual(command["stdout"], "remote-ok")
        target = Path(self.tmp.name) / "telegram.txt"
        await self.tools.execute(
            "write_file", {"path": str(target), "content": "approved"}, context
        )
        self.assertEqual(target.read_text(), "approved")
        self.assertTrue(any(item[0] == "filesystem.write" for item in approvals))
        with self.assertRaises(SecurityError):
            await self.tools.execute(
                "write_file",
                {"path": str(target), "content": "denied"},
                ToolContext(self.session, Path(self.tmp.name), remote=True),
            )

    async def test_tool_schemas_are_task_relevant_for_fast_local_inference(self):
        baseline = self.tools.schemas()
        self.assertTrue(baseline)
        self.assertEqual(self.tools.schemas(request="Reply with exactly: ready"), [])
        names = {item["function"]["name"] for item in self.tools.schemas(request="Inspect this machine CPU")}
        self.assertEqual(names, {"system_info"})
        names = {item["function"]["name"] for item in self.tools.schemas(request="Search the web for Arch Linux")}
        self.assertEqual(names, {"web_search"})
        # Remote task selection obeys the same approval-gated execution boundary.
        remote = self.tools.schemas(remote=True)
        self.assertEqual(remote, baseline)

    async def test_memory_tools(self):
        await self.tools.execute("remember", {"content": "favorite shell is bash"}, self.context)
        result = await self.tools.execute("recall", {"query": "favorite shell"}, self.context)
        self.assertTrue(result["facts"])

    async def test_missing_tool_arguments_return_actionable_schema_error(self):
        with self.assertRaisesRegex(
            ToolError, r"write_file missing required argument.*path, content"
        ):
            await self.tools.execute("write_file", {}, self.context)

    async def test_web_search_parses_bounded_rss(self):
        rss = """<?xml version="1.0"?><rss><channel><item><title>Arch Linux</title><link>https://archlinux.org/</link><description>Simple &amp; lightweight.</description></item></channel></rss>"""
        results = self.tools._parse_search_rss(rss, 2)
        self.assertEqual(results[0]["url"], "https://archlinux.org/")
        self.assertEqual(results[0]["snippet"], "Simple & lightweight.")


class WebSecurityTests(unittest.TestCase):
    """The web tools are the only path that reaches outside the machine, so the
    private-network block has to survive redirects and hostile responses."""

    def test_private_and_non_http_urls_are_refused(self):
        from kiloframe.tools import _assert_public

        for url in ("http://127.0.0.1/", "http://192.168.1.1/admin", "http://[::1]/", "file:///etc/passwd", "gopher://example.com/"):
            with self.assertRaises((SecurityError, ToolError), msg=url):
                _assert_public(url)

    def test_redirect_targets_are_revalidated(self):
        """A public host answering 302 with a local address must not be followed;
        validating only the requested URL leaves the block bypassable."""
        from kiloframe.tools import _ValidatingRedirectHandler

        handler = _ValidatingRedirectHandler()
        with self.assertRaises(SecurityError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data/")

    def test_entity_expansion_document_is_refused(self):
        """ElementTree expands internal entities, so a small hostile document can
        expand to gigabytes on a machine with little memory to spare."""
        bomb = (
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
            '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]>'
            "<rss><channel><item><title>&lol2;</title></item></channel></rss>"
        )
        with self.assertRaises(ToolError):
            ToolRegistry._parse_search_rss(bomb, 5)


if __name__ == "__main__":
    unittest.main()
