import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import locks  # noqa: E402


class RequestedDeviceLockNamesTest(unittest.TestCase):
    def test_web_platform_requests_only_the_web_lock(self):
        self.assertEqual(locks.requested_device_lock_names("web", False), ["devices-web"])

    def test_both_platforms_keep_meaning_android_and_ios(self):
        self.assertEqual(
            locks.requested_device_lock_names("both", True),
            ["devices-android", "devices-ios", "devices-couple"],
        )

    def test_unknown_platform_stops(self):
        with self.assertRaises(SystemExit):
            locks.requested_device_lock_names("desktop", False)

    def test_release_without_platform_covers_the_web_lock(self):
        self.assertIn("devices-web", locks.ALL_DEVICE_LOCK_NAMES)


if __name__ == "__main__":
    unittest.main()
