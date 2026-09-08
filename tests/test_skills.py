import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kiloframe.memory import MemoryStore
from kiloframe.skills import seed_superpowers


class PreconfiguredSkillTests(unittest.TestCase):
    def test_installed_superpowers_skill_is_loaded_into_kiloframe_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "brainstorming" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text(
                "---\nname: brainstorming\ndescription: Use before designing a feature\n---\n"
                "Explore constraints before implementation.\n",
                encoding="utf-8",
            )
            memory = MemoryStore(root / "memory.sqlite3")
            try:
                self.assertEqual(seed_superpowers(memory, root), 1)
                records = memory.recall_skills("design feature")
                self.assertEqual(records[0]["name"], "superpowers:brainstorming")
                self.assertIn("Explore constraints", records[0]["steps"])
            finally:
                memory.close()

    def test_official_playwright_agent_skill_is_loaded_into_kiloframe_memory(self):
        from kiloframe.config import Settings
        from kiloframe.skills import seed_preconfigured_skills

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            skill = root / "playwright" / ".agents" / "skills" / "playwright-cli" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: playwright-cli\n---\nOfficial Playwright workflow marker.",
                encoding="utf-8",
            )
            memory = MemoryStore(root / "memory.sqlite3")
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root)
            try:
                with patch.dict("os.environ", {"KILOFRAME_INTEGRATIONS_DIR": str(root)}):
                    seed_preconfigured_skills(memory, settings)
                found = next(
                    item
                    for item in memory.recall_skills("browser automation")
                    if item["name"] == "playwright-cli"
                )
                self.assertIn("Official Playwright workflow marker", found["steps"])
            finally:
                memory.close()


if __name__ == "__main__":
    unittest.main()
