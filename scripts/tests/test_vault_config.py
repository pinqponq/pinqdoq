"""Runs scripts/vault_config.py end to end against two in-memory fake Vault servers (one test, one prod).

    python -m unittest discover -s scripts/tests -v

Needs git on the PATH. Nothing outside a temporary directory is touched and no real Vault is contacted.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / 'vault_config.py'
SECRET_VALUE = 'Server=db;Password=hunter2'
TEST_TOKEN, PROD_TOKEN, FILE_TOKEN = 'tok-test-9f3a1c', 'tok-prod-77b2e0', 'tok-file-5d41aa'
BASE_SETTINGS = {
    'Logging': {'LogLevel': {'Default': 'Information'}},
    'Database': {'ConnectionString': SECRET_VALUE, 'CommandTimeoutSeconds': 30},
    'Downstream': {'BaseUrl': 'http://prod-host:8080'},
}
DEVELOPMENT_SETTINGS = {'Downstream': {'BaseUrl': 'http://localhost:8080'}}


class FakeVault:
    """Just enough of the KV v2 HTTP API: read, write and the mount listing."""

    def __init__(self):
        self.records = {}
        self.tokens_seen = set()
        self.mounts = {'apps/': {'options': {'version': '2'}}}
        records = self.records
        tokens_seen = self.tokens_seen
        mounts = self.mounts

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def _send(self, status, body=None):
                data = json.dumps(body or {}).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                tokens_seen.add(self.headers.get('X-Vault-Token'))
                path = self.path[len('/v1/'):]
                if path == 'sys/mounts':
                    return self._send(200, {'data': mounts})
                record = records.get(path.replace('apps/data/', ''))
                self._send(404) if record is None else self._send(200, {'data': {'data': record}})

            def do_POST(self):
                tokens_seen.add(self.headers.get('X-Vault-Token'))
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records[self.path[len('/v1/'):].replace('apps/data/', '')] = body['data']
                self._send(200)

        self._server = HTTPServer(('127.0.0.1', 0), Handler)
        self.address = f'http://127.0.0.1:{self._server.server_address[1]}'
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + '\n', encoding='utf-8')


class VaultScriptTestCase(unittest.TestCase):
    """A throwaway git repository with one service, and the script run against fake Vault servers."""
    layout = ''
    single_vault = False
    base_bytes = None
    development_bytes = None
    has_development_file = True

    def setUp(self):
        self.test_vault = FakeVault()
        self.prod_vault = self.test_vault if self.single_vault else FakeVault()
        self.addCleanup(self.test_vault.stop)
        if not self.single_vault:
            self.addCleanup(self.prod_vault.stop)
        self.repository = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repository, True)
        self.project_root = self.repository / self.layout
        service = self.project_root / 'acme.Orders.Api'
        service.mkdir(parents=True, exist_ok=True)
        if self.base_bytes is None:
            write_json(service / 'appsettings.json', BASE_SETTINGS)
        else:
            (service / 'appsettings.json').write_bytes(self.base_bytes)
        if self.development_bytes is not None:
            (service / 'appsettings.Development.json').write_bytes(self.development_bytes)
        elif self.has_development_file:
            write_json(service / 'appsettings.Development.json', DEVELOPMENT_SETTINGS)
        (service / 'acme.Orders.Api.csproj').write_text('<Project />', encoding='utf-8')
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('-c', 'user.email=t@t.t', '-c', 'user.name=t', 'commit', '-q', '-m', 'baseline')
        self.baseline = self.git('rev-parse', 'HEAD').strip()
        self.settings_path = service / 'appsettings.json'

    def git(self, *arguments):
        return subprocess.run(['git', *arguments], cwd=self.repository, capture_output=True, text=True, check=True).stdout

    def run_script(self, command, *arguments, prod_token=True):
        environment = {key: value for key, value in os.environ.items() if key not in ('VAULT_TEST_TOKEN', 'VAULT_PROD_TOKEN')}
        environment['VAULT_TEST_TOKEN'] = TEST_TOKEN
        if prod_token is True:
            environment['VAULT_PROD_TOKEN'] = PROD_TOKEN
        token_file_arguments = ['--prod-token-file', str(prod_token)] if isinstance(prod_token, Path) else []
        test_address_arguments = [] if self.single_vault else ['--test-vault-address', self.test_vault.address]
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, '--project-root', str(self.project_root), '--project-name', 'acme',
             *test_address_arguments, '--prod-vault-address', self.prod_vault.address, *token_file_arguments, *arguments],
            env=environment, capture_output=True, text=True, encoding='utf-8')
        for secret in (SECRET_VALUE, TEST_TOKEN, PROD_TOKEN, FILE_TOKEN):
            self.assertNotIn(secret, result.stdout + result.stderr, 'a secret value or token must never be printed')
        return result


class VaultConfigFlowTests(VaultScriptTestCase):
    def test_prod_records_are_written_after_a_skip_prod_run(self):
        first = self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(sorted(self.test_vault.records), ['acme/local/orders-api', 'acme/test/orders-api'])
        self.assertEqual(self.prod_vault.records, {})
        self.assertNotIn(SECRET_VALUE, self.settings_path.read_text(encoding='utf-8'))

        verified = self.run_script('verify', '--baseline-ref', self.baseline, '--skip-prod', prod_token=False)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertIn('PROD NOT VERIFIED', verified.stdout)

        without_skip = self.run_script('verify', '--baseline-ref', self.baseline)
        self.assertNotEqual(without_skip.returncode, 0, 'prod records do not exist yet')

        files_before = self.settings_path.read_bytes()
        prod = self.run_script('apply', '--apply-changes', '--only-prod', '--baseline-ref', self.baseline)
        self.assertEqual(prod.returncode, 0, prod.stdout + prod.stderr)
        self.assertEqual(list(self.prod_vault.records), ['acme/prod/orders-api'])
        self.assertEqual(self.prod_vault.records['acme/prod/orders-api']['Database']['ConnectionString'], SECRET_VALUE)
        self.assertEqual(self.settings_path.read_bytes(), files_before, '--only-prod must not touch the settings files')

        final = self.run_script('verify', '--baseline-ref', self.baseline)
        self.assertEqual(final.returncode, 0, final.stdout + final.stderr)

    def test_prod_token_can_come_from_a_file_and_never_from_the_cli_token(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        token_file = self.repository / 'prod-token-file'
        token_file.write_text(FILE_TOKEN + '\n', encoding='utf-8')
        prod = self.run_script('apply', '--apply-changes', '--only-prod', '--baseline-ref', self.baseline, prod_token=token_file)
        self.assertEqual(prod.returncode, 0, prod.stdout + prod.stderr)
        self.assertEqual(self.prod_vault.tokens_seen, {FILE_TOKEN})
        self.assertNotIn(FILE_TOKEN, self.test_vault.tokens_seen)
        self.assertEqual(self.run_script('verify', '--baseline-ref', self.baseline, prod_token=token_file).returncode, 0)

    def test_empty_prod_token_file_is_reported(self):
        token_file = self.repository / 'prod-token-file'
        token_file.write_text('', encoding='utf-8')
        result = self.run_script('apply', '--only-prod', '--baseline-ref', self.baseline, prod_token=token_file)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('is empty', result.stderr)

    def test_missing_prod_token_is_reported(self):
        result = self.run_script('apply', '--only-prod', '--baseline-ref', self.baseline, prod_token=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--prod-token-file', result.stderr)

    def test_a_missing_mount_is_reported_and_never_created(self):
        self.test_vault.mounts.clear()
        for arguments in (['--skip-prod'], ['--apply-changes', '--skip-prod']):
            result = self.run_script('apply', *arguments, prod_token=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('has no "apps" mount', result.stderr)
            self.assertIn('vault secrets enable', result.stderr)
        self.assertEqual(self.test_vault.mounts, {})
        self.assertEqual(self.test_vault.records, {})
        self.assertNotIn('Vault', self.settings_path.read_text(encoding='utf-8').replace('ConnectionString', ''))

    def test_a_kv_version_1_mount_is_refused(self):
        self.test_vault.mounts['apps/']['options']['version'] = '1'
        result = self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('KV version 1', result.stderr)
        self.assertEqual(self.test_vault.records, {})

    def test_plan_on_an_already_moved_tree_points_to_the_baseline(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        plan = self.run_script('plan')
        self.assertIn('nothing to move', plan.stdout)
        self.assertIn('--baseline-ref', plan.stdout)
        from_baseline = self.run_script('plan', '--baseline-ref', self.baseline)
        self.assertIn('Database:ConnectionString', from_baseline.stdout)

    def test_verify_flags_a_secret_left_in_the_development_file(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        development_path = self.project_root / 'acme.Orders.Api' / 'appsettings.Development.json'
        development = json.loads(development_path.read_text(encoding='utf-8'))
        development['Extra'] = {'ApiKey': 'left-behind'}
        write_json(development_path, development)
        arguments = ['--baseline-ref', self.baseline, '--skip-prod', '--accept-differences', 'extra:apikey']
        flagged = self.run_script('verify', *arguments, prod_token=False)
        self.assertNotEqual(flagged.returncode, 0)
        self.assertIn('appsettings.Development.json: Extra:ApiKey', flagged.stdout)
        excluded = self.run_script('verify', *arguments, '--exclude', 'Extra:ApiKey', prod_token=False)
        self.assertEqual(excluded.returncode, 0, excluded.stdout + excluded.stderr)

    def test_second_plain_apply_warns_instead_of_pretending(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        again = self.run_script('apply', '--skip-prod', '--overwrite', prod_token=False)
        self.assertIn('already point at Vault', again.stdout)

    def test_only_prod_requires_a_baseline(self):
        result = self.run_script('apply', '--only-prod')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--baseline-ref', result.stderr)

    def test_only_prod_and_skip_prod_contradict(self):
        result = self.run_script('apply', '--only-prod', '--skip-prod', '--baseline-ref', self.baseline)
        self.assertNotEqual(result.returncode, 0)

    def test_full_apply_writes_all_three_records_and_verifies(self):
        applied = self.run_script('apply', '--apply-changes')
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual(sorted(self.prod_vault.records), ['acme/prod/orders-api'])
        self.assertEqual(self.test_vault.records['acme/local/orders-api']['Downstream']['BaseUrl'], 'http://localhost:8080')
        self.assertEqual(self.run_script('verify', '--baseline-ref', self.baseline).returncode, 0)


class NestedProjectRootTests(VaultConfigFlowTests):
    """The services live below the repository root (for example in src/): git paths must follow --project-root."""
    layout = 'src'


class SingleVaultTests(VaultScriptTestCase):
    """Only one Vault exists: it is the prod Vault and also holds the test and local records. Only --prod-vault-address is given."""
    single_vault = True

    def test_all_three_record_folders_live_on_the_one_vault(self):
        first = self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn('one Vault', first.stdout)
        self.assertEqual(sorted(self.test_vault.records), ['acme/local/orders-api', 'acme/test/orders-api'])

        token_file = self.repository / 'prod-token-file'
        token_file.write_text(FILE_TOKEN + '\n', encoding='utf-8')
        prod = self.run_script('apply', '--apply-changes', '--only-prod', '--baseline-ref', self.baseline, prod_token=token_file)
        self.assertEqual(prod.returncode, 0, prod.stdout + prod.stderr)
        self.assertEqual(sorted(self.test_vault.records), ['acme/local/orders-api', 'acme/prod/orders-api', 'acme/test/orders-api'])
        self.assertEqual(self.run_script('verify', '--baseline-ref', self.baseline, prod_token=token_file).returncode, 0)

    def test_every_settings_file_points_at_the_one_address(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        service = self.project_root / 'acme.Orders.Api'
        for file_name, folder in (('appsettings.json', 'prod'), ('appsettings.Test.json', 'test'), ('appsettings.Development.json', 'local')):
            section = json.loads((service / file_name).read_text(encoding='utf-8'))['VaultConfiguration']
            self.assertEqual(section['Address'], self.test_vault.address)
            self.assertEqual(section['Path'], f'acme/{folder}/orders-api')

    def test_next_run_finds_the_addresses_in_the_settings_files(self):
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        verified = subprocess.run(
            [sys.executable, str(SCRIPT), 'verify', '--project-root', str(self.project_root), '--project-name', 'acme',
             '--baseline-ref', self.baseline, '--skip-prod'],
            env={**os.environ, 'VAULT_TEST_TOKEN': TEST_TOKEN}, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)


HAND_FORMATTED_BASE = '''{
    "Logging": { "LogLevel": { "Default": "Information" } },
    "Database": {
        "ConnectionString": "Server=db;Password=hunter2",
        "CommandTimeoutSeconds": 30
    },
    "Tags": [ "a", "b" ],
    "Mail": {
        "SmtpPassword": "pw",
        "ApiKey": "k"
    },
    "Downstream": { "BaseUrl": "http://prod-host:8080", "Note": "Q&A \\u0026 {braces}, \\"quotes\\"" }
}
'''
HAND_FORMATTED_DEVELOPMENT = '{ "Downstream": { "BaseUrl": "http://localhost:8080" } }'


class FormattingIsPreservedTests(VaultScriptTestCase):
    """Only the moved keys disappear; indentation, inline arrays and objects, escapes, the BOM and CRLF stay exactly as they were."""
    base_bytes = b'\xef\xbb\xbf' + HAND_FORMATTED_BASE.replace('\n', '\r\n').encode('utf-8')
    development_bytes = HAND_FORMATTED_DEVELOPMENT.encode('utf-8')

    def test_untouched_content_keeps_its_exact_bytes(self):
        applied = self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        expected = f'''{{
    "Logging": {{ "LogLevel": {{ "Default": "Information" }} }},
    "Database": {{
        "CommandTimeoutSeconds": 30
    }},
    "Tags": [ "a", "b" ],
    "Downstream": {{ "Note": "Q&A \\u0026 {{braces}}, \\"quotes\\"" }},
    "VaultConfiguration": {{
        "Address": "{self.prod_vault.address}",
        "Mount": "apps",
        "Path": "acme/prod/orders-api"
    }}
}}
'''
        self.assertEqual(self.settings_path.read_bytes(), b'\xef\xbb\xbf' + expected.replace('\n', '\r\n').encode('utf-8'))

    def test_a_file_without_an_ending_newline_and_with_other_indentation_is_respected(self):
        development = self.settings_path.parent / 'appsettings.Development.json'
        self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        text = development.read_text(encoding='utf-8')
        self.assertFalse(text.endswith('\n'), 'the original had no ending newline')
        self.assertEqual(json.loads(text), {'VaultConfiguration': {'Address': self.test_vault.address, 'Path': 'acme/local/orders-api'}})
        self.assertEqual(self.run_script('verify', '--baseline-ref', self.baseline, '--skip-prod', prod_token=False).returncode, 0)


class NoDevelopmentFileTests(VaultScriptTestCase):
    """A service that has no appsettings.Development.json at all still moves its secrets and gets all three settings files."""
    has_development_file = False

    def test_the_missing_files_are_created(self):
        applied = self.run_script('apply', '--apply-changes', '--skip-prod', prod_token=False)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        service = self.project_root / 'acme.Orders.Api'
        development = json.loads((service / 'appsettings.Development.json').read_text(encoding='utf-8'))
        self.assertEqual(development['VaultConfiguration']['Path'], 'acme/local/orders-api')
        self.assertEqual(self.run_script('verify', '--baseline-ref', self.baseline, '--skip-prod', prod_token=False).returncode, 0)


sys.path.insert(0, str(SCRIPT.parent))
from vault_config import JsonText  # noqa: E402


class JsonTextTests(unittest.TestCase):
    SECTION = {'Address': 'http://v', 'Path': 'p'}

    def edit(self, text, moved):
        edited = JsonText(text).without(moved, 'VaultConfiguration', self.SECTION)
        return edited, json.loads(edited)

    def test_a_run_of_members_at_the_end_leaves_no_trailing_comma(self):
        edited, parsed = self.edit('{"a": 1, "b": 2, "c": 3}', [('b',), ('c',)])
        self.assertEqual(parsed, {'a': 1, 'VaultConfiguration': self.SECTION})
        self.assertTrue(edited.startswith('{"a": 1,'))

    def test_a_run_in_the_middle_keeps_the_neighbours(self):
        _, parsed = self.edit('{"a": 1,\n "b": 2,\n "c": 3,\n "d": 4}', [('b',), ('c',)])
        self.assertEqual(parsed, {'a': 1, 'd': 4, 'VaultConfiguration': self.SECTION})

    def test_every_member_moved_leaves_only_the_section(self):
        edited, parsed = self.edit('{\n  "a": 1,\n  "b": {"c": 2}\n}\n', [('a',), ('b', 'c')])
        self.assertEqual(parsed, {'VaultConfiguration': self.SECTION})
        self.assertTrue(edited.endswith('}\n'))

    def test_an_object_that_becomes_empty_is_removed_with_its_name(self):
        _, parsed = self.edit('{"keep": {"x": 1}, "gone": {"y": {"z": 2}}, "also": 3}', [('gone', 'y', 'z')])
        self.assertEqual(parsed, {'keep': {'x': 1}, 'also': 3, 'VaultConfiguration': self.SECTION})

    def test_an_object_that_was_empty_before_is_left_alone(self):
        _, parsed = self.edit('{"empty": {}, "a": 1}', [('a',)])
        self.assertEqual(parsed, {'empty': {}, 'VaultConfiguration': self.SECTION})

    def test_an_existing_section_is_replaced_in_place(self):
        edited, parsed = self.edit('{\n  "VaultConfiguration": {"Address": "old"},\n  "a": 1\n}', [])
        self.assertEqual(parsed, {'VaultConfiguration': self.SECTION, 'a': 1})
        self.assertLess(edited.index('VaultConfiguration'), edited.index('"a"'))

    def test_strings_that_look_like_json_do_not_confuse_the_parser(self):
        tricky = '{"a": "x, } ] { \\" y", "b": [1, {"c": "}"}], "secret": "s"}'
        _, parsed = self.edit(tricky, [('secret',)])
        self.assertEqual(parsed, {'a': 'x, } ] { " y', 'b': [1, {'c': '}'}], 'VaultConfiguration': self.SECTION})

    def test_text_that_is_not_strict_json_is_refused(self):
        for text in ('{"a": 1,}', '[1, 2]', '{"a": 1} trailing', '{"a" 1}', '{"a": 1'):
            with self.assertRaises((ValueError, IndexError), msg=text):
                JsonText(text).without([], 'VaultConfiguration', self.SECTION)


if __name__ == '__main__':
    unittest.main()
