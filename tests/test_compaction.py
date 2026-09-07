import tempfile
import unittest
from pathlib import Path

from kiloframe.agent import Agent
from kiloframe.config import Settings
from kiloframe.memory import MemoryStore


class ConversationCompactionTests(unittest.TestCase):
    def test_old_turns_are_preserved_as_a_bounded_role_labelled_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, max_history_tokens=120)
            memory = MemoryStore(root / "memory.sqlite3")
            try:
                session = memory.new_session()
                memory.add_message(session, "user", "first decision: use the blue deployment target " * 4)
                memory.add_message(session, "assistant", "recorded deployment target and rollback plan " * 4)
                memory.add_message(session, "user", "latest question")
                agent = object.__new__(Agent)
                agent.settings = settings
                agent.memory = memory
                kept, compacted = agent._history_within_budget(session)
                self.assertIsNotNone(compacted)
                self.assertIn("Conversation compacted", compacted or "")
                self.assertIn("blue deployment target", compacted or "")
                self.assertEqual(kept[-1]["content"], "latest question")
            finally:
                memory.close()
