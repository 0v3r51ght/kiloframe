import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kiloframe.config import Settings
from kiloframe.resources import MIB, ResourceManager


class ResourceTests(unittest.TestCase):
    def test_profile_is_dynamic_and_sane(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root)
            profile = ResourceManager(settings).profile()
            self.assertGreaterEqual(profile.threads, 1)
            self.assertLessEqual(profile.threads, 8)
            self.assertLessEqual(profile.safe_available_mb, profile.available_mb)
            self.assertGreaterEqual(profile.safe_available_mb, 0)
            self.assertEqual(set(profile.to_dict()), {
                "total_mb", "available_mb", "safe_available_mb", "threads",
                "gpu", "cpu_arch", "cpu_level",
            })
            ok, headroom = ResourceManager(settings).live_headroom()
            self.assertIsInstance(ok, bool)
            self.assertGreaterEqual(headroom, 0)

    def test_profile_respects_cgroup_and_memory_reserve(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            settings = Settings(data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, home=root, reserve_memory_mb=1024)
            with patch("kiloframe.resources._meminfo", return_value={
                "MemTotal": 4096 * MIB, "MemAvailable": 3000 * MIB,
            }), patch("kiloframe.resources._cgroup_available", return_value=2000 * MIB):
                profile = ResourceManager(settings).profile()
            self.assertEqual(profile.total_mb, 4096)
            self.assertEqual(profile.available_mb, 2000)
            self.assertEqual(profile.safe_available_mb, 976)

    def test_headroom_uses_cgroup_pressure_threshold(self):
        manager = ResourceManager(Settings())
        for available, expected in ((319, False), (320, True)):
            with self.subTest(available=available), patch(
                "kiloframe.resources._meminfo", return_value={"MemAvailable": 3000 * MIB},
            ), patch("kiloframe.resources._cgroup_available", return_value=available * MIB):
                self.assertEqual(manager.live_headroom(), (expected, available))


if __name__ == "__main__":
    unittest.main()
