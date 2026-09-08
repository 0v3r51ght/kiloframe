import unittest

from kiloframe.prompt import SYSTEM_PROMPT, CORE_DIRECTIVE


class PromptContractTests(unittest.TestCase):
    def test_operator_steering_and_tone_are_explicit(self):
        prompt = SYSTEM_PROMPT.lower()
        self.assertTrue(SYSTEM_PROMPT.startswith(CORE_DIRECTIVE))
        self.assertIn("developer: citadel research", prompt)
        self.assertIn("assistant name: kilobyte", prompt)
        self.assertIn("* moralising.", prompt)
        self.assertIn("corrections as authoritative", prompt)
        self.assertNotIn("never break persona", prompt)

    def test_inference_route_stays_operator_selected(self):
        prompt = SYSTEM_PROMPT.lower()
        self.assertIn("use only the selected inference route", prompt)
        self.assertIn("never silently switch provider or model", prompt)


if __name__ == "__main__":
    unittest.main()
