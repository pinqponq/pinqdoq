import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import new_product  # noqa: E402

MANIFEST = {
    "placeholders": {
        "app_name": "TemplateApp",
        "package": "com.pinqponq.templateapp",
        "bundle_id": "com.pinqponq.templateapp.TemplateApp",
        "api_base_url": "https://api-test.template.example/",
    },
    "keys": {
        "REVENUECAT_ANDROID_KEY": {"secret": False},
        "GOOGLE_WEB_CLIENT_ID": {"secret": False, "required": False},
        "PINQLOQ_API_KEY": {"secret": True, "file": "local.properties"},
        "SIGNING_PASSWORD": {"secret": True, "file": "signing/keystore.properties", "required": False},
    },
    "modules": {
        "paywall": {"paths": ["composeApp/src/commonMain/kotlin/feature/paywall"]},
        "onboarding": {"paths": ["composeApp/src/commonMain/kotlin/feature/onboarding"], "default": False},
        "widget": {"paths": ["iosApp/TemplateAppWidget", "composeApp/src/commonMain/kotlin/core/Widget.kt"]},
    },
    "theme_file": "composeApp/src/commonMain/kotlin/core/presentation/theme/Color.kt",
}

PRODUCT = {
    "app_name": "Lumo",
    "package": "com.deveng.lumo",
    "bundle_id": "com.deveng.lumo.Lumo",
    "api_base_url": "https://api-test.lumo.app/",
    "keys": {"REVENUECAT_ANDROID_KEY": "goog_public", "PINQLOQ_API_KEY": "plq_secret"},
    "modules": {"paywall": False},
    "theme": {"PrimaryColor": "#12AB34"},
}

FILES = {
    "settings.gradle.kts": 'rootProject.name = "TemplateApp"\ninclude(":composeApp")\n',
    ".gitignore": "build/\nlocal.properties\n/signing/keystore.properties\n",
    "composeApp/src/commonMain/kotlin/core/Widget.kt": "object Widget\n",
    "composeApp/src/commonMain/kotlin/core/DeepLink.kt": 'const val SCHEME = "templateapp"\n',
    "composeApp/build.gradle.kts": (
        'android {\n    namespace = "com.pinqponq.templateapp"\n'
        '    buildConfigField("String", "REVENUECAT_PUBLIC_API_KEY", "\\"__REVENUECAT_ANDROID_KEY__\\"")\n}\n'
    ),
    "composeApp/src/androidMain/kotlin/com/pinqponq/templateapp/MainActivity.kt": (
        "package com.pinqponq.templateapp\n\nclass MainActivity\n"
    ),
    "composeApp/src/commonMain/kotlin/core/Constants.kt": 'const val BASE_URL = "https://api-test.template.example/"\n',
    "composeApp/src/commonMain/kotlin/core/presentation/theme/Color.kt": (
        "val PrimaryColor = Color(0xFFFFC964)\nval ErrorColor = Color(0xFFDC2626)\n"
    ),
    "composeApp/src/commonMain/kotlin/feature/paywall/PaywallScreen.kt": "package feature.paywall\n",
    "composeApp/src/commonMain/kotlin/feature/onboarding/OnboardingScreen.kt": "package feature.onboarding\n",
    "composeApp/src/commonMain/kotlin/di/initKoin.kt": (
        "modules(\n    loginModule,\n    // template:paywall:start\n    paywallModule,\n"
        "    // template:paywall:end\n    // template:onboarding:start\n    onboardingModule,\n"
        "    // template:onboarding:end\n)\n"
    ),
    "iosApp/Configuration/Config.xcconfig": "TEAM_ID=\nBUNDLE_ID=com.pinqponq.templateapp.TemplateApp\nAPP_NAME=TemplateApp\n",
    "iosApp/TemplateAppWidget/TemplateAppWidget.swift": "struct TemplateAppWidget {}\n",
}


