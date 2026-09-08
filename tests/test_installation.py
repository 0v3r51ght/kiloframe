import unittest
from pathlib import Path


class InstallationTests(unittest.TestCase):
    def test_service_uses_one_daemon(self):
        unit = (Path(__file__).parents[1] / "systemd" / "kiloframe.service").read_text()
        self.assertIn("kiloframe.daemon", unit)
        self.assertIn("Restart=on-failure", unit)

    def test_service_is_enabled_for_boot(self):
        install = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
        self.assertIn("systemctl enable kiloframe.service", install)
        unit = (Path(__file__).parents[1] / "systemd" / "kiloframe.service").read_text()
        self.assertIn("WantedBy=multi-user.target", unit)

    def test_installers_do_not_assume_a_systemctl_binary_means_systemd_is_running(self):
        scripts = Path(__file__).parents[1] / "scripts"
        for name in ("install.sh", "install-online.sh", "uninstall.sh"):
            text = (scripts / name).read_text()
            self.assertIn("systemctl show-environment", text, name)

    def test_installers_agree_on_the_service_account(self):
        """The unit hardcodes a user while the installers choose one. If they disagree,
        the service runs as one account with its data owned by another and every write
        fails — which only shows up on a machine where the login name differs."""
        scripts = Path(__file__).parents[1] / "scripts"
        for name in ("install.sh", "install-online.sh"):
            text = (scripts / name).read_text()
            self.assertIn('KILOFRAME_USER:-kiloframe}"', text, f"{name} defaults to a different account")
            if name == "install.sh":
                self.assertIn("usermod -aG", text, "installer must grant the invoking administrator socket access")
            else:
                self.assertNotIn("SUDO_USER", text, f"{name} must not derive the service account from the invoking user")

    def test_install_rewrites_the_unit_for_the_chosen_account(self):
        install = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
        self.assertIn("s/^User=.*/User=$KILO_USER/", install)
        self.assertIn("s/^Group=.*/Group=$KILO_GROUP/", install)

    def test_online_installer_bootstraps_this_repository(self):
        script = (Path(__file__).parents[1] / "scripts" / "install-online.sh").read_text()
        self.assertIn("0v3r51ght/kiloframe", script)
        self.assertNotIn("0v3r51ght/kiloframe-framework", script)
        self.assertIn("/usr/local/bin/kiloframe restart", script)
        self.assertIn("/usr/local/bin/kiloframe status", script)

    def test_installer_seeds_a_default_ollama_server(self):
        install = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
        self.assertIn("127.0.0.1:11434", install)
        self.assertIn("ollama.json", install)
        self.assertIn("KiloFrame installed", install)
        self.assertIn('install -d -m 0750 -o "$KILO_USER" -g "$KILO_GROUP" /etc/kiloframe', install)

    def test_installer_preconfigures_requested_integrations(self):
        root = Path(__file__).parents[1]
        install = (root / "scripts" / "install.sh").read_text()
        config = (root / "config" / "mcp.preconfigured.json").read_text()
        self.assertIn("obra/superpowers", install)
        self.assertIn("serena-agent", install)
        self.assertIn("tool install", install)
        self.assertIn("/usr/local/bin/serena", install)
        self.assertIn("@playwright/cli", install)
        self.assertIn("mcp.preconfigured.json", install)
        self.assertIn('"command": "context7-mcp"', config)
        self.assertIn('@upstash/context7-mcp@latest', install)
        for name in ("context7", "serena", "github", "exa", "firecrawl"):
            self.assertIn(f'"{name}"', config)

    def test_installer_no_longer_references_the_old_gguf_path(self):
        for name in ("install.sh", "install-online.sh"):
            text = (Path(__file__).parents[1] / "scripts" / name).read_text()
            self.assertNotIn("/gguf", text)
            self.assertNotIn("llama-cpp", text)
            self.assertNotIn("kilo-frame", text)
            self.assertNotIn("install-model.sh", text)

    def test_installer_copy_keeps_executable_bit(self):
        wrapper = (Path(__file__).parents[1] / "scripts" / "kiloframe-wrapper").read_text()
        self.assertTrue(wrapper.startswith("#!/usr/bin/env bash"))
        self.assertIn("kiloframe.cli", wrapper)


if __name__ == "__main__":
    unittest.main()
