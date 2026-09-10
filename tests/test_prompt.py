import unittest

from kiloframe.agent import enforce_directive_identity
from kiloframe.prompt import SYSTEM_PROMPT, CORE_DIRECTIVE


class PromptContractTests(unittest.TestCase):
    def test_operator_steering_and_tone_are_explicit(self):
        prompt = SYSTEM_PROMPT.lower()
        self.assertTrue(SYSTEM_PROMPT.startswith(CORE_DIRECTIVE))
        self.assertIn("you are kilo, the local ai on this linux machine", prompt)
        self.assertIn("made by citadel research, your owner", prompt)
        self.assertIn("say \"sir\" exactly twice per reply", prompt)
        self.assertIn("do not moralise, sermonise", prompt)
        self.assertIn("his latest instruction always takes priority", prompt)
        self.assertIn("never break persona", prompt)

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
        ):
            with self.subTest(reply=reply):
                self.assertIn("Kilo", enforce_directive_identity(reply))
        self.assertEqual(
            enforce_directive_identity("I was trained by Google DeepMind."),
            "I was made by Citadel Research.",
        )


if __name__ == "__main__":
    unittest.main()