def write_template(root: Path, manifest: dict = None, files: dict = None) -> None:
    for relative, content in (files or FILES).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "composeApp/src/androidMain/res/drawable").mkdir(parents=True, exist_ok=True)
    (root / "composeApp/src/androidMain/res/drawable/icon.png").write_bytes(b"\x89PNG\0TemplateApp")
    (root / new_product.MANIFEST_NAME).write_text(json.dumps(manifest or MANIFEST), encoding="utf-8")


class NewProductTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.root = Path(self.workdir.name)
        self.template = self.root / "template"
        self.destination = self.root / "lumo"
        self.product_path = self.root / "product.json"
        write_template(self.template)

    def tearDown(self):
        self.workdir.cleanup()

    def run_generate(self, product: dict = None, dry_run: bool = False) -> dict:
        self.product_path.write_text(json.dumps(product or PRODUCT), encoding="utf-8")
        if dry_run:
            return new_product.generate(str(self.template), self.product_path, self.destination, dry_run=True)
        return new_product.generate(str(self.template), self.product_path, self.destination)

    def assert_error(self, code: str, product: dict = None) -> None:
        with self.assertRaises(new_product.StarterError) as context:
            self.run_generate(product)
        self.assertEqual(code, context.exception.error_code)

    def read(self, relative: str) -> str:
        return (self.destination / relative).read_text(encoding="utf-8")

    def all_text(self) -> str:
        return "".join(
            path.read_bytes().decode("utf-8", "replace") for path in self.destination.rglob("*") if path.is_file()
        )

    def test_identity_is_replaced_in_contents(self):
        self.run_generate()

        self.assertIn('rootProject.name = "Lumo"', self.read("settings.gradle.kts"))
        self.assertIn('namespace = "com.deveng.lumo"', self.read("composeApp/build.gradle.kts"))
        self.assertEqual(
            "TEAM_ID=\nBUNDLE_ID=com.deveng.lumo.Lumo\nAPP_NAME=Lumo\n",
            self.read("iosApp/Configuration/Config.xcconfig"),
        )
        self.assertIn("https://api-test.lumo.app/", self.read("composeApp/src/commonMain/kotlin/core/Constants.kt"))

    def test_lowercase_app_name_and_longest_placeholder_win(self):
        product = dict(PRODUCT, bundle_id="com.deveng.lumo.ios")

        result = self.run_generate(product)

        self.assertIn('SCHEME = "lumo"', self.read("composeApp/src/commonMain/kotlin/core/DeepLink.kt"))
        self.assertIn("BUNDLE_ID=com.deveng.lumo.ios\n", self.read("iosApp/Configuration/Config.xcconfig"))
        self.assertEqual(9, result["files_changed"])

    def test_package_with_new_root_prunes_old_directories(self):
        result = self.run_generate(dict(PRODUCT, package="org.lumo"))

        self.assertTrue((self.destination / "composeApp/src/androidMain/kotlin/org/lumo/MainActivity.kt").is_file())
        self.assertFalse((self.destination / "composeApp/src/androidMain/kotlin/com").exists())
        self.assertEqual(3, result["paths_renamed"])

    def test_package_directories_and_named_files_move(self):
        self.run_generate()

        self.assertTrue((self.destination / "composeApp/src/androidMain/kotlin/com/deveng/lumo/MainActivity.kt").is_file())
        self.assertFalse((self.destination / "composeApp/src/androidMain/kotlin/com/pinqponq").exists())
        self.assertTrue((self.destination / "iosApp/LumoWidget/LumoWidget.swift").is_file())
        self.assertIn("package com.deveng.lumo", self.read("composeApp/src/androidMain/kotlin/com/deveng/lumo/MainActivity.kt"))

    def test_unused_modules_are_removed_with_their_blocks(self):
        result = self.run_generate()

        self.assertEqual(["paywall", "onboarding"], result["modules_removed"])
        self.assertTrue((self.destination / "composeApp/src/commonMain/kotlin/core/Widget.kt").is_file())
        self.assertFalse((self.destination / "composeApp/src/commonMain/kotlin/feature/paywall").exists())
        self.assertFalse((self.destination / "composeApp/src/commonMain/kotlin/feature/onboarding").exists())
        self.assertEqual("modules(\n    loginModule,\n)\n", self.read("composeApp/src/commonMain/kotlin/di/initKoin.kt"))

    def test_module_paths_can_be_files_and_unlisted_modules_stay(self):
        self.run_generate(dict(PRODUCT, modules={"widget": False}))

        self.assertFalse((self.destination / "composeApp/src/commonMain/kotlin/core/Widget.kt").exists())
        self.assertFalse((self.destination / "iosApp/LumoWidget").exists())
        self.assertTrue((self.destination / "composeApp/src/commonMain/kotlin/feature/paywall/PaywallScreen.kt").is_file())

    def test_kept_module_keeps_code_without_markers(self):
        product = dict(PRODUCT, modules={"paywall": True, "onboarding": True})

        result = self.run_generate(product)

        self.assertEqual([], result["modules_removed"])
        self.assertEqual(
            "modules(\n    loginModule,\n    paywallModule,\n    onboardingModule,\n)\n",
            self.read("composeApp/src/commonMain/kotlin/di/initKoin.kt"),
        )
        self.assertTrue((self.destination / "composeApp/src/commonMain/kotlin/feature/paywall/PaywallScreen.kt").is_file())

    def test_marker_of_module_missing_from_manifest_keeps_its_block(self):
        (self.template / "Extra.kt").write_text("// template:chat:start\nval chat = 1\n// template:chat:end\n", encoding="utf-8")

        self.run_generate()

        self.assertEqual("val chat = 1\n", self.read("Extra.kt"))

    def test_public_key_goes_into_files_and_secret_only_into_ignored_file(self):
        result = self.run_generate()

        self.assertIn('\\"goog_public\\"', self.read("composeApp/build.gradle.kts"))
        self.assertEqual("PINQLOQ_API_KEY=plq_secret\n", self.read("local.properties"))
        self.assertEqual(1, self.all_text().count("plq_secret"))
        self.assertEqual(["REVENUECAT_ANDROID_KEY", "PINQLOQ_API_KEY"], result["keys_written"])

    def test_secret_in_subfolder_is_written_when_its_path_is_ignored(self):
        keys = dict(PRODUCT["keys"], SIGNING_PASSWORD="sign_secret")

        self.run_generate(dict(PRODUCT, keys=keys))

        self.assertEqual("SIGNING_PASSWORD=sign_secret\n", self.read("signing/keystore.properties"))

    def test_secret_needs_a_gitignore(self):
        (self.template / ".gitignore").unlink()

        self.assert_error(new_product.SECRET_NOT_IGNORED)

    def test_theme_needs_a_theme_file(self):
        manifest = {key: value for key, value in MANIFEST.items() if key != "theme_file"}
        (self.template / new_product.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

        self.assert_error(new_product.THEME_FILE_MISSING)

    def test_existing_empty_destination_is_used(self):
        self.destination.mkdir()

        self.run_generate()

        self.assertTrue((self.destination / "settings.gradle.kts").is_file())

    def test_theme_color_is_set_with_opaque_alpha(self):
        product = dict(PRODUCT, theme={"PrimaryColor": "#12ab34", "ErrorColor": "#80FF0000"})

        result = self.run_generate(product)

        color = self.read("composeApp/src/commonMain/kotlin/core/presentation/theme/Color.kt")
        self.assertEqual("val PrimaryColor = Color(0xFF12AB34)\nval ErrorColor = Color(0x80FF0000)\n", color)
        self.assertEqual(["ErrorColor", "PrimaryColor"], result["theme_tokens"])

    def test_binary_files_are_copied_unchanged_and_manifest_is_dropped(self):
        self.run_generate()

        self.assertEqual(
            b"\x89PNG\0TemplateApp",
            (self.destination / "composeApp/src/androidMain/res/drawable/icon.png").read_bytes(),
        )
        self.assertFalse((self.destination / new_product.MANIFEST_NAME).exists())

    def test_dry_run_writes_nothing(self):
        result = self.run_generate(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertFalse(self.destination.exists())

    def test_invalid_package_is_rejected(self):
        self.assert_error(new_product.INVALID_FIELD, dict(PRODUCT, package="Com.Lumo"))
        self.assertFalse(self.destination.exists())

    def test_each_identity_field_is_validated(self):
        for field, value in (
            ("app_name", "lumo"),
            ("bundle_id", "lumo"),
            ("api_base_url", "http://api.lumo.app"),
        ):
            with self.subTest(field=field):
                self.assert_error(new_product.INVALID_FIELD, dict(PRODUCT, **{field: value}))

    def test_missing_identity_field_is_rejected(self):
        product = {key: value for key, value in PRODUCT.items() if key != "bundle_id"}

        self.assert_error(new_product.MISSING_FIELDS, product)

    def test_missing_required_key_is_rejected_but_optional_key_is_not(self):
        self.assert_error(new_product.MISSING_KEYS, dict(PRODUCT, keys={"PINQLOQ_API_KEY": "plq_secret"}))

        result = self.run_generate(dict(PRODUCT, keys=dict(PRODUCT["keys"])))

        self.assertNotIn("GOOGLE_WEB_CLIENT_ID", result["keys_written"])

    def test_unknown_key_module_and_color_are_rejected(self):
        self.assert_error(new_product.UNKNOWN_KEYS, dict(PRODUCT, keys=dict(PRODUCT["keys"], STRIPE_KEY="x")))
        self.assert_error(new_product.UNKNOWN_MODULES, dict(PRODUCT, modules={"chat": True}))
        self.assert_error(new_product.INVALID_COLOR, dict(PRODUCT, theme={"PrimaryColor": "red"}))
        self.assert_error(new_product.UNKNOWN_THEME_TOKEN, dict(PRODUCT, theme={"AccentColor": "#000000"}))

    def test_non_empty_destination_is_rejected(self):
        self.destination.mkdir()
        (self.destination / "keep.txt").write_text("existing", encoding="utf-8")

        self.assert_error(new_product.INVALID_DESTINATION)
        self.assertEqual("existing", (self.destination / "keep.txt").read_text(encoding="utf-8"))

    def test_leftover_placeholder_fails_without_writing(self):
        (self.template / "Keys.kt").write_text('val pinqloqKey = "__PINQLOQ_API_KEY__"\n', encoding="utf-8")

        with self.assertRaises(new_product.StarterError) as context:
            self.run_generate()

        self.assertEqual(new_product.PLACEHOLDERS_LEFT, context.exception.error_code)
        self.assertEqual("Keys.kt: __PINQLOQ_API_KEY__", context.exception.message)
        self.assertFalse(self.destination.exists())

    def test_secret_file_must_be_gitignored(self):
        (self.template / ".gitignore").write_text("build/\n", encoding="utf-8")

        self.assert_error(new_product.SECRET_NOT_IGNORED)

    def test_unclosed_marker_is_rejected(self):
        (self.template / "Extra.kt").write_text("// template:paywall:start\nval x = 1\n", encoding="utf-8")

        self.assert_error(new_product.UNCLOSED_MARKER)

    def test_manifest_problems_are_rejected(self):
        broken = (
            dict(MANIFEST, placeholders={"app_name": "TemplateApp"}),
            dict(MANIFEST, keys={"lower_key": {}}),
            dict(MANIFEST, keys={"SECRET": {"secret": True}}),
        )
        for manifest in broken:
            with self.subTest(manifest=manifest):
                (self.template / new_product.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
                self.assert_error(new_product.INVALID_MANIFEST)

    def test_template_without_manifest_or_bad_url_is_unavailable(self):
        (self.template / new_product.MANIFEST_NAME).unlink()
        self.assert_error(new_product.TEMPLATE_UNAVAILABLE)

        self.product_path.write_text(json.dumps(PRODUCT), encoding="utf-8")
        with self.assertRaises(new_product.StarterError) as context:
            new_product.generate("https://127.0.0.1:9/missing.git", self.product_path, self.destination)
        self.assertEqual(new_product.TEMPLATE_UNAVAILABLE, context.exception.error_code)

    def test_package_target_that_exists_in_template_is_rejected(self):
        (self.template / "composeApp/src/androidMain/kotlin/com/deveng/lumo").mkdir(parents=True)
        (self.template / "composeApp/src/androidMain/kotlin/com/deveng/lumo/Other.kt").write_text("x", encoding="utf-8")

        self.assert_error(new_product.PATH_CONFLICT)

    def test_main_prints_json_and_exit_codes(self):
        self.product_path.write_text(json.dumps(PRODUCT), encoding="utf-8")
        args = ["--template", str(self.template), "--product", str(self.product_path), "--destination", str(self.destination)]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = new_product.main(args)
        self.assertEqual(0, code)
        self.assertEqual(str(self.destination), json.loads(output.getvalue())["destination"])

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = new_product.main(args)
        self.assertEqual(new_product.EXIT_CODE_ERROR, code)
        self.assertEqual(new_product.INVALID_DESTINATION, json.loads(output.getvalue())["error_code"])

    def test_theme_file_that_does_not_exist_is_rejected(self):
        (self.template / MANIFEST["theme_file"]).unlink()

        self.assert_error(new_product.THEME_FILE_MISSING)

    def test_template_secret_files_are_not_copied(self):
        (self.template / "local.properties").write_text("PINQLOQ_API_KEY=template_secret\nsdk.dir=/sdk\n", encoding="utf-8")
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["keys"]["PINQLOQ_API_KEY"]["required"] = False
        (self.template / new_product.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        keys = {"REVENUECAT_ANDROID_KEY": "goog_public"}

        self.run_generate(dict(PRODUCT, keys=keys))

        self.assertFalse((self.destination / "local.properties").exists())
        self.assertNotIn("template_secret", self.all_text())

    def test_secret_file_is_written_fresh(self):
        (self.template / "local.properties").write_text("PINQLOQ_API_KEY=template_secret\n", encoding="utf-8")

        self.run_generate()

        self.assertEqual("PINQLOQ_API_KEY=plq_secret\n", self.read("local.properties"))

    def test_gitignore_globs_and_directories_cover_secret_files(self):
        keys = dict(PRODUCT["keys"], SIGNING_PASSWORD="sign_secret")
        for entries in ("*.properties\n", "local.properties\nsigning/\n", "# comment\n!x\nlocal.properties\n/signing/*.properties\n"):
            with self.subTest(entries=entries):
                (self.template / ".gitignore").write_text(entries, encoding="utf-8")
                self.run_generate(dict(PRODUCT, keys=keys))
                self.assertEqual("SIGNING_PASSWORD=sign_secret\n", self.read("signing/keystore.properties"))
                shutil.rmtree(self.destination)

    def test_gitignore_entries_that_do_not_cover_the_file_are_rejected(self):
        keys = dict(PRODUCT["keys"], SIGNING_PASSWORD="sign_secret")
        for entries in ("local.properties\nother/\n", "local.properties\n# signing/\n", "local.properties\n!signing/keystore.properties\n", "local.properties\nkeystore/*.properties\n"):
            with self.subTest(entries=entries):
                (self.template / ".gitignore").write_text(entries, encoding="utf-8")
                self.assert_error(new_product.SECRET_NOT_IGNORED, dict(PRODUCT, keys=keys))

    def test_optional_public_key_left_out_becomes_empty(self):
        (self.template / "Keys.kt").write_text('val clientId = "__GOOGLE_WEB_CLIENT_ID__"\n', encoding="utf-8")

        self.run_generate()

        self.assertEqual('val clientId = ""\n', self.read("Keys.kt"))

    def test_destination_that_is_a_file_is_rejected(self):
        self.destination.write_text("x", encoding="utf-8")

        self.assert_error(new_product.INVALID_DESTINATION)

    def test_non_string_values_are_rejected(self):
        self.assert_error(new_product.INVALID_FIELD, dict(PRODUCT, app_name=42))
        self.assert_error(new_product.INVALID_FIELD, dict(PRODUCT, keys=dict(PRODUCT["keys"], REVENUECAT_ANDROID_KEY=7)))

    def test_package_inside_the_template_package_is_rejected(self):
        self.assert_error(new_product.PATH_CONFLICT, dict(PRODUCT, package="com.pinqponq.templateapp.lumo"))

    def test_product_file_that_is_not_an_object_is_rejected(self):
        self.product_path.write_text("[]", encoding="utf-8")

        with self.assertRaises(new_product.StarterError) as context:
            new_product.generate(str(self.template), self.product_path, self.destination)

        self.assertEqual(new_product.INVALID_PRODUCT, context.exception.error_code)

    def test_error_output_lists_missing_fields(self):
        product = {key: value for key, value in PRODUCT.items() if key not in ("bundle_id", "api_base_url")}
        self.product_path.write_text(json.dumps(product), encoding="utf-8")
        args = ["--template", str(self.template), "--product", str(self.product_path), "--destination", str(self.destination)]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = new_product.main(args)

        self.assertEqual(new_product.EXIT_CODE_ERROR, code)
        self.assertEqual(
            {"error_code": "MISSING_FIELDS", "message": "Product is missing bundle_id, api_base_url",
             "missing_fields": ["bundle_id", "api_base_url"], "how_to_fix": "Add the fields to the product file"},
            json.loads(output.getvalue()),
        )

    def test_file_system_error_is_reported_as_json(self):
        self.product_path.write_text(json.dumps(PRODUCT), encoding="utf-8")
        (self.template / "unreadable.txt").write_text("x", encoding="utf-8")
        (self.template / "unreadable.txt").chmod(0)
        args = ["--template", str(self.template), "--product", str(self.product_path), "--destination", str(self.destination)]

        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = new_product.main(args)
        finally:
            (self.template / "unreadable.txt").chmod(0o644)

        self.assertEqual(new_product.EXIT_CODE_ERROR, code)
        self.assertEqual(new_product.FILE_SYSTEM_ERROR, json.loads(output.getvalue())["error_code"])

    def test_sections_that_are_not_objects_are_rejected(self):
        for section in ("keys", "modules", "theme"):
            with self.subTest(section=section):
                self.assert_error(new_product.INVALID_FIELD, dict(PRODUCT, **{section: []}))

    def test_secret_file_under_a_placeholder_folder_follows_the_rename(self):
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["keys"]["SIGNING_PASSWORD"]["file"] = "iosApp/TemplateAppWidget/Secrets.xcconfig"
        (self.template / new_product.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        (self.template / ".gitignore").write_text("local.properties\nSecrets.xcconfig\n", encoding="utf-8")

        self.run_generate(dict(PRODUCT, keys=dict(PRODUCT["keys"], SIGNING_PASSWORD="sign_secret")))

        self.assertEqual("SIGNING_PASSWORD=sign_secret\n", self.read("iosApp/LumoWidget/Secrets.xcconfig"))

    def test_git_failure_is_reported(self):
        original_run = new_product.subprocess.run
        new_product.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, "", "no git")
        try:
            self.assert_error(new_product.GIT_UNAVAILABLE)
        finally:
            new_product.subprocess.run = original_run

    def test_invalid_product_json_is_rejected(self):
        self.product_path.write_text("{", encoding="utf-8")

        with self.assertRaises(new_product.StarterError) as context:
            new_product.generate(str(self.template), self.product_path, self.destination)

        self.assertEqual(new_product.INVALID_PRODUCT, context.exception.error_code)


if __name__ == "__main__":
    unittest.main()
