import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import storage_keys


class StorageKeysTest(unittest.TestCase):
    def test_data_path_uses_the_kv_v2_data_segment(self):
        self.assertEqual(storage_keys.data_path("apps", "acme", "test", "user-api"), "apps/data/acme/test/user-api")

    def test_merge_keeps_other_keys_and_other_storage_keys(self):
        record = {"Auth": {"Code": "x"}, "Storage": {"Extra": "keep", "BucketName": "old"}}
        values = {"BucketName": "new", "AccountId": "a", "AccessKey": "b", "SecretKey": "c"}
        merged = storage_keys.merge_storage(record, values)
        self.assertEqual(merged["Auth"], {"Code": "x"})
        self.assertEqual(merged["Storage"]["Extra"], "keep")
        self.assertEqual(merged["Storage"]["BucketName"], "new")
        self.assertEqual(record["Storage"]["BucketName"], "old")

    def test_merge_creates_the_section_when_missing(self):
        values = {"BucketName": "b", "AccountId": "a", "AccessKey": "k", "SecretKey": "s"}
        self.assertEqual(storage_keys.merge_storage({}, values)["Storage"], values)

    def test_report_prints_counts_and_never_the_secret_values(self):
        values = {"BucketName": "acme-test-media", "AccountId": "a" * 32, "AccessKey": "SECRETKEYVALUE", "SecretKey": "z" * 64}
        report = storage_keys.length_report(values)
        self.assertIn("acme-test-media", report)
        self.assertIn("AccountId (32 characters, expected 32)", report)
        self.assertIn("SecretKey (64 characters, expected 64)", report)
        self.assertNotIn("SECRETKEYVALUE", report)
        self.assertNotIn("a" * 32, report)

    def test_existing_value_is_not_asked_again_unless_replace(self):
        self.assertEqual(storage_keys.ask({"AccountId": "kept"}, "AccountId", False), "kept")


if __name__ == "__main__":
    unittest.main()
