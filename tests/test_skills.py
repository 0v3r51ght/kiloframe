import tempfile
import unittest
from pathlib import Path

from kiloframe.memory import MemoryStore
from kiloframe.skills import seed_superpowers


class SuperpowersSkillTests(unittest.TestCase):
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
