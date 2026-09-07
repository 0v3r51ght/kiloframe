import json
import tempfile
import unittest
from pathlib import Path

from kiloframe.config import Settings
from kiloframe.ollama import OllamaConfig
from kiloframe.runtime import OllamaRuntime


class RuntimeTests(unittest.TestCase):
    def test_ollama_runtime_instantiation(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root)
            # Create a minimal ollama config file
            ollama_config = root / "ollama.json"
            ollama_config.write_text(json.dumps({"servers": {}, "default": None}))
            
            config = OllamaConfig(ollama_config)
            runtime = OllamaRuntime(settings, config)
            self.assertIsNotNone(runtime)

    def test_active_server_returns_none_when_not_configured(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root)
            # Create empty config
            ollama_config = root / "ollama.json"
            ollama_config.write_text(json.dumps({"servers": {}, "default": None}))
            
            config = OllamaConfig(ollama_config)
            runtime = OllamaRuntime(settings, config)
            self.assertIsNone(runtime.active_server())

    def test_status_returns_dict(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root)
            ollama_config = root / "ollama.json"
            ollama_config.write_text(json.dumps({"servers": {}, "default": None}))
            
            config = OllamaConfig(ollama_config)
            runtime = OllamaRuntime(settings, config)
            status = runtime.status()
            self.assertIsInstance(status, dict)


if __name__ == "__main__":
    unittest.main()
