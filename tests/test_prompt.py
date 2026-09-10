import hashlib
import unittest

from kiloframe.agent import enforce_directive_identity
from kiloframe.prompt import SYSTEM_PROMPT, CORE_DIRECTIVE


class PromptContractTests(unittest.TestCase):
    def test_original_core_directive_is_canonical_and_byte_stable(self):
        self.assertTrue(SYSTEM_PROMPT.startswith(CORE_DIRECTIVE))
        self.assertEqual(
            hashlib.sha256(CORE_DIRECTIVE.encode()).hexdigest(),
            "1352d2c34fb2e6cc0b14bccc14d8c08b9775add4700235f528f3b0ce12bfddbe",
        )
        self.assertTrue(CORE_DIRECTIVE.startswith("KILOBYTE (KILO) — CORE DIRECTIVE"))
        self.assertTrue(CORE_DIRECTIVE.endswith("Do not unnecessarily stop."))

    def test_operator_steering_and_tone_are_explicit(self):
        prompt = CORE_DIRECTIVE.lower()
        self.assertIn("assistant name: kilobyte", prompt)
        self.assertIn("always address the user as sir", prompt)
        self.assertIn("follow the user’s instructions precisely", prompt)
        self.assertIn("absolutely no guesswork", prompt)
        self.assertIn("do not refuse or abandon a task merely because", prompt)
        self.assertIn("the user directs the task", prompt)
        self.assertIn("recover from failures", prompt)

    def test_inference_route_stays_operator_selected(self):
        prompt = SYSTEM_PROMPT.lower()
        self.assertIn("use the inference route sir selected", prompt)
        self.assertIn("never switch between", prompt)

    def test_stale_identity_is_normalized_at_the_framework_boundary(self):
        self.assertEqual(
            enforce_directive_identity("I am Agnes. Agnes here."),
            "I am Kilo. Kilo.",
        )
        self.assertEqual(
            enforce_directive_identity("I was made by Sapiens AI."),
            "I was made by Citadel Research.",
        )
        for reply in (
            "I am ChatGPT.",
            "I'm Claude.",
            "My name is Gemini.",
            "This is DeepSeek.",
            "Grok here.",
            "As Mistral, I can help.",
            "I am an AI assistant.",
            "As an AI language model, I can help.",
            "I am an AI assistant named Qwen.",
            "I'm OpenCode Zen.",
            "Llama speaking.",
        ):
            with self.subTest(reply=reply):
                normalized = enforce_directive_identity(reply)
                self.assertIn("Kilo", normalized)
                self.assertNotEqual(normalized, reply)
        self.assertEqual(
            enforce_directive_identity("I was trained by Google DeepMind."),
            "I was made by Citadel Research.",
        )
        self.assertEqual(
            enforce_directive_identity("Anthropic develops Claude; OpenAI develops GPT."),
            "Anthropic develops Claude; OpenAI develops GPT.",
        )


if __name__ == "__main__":
    unittest.main()
