#!/usr/bin/env python3
"""Move a .NET project's secret and per-reader settings out of appsettings files and into HashiCorp Vault records.

The pinq-doq Vault configuration standard (references/dotnet/vault-configuration.md) has three readers, each
with its own record per service:

    prod server    -> prod Vault  <mount>/<project>/prod/<service>    (appsettings.json)
    test server    -> test Vault  <mount>/<project>/test/<service>    (appsettings.Test.json)
    developer      -> test Vault  <mount>/<project>/local/<service>   (appsettings.Development.json)

Subcommands (stdlib only, no third-party packages; run from anywhere with --project-root):

    plan     Read the settings files and show which keys would move to Vault, and why. Writes nothing.
    apply    Write the three records per service, then rewrite the settings files. Dry run unless --apply-changes.
    verify   Check that every reader still sees exactly the settings it saw before the move.
    check    Developer preflight on a project that is already moved: can this machine, with the login `vault login`
             saved (or VAULT_TOKEN), read the records its services need, and if not, why. Writes nothing.

Secrets are never printed and never passed on the command line. The test Vault token comes from VAULT_TEST_TOKEN or,
when that is unset, from the token `vault login` saved in ~/.vault-token; the prod Vault token must be given in
VAULT_PROD_TOKEN or in a file named by --prod-token-file (a prod write is deliberate: ~/.vault-token is never used for
prod). Output shows key names, types and counts only.

Typical use:
    python vault_config.py plan   --project-root <repo> --project-name <name>
    python vault_config.py apply  --project-root <repo> --project-name <name> --apply-changes
    python vault_config.py verify --project-root <repo> --project-name <name> --baseline-ref <git ref before the move>
    python vault_config.py check  --project-root <repo> --project-name <name>
"""
import argparse
import copy
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MOUNT = 'apps'
DEFAULT_TEST_TOKEN_ENV = 'VAULT_TEST_TOKEN'
DEFAULT_PROD_TOKEN_ENV = 'VAULT_PROD_TOKEN'
VAULT_SECTION = 'VaultConfiguration'
READERS = ('prod', 'test', 'local')

# A key is treated as a secret when its last segment looks like one, unless it clearly names a duration or a size
# (RefreshTokenExpirationMinutes, MaxDeviceTokensPerRequest). The plan lists every decision, so a wrong guess is
# corrected with --include / --exclude rather than silently applied.
SECRET_NAME = re.compile(r'secret|password|passwd|token|accesskey|apikey|credential|privatekey|signingkey|encryptionkey|connectionstring', re.IGNORECASE)
NOT_SECRET_SUFFIX = re.compile(r'(minutes|seconds|days|hours|ttl|length|count|size|limit|perrequest|enabled|expiration)$', re.IGNORECASE)
NEVER_MOVED_SECTIONS = ('Logging', 'AllowedHosts', VAULT_SECTION)

EXIT_PROBLEM = 1


class ConfigurationProblem(Exception):
    pass


# --------------------------------------------------------------------------- settings files

class JsonText:
    """Edits a settings file as text: the moved keys are cut out and the Vault section is added or replaced, and every
    other byte (indentation, inline arrays, key order, escapes, line endings) stays as it was. Strict JSON only; any
    surprise raises ValueError and the caller falls back to rewriting the whole file."""

    WHITESPACE = ' \t\r\n'

    def __init__(self, text):
        self.text = text

    def without(self, moved_paths, section_name, section):
        root = self._value(0)
        if root['members'] is None or self._skip(root['end']) != len(self.text):
            raise ValueError('not a JSON object')
        members = root['members']
        _, edits, removed = self._plan(root, (), {tuple(path) for path in moved_paths})
        newline = '\r\n' if '\r\n' in self.text else '\n'
        indent = self._indent(root)
        rendered = json.dumps(section, indent=indent, ensure_ascii=False).replace('\n', newline + indent)

        existing = [member for member in members if member['key'] == section_name]
        if existing:
            edits.append((existing[0]['value']['start'], existing[0]['value']['end'], rendered))
        else:
            member_text = f'"{section_name}": {rendered}'
            remaining = [member for member, is_removed in zip(members, removed) if not is_removed]
            if not remaining:
                return f'{self.text[:root["start"]]}{{{newline}{indent}{member_text}{newline}}}{self.text[root["end"]:]}'
            edits.append((remaining[-1]['end'], remaining[-1]['end'], f',{newline}{indent}{member_text}'))

        text = self.text
        for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
            text = text[:start] + replacement + text[end:]
        return text

    def _plan(self, node, prefix, moved):
        """Returns (every member moved, edits, which members were removed). An object whose members all move goes with them."""
        members = node['members']
        removed = []
        edits = []
        for member in members:
            path = prefix + (member['key'],)
            value = member['value']
            if path in moved:
                removed.append(True)
                continue
            if value['members']:
                everything, child_edits, _ = self._plan(value, path, moved)
                if everything:
                    removed.append(True)
                    continue
                edits.extend(child_edits)
            removed.append(False)

        index = 0
        while index < len(members):
            if not removed[index]:
                index += 1
                continue
            last = index
            while last + 1 < len(members) and removed[last + 1]:
                last += 1
            if last + 1 < len(members):
                edits.append((members[index]['start'], members[last + 1]['start'], ''))
            elif index > 0:
                edits.append((members[index - 1]['end'], members[last]['end'], ''))
            index = last + 1
        return bool(members) and all(removed), edits, removed

    def _indent(self, root):
        if not root['members']:
            return '  '
        first = root['members'][0]['start']
        prefix = self.text[self.text.rfind('\n', 0, first) + 1:first]
        return prefix if prefix and not prefix.strip() else '  '

    def _skip(self, index):
        while index < len(self.text) and self.text[index] in self.WHITESPACE:
            index += 1
        return index

    def _string_end(self, index):
        index += 1
        while self.text[index] != '"':
            index += 2 if self.text[index] == '\\' else 1
        return index + 1

    def _value(self, index):
        index = self._skip(index)
        character = self.text[index]
        if character == '{':
            return self._object(index)
        if character == '[':
            return self._array(index)
        if character == '"':
            return {'members': None, 'start': index, 'end': self._string_end(index)}
        end = index
        while end < len(self.text) and self.text[end] not in ',]} \t\r\n':
            end += 1
        if end == index:
            raise ValueError('value expected')
        return {'members': None, 'start': index, 'end': end}

    def _array(self, start):
        index = self._skip(start + 1)
        if self.text[index] == ']':
            return {'members': None, 'start': start, 'end': index + 1}
        while True:
            index = self._skip(self._value(index)['end'])
            if self.text[index] == ',':
                index = self._skip(index + 1)
            elif self.text[index] == ']':
                return {'members': None, 'start': start, 'end': index + 1}
            else:
                raise ValueError('array not closed')

    def _object(self, start):
        members = []
        index = self._skip(start + 1)
        if self.text[index] == '}':
            return {'members': members, 'start': start, 'end': index + 1}
        while True:
            if self.text[index] != '"':
                raise ValueError('key expected')
            key_end = self._string_end(index)
            colon = self._skip(key_end)
            if self.text[colon] != ':':
                raise ValueError('colon expected')
            value = self._value(colon + 1)
            members.append({'key': json.loads(self.text[index:key_end]), 'start': index, 'end': value['end'], 'value': value})
            after = self._skip(value['end'])
            if self.text[after] == ',':
                index = self._skip(after + 1)
            elif self.text[after] == '}':
                return {'members': members, 'start': start, 'end': after + 1}
            else:
                raise ValueError('object not closed')


class SettingsFile:
    def __init__(self, path, content, has_bom=False, uses_crlf=False, ends_with_newline=True, text=None):
        self.path = Path(path)
        self.content = content
        self.has_bom = has_bom
        self.uses_crlf = uses_crlf
        self.ends_with_newline = ends_with_newline
        self.text = text

    @classmethod
    def read(cls, path):
        raw = Path(path).read_bytes()
        has_bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig' if has_bom else 'utf-8')
        return cls(path, json.loads(text), has_bom, '\r\n' in text, text.endswith('\n'), text)

    def rewrite_without(self, moved_paths, section_name, section):
        """Cuts the moved keys out and sets the Vault section, leaving the rest of the file as it was. When the text
        edit cannot be proven to give the intended settings, the whole file is rewritten instead."""
        expected = copy.deepcopy(self.content)
        for path in moved_paths:
            remove_path(expected, path)
        expected[section_name] = copy.deepcopy(section)
        new_text = None
        if self.text is not None:
            try:
                new_text = JsonText(self.text).without(moved_paths, section_name, section)
                if json.loads(new_text) != expected:
                    new_text = None
            except (ValueError, IndexError):
                new_text = None
        if new_text is None:
            self.content = expected
            self.write()
            return
        self.path.write_bytes((b'\xef\xbb\xbf' if self.has_bom else b'') + new_text.encode('utf-8'))

    @classmethod
    def read_at_git_ref(cls, repo_root, git_ref, relative_path):
        # "./" makes the path relative to repo_root, so a project root below the repository root works too.
        shown = subprocess.run(['git', '-C', str(repo_root), 'show', f'{git_ref}:./{relative_path}'], capture_output=True)
        if shown.returncode != 0:
            return cls(repo_root / relative_path, {})
        raw = shown.stdout
        has_bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig' if has_bom else 'utf-8')
        return cls(repo_root / relative_path, json.loads(text), has_bom, '\r\n' in text, text.endswith('\n'))

    def write(self):
        text = json.dumps(self.content, indent=2, ensure_ascii=False) + ('\n' if self.ends_with_newline else '')
        if self.uses_crlf:
            text = text.replace('\n', '\r\n')
        self.path.write_bytes((b'\xef\xbb\xbf' if self.has_bom else b'') + text.encode('utf-8'))


def leaves(node, prefix=()):
    """Maps every leaf to its path. A JSON array is one leaf, because it has to move as a whole."""
    found = {}
    for key, value in node.items():
        if isinstance(value, dict):
            found.update(leaves(value, prefix + (key,)))
        else:
            found[prefix + (key,)] = value
    return found


def get_path(node, path):
    for segment in path:
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node


def set_path(node, path, value):
    for segment in path[:-1]:
        node = node.setdefault(segment, {})
    node[path[-1]] = copy.deepcopy(value)


def remove_path(node, path):
    """Removes a leaf and any section that becomes empty because of it."""
    if not isinstance(node, dict) or path[0] not in node:
        return
    if len(path) == 1:
        del node[path[0]]
        return
    remove_path(node[path[0]], path[1:])
    if node[path[0]] == {}:
        del node[path[0]]


def flatten_like_dotnet(node, prefix=''):
    """Flattens JSON the way .NET configuration does: ':' separated keys, arrays by index, keys case-insensitive."""
    flat = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(flatten_like_dotnet(value, f'{prefix}:{key}' if prefix else key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            flat.update(flatten_like_dotnet(value, f'{prefix}:{index}'))
    elif isinstance(node, bool):
        flat[prefix.lower()] = 'true' if node else 'false'
    else:
        flat[prefix.lower()] = None if node is None else str(node)
    return flat


def effective_settings(*layers):
    """What the application sees: later layers override earlier ones. Vault location keys are left out of comparisons."""
    merged = {}
    for layer in layers:
        merged.update(flatten_like_dotnet(layer))
    return {key: value for key, value in merged.items() if not key.startswith(VAULT_SECTION.lower() + ':')}


# --------------------------------------------------------------------------- classification

def matches_any(dotted_key, patterns):
    lowered = dotted_key.lower()
    return any(fnmatch.fnmatch(lowered, pattern.lower()) or lowered.startswith(pattern.lower() + ':') for pattern in patterns)


def is_secret_looking(path, value):
    return (isinstance(value, str) and value != '' and bool(SECRET_NAME.search(path[-1]))
            and not NOT_SECRET_SUFFIX.search(path[-1]))


def merge_arrays_like_dotnet(base_array, development_array):
    """.NET merges two arrays defined in different files by index, so a shorter Development array keeps the
    base array's remaining elements."""
    merged = list(base_array)
    for index, element in enumerate(development_array):
        if index < len(merged):
            merged[index] = element
        else:
            merged.append(element)
    return merged


def local_value(base_leaves, development_leaves, path):
    """The value a developer machine sees. An empty string in the Development file does not hide a real base value."""
    base_value, development_value = base_leaves.get(path), development_leaves.get(path)
    if isinstance(base_value, list) and isinstance(development_value, list):
        return merge_arrays_like_dotnet(base_value, development_value)
    if path in development_leaves and development_value != '':
        return development_value
    return base_value if path in base_leaves else development_value


def select_keys(base, development, include, exclude):
    """Returns {path: reason} for the keys that move to Vault."""
    base_leaves, development_leaves = leaves(base), leaves(development)
    selected = {}
    for path in dict.fromkeys(list(base_leaves) + list(development_leaves)):
        dotted_key = ':'.join(path)
        if path[0] in NEVER_MOVED_SECTIONS or matches_any(dotted_key, exclude):
            continue
        if matches_any(dotted_key, include):
            selected[path] = 'included'
        elif is_secret_looking(path, local_value(base_leaves, development_leaves, path)):
            selected[path] = 'secret'
        elif path in development_leaves and development_leaves[path] not in ('', base_leaves.get(path)):
            selected[path] = 'differs between server and developer machine'
    return selected


def build_records(base, development, selected_paths, test_from):
    base_leaves, development_leaves = leaves(base), leaves(development)
    prod, local, warnings = {}, {}, []
    for path in selected_paths:
        if path in base_leaves:
            set_path(prod, path, base_leaves[path])
        else:
            warnings.append(f'{":".join(path)} exists only in the Development file: prod and test records will not have it')
        set_path(local, path, local_value(base_leaves, development_leaves, path))
        base_value, development_value = base_leaves.get(path), development_leaves.get(path)
        if isinstance(base_value, list) and isinstance(development_value, list) and len(base_value) != len(development_value):
            warnings.append(f'{":".join(path)}: the Development array has {len(development_value)} elements and the base array {len(base_value)}; '
                            f'.NET merges them by index, so the local record keeps the merged result. Review it.')
    test = copy.deepcopy(prod if test_from == 'prod' else local)
    return {'prod': prod, 'test': test, 'local': local}, warnings


# --------------------------------------------------------------------------- Vault

class Vault:
    def __init__(self, label, address, token):
        self.label = label
        self.address = address.rstrip('/')
        self._token = token

    def call(self, method, path, payload=None):
        request = urllib.request.Request(
            f'{self.address}/v1/{path}', method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'X-Vault-Token': self._token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read()
                return response.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as error:
            return error.code, {}
        except urllib.error.URLError as error:
            raise ConfigurationProblem(f'{self.label} Vault at {self.address} is unreachable: {error.reason}') from error

    def read_record(self, mount, record_path):
        status, body = self.call('GET', f'{mount}/data/{record_path}')
        if status == 200:
            return body['data']['data']
        if status == 404:
            return None
        raise ConfigurationProblem(f'{self.label} Vault answered {status} for {mount}/{record_path}: the token may lack read access')

    def write_record(self, mount, record_path, record):
        status, _ = self.call('POST', f'{mount}/data/{record_path}', {'data': record})
        if status != 200:
            raise ConfigurationProblem(f'{self.label} Vault answered {status} when writing {mount}/{record_path}: '
                                       f'check that the {mount} mount exists as KV version 2 and that the token may write there')

    def check_kv2_mount(self, mount):
        """The records live in a KV v2 mount that a Vault administrator creates; this script never creates one."""
        status, body = self.call('GET', 'sys/mounts')
        if status != 200:
            return  # the token may not be allowed to list mounts; a missing mount then shows up when the first record is written
        mounts = body.get('data', body)
        info = mounts.get(f'{mount}/')
        if info is None:
            raise ConfigurationProblem(f'The {self.label} Vault has no "{mount}" mount. Ask a Vault administrator to create it: '
                                       f'vault secrets enable -address={self.address} -path={mount} -version=2 kv')
        version = (info.get('options') or {}).get('version')
        if version not in (None, '2'):
            raise ConfigurationProblem(f'The "{mount}" mount on the {self.label} Vault is KV version {version}; the records need version 2.')


def read_cli_token():
    """The token the Vault CLI saved on `vault login`: the same file Pinqponq.Configuration.Vault reads."""
    token_file = Path.home() / '.vault-token'
    return token_file.read_text(encoding='utf-8').strip() if token_file.is_file() else None


def read_token_file(token_file):
    """A token the user saved on purpose for this run (for example with `vault login -no-store -token-only`)."""
    path = Path(token_file).expanduser()
    if not path.is_file():
        raise ConfigurationProblem(f'Token file {path} does not exist.')
    token = path.read_text(encoding='utf-8-sig').strip()
    if not token:
        raise ConfigurationProblem(f'Token file {path} is empty: the login that should have written it did not succeed.')
    return token


def connect(label, address, token_env, allow_cli_token=False, token_file=None):
    token = os.environ.get(token_env) or (read_token_file(token_file) if token_file else None) or (read_cli_token() if allow_cli_token else None)
    if not token:
        hint = (f' (or run `vault login` against the {label} Vault)' if allow_cli_token
                else ' or pass --prod-token-file (a prod write is deliberate: the token the Vault CLI saved on login is not used for it)')
        raise ConfigurationProblem(f'Set the {token_env} environment variable to a {label} Vault token{hint}. Never pass a token on the command line.')
    if not address:
        only_one = ' With a single Vault, pass only --prod-vault-address.' if label == 'test' else ''
        raise ConfigurationProblem(f'No {label} Vault address: pass --{label}-vault-address or set {VAULT_SECTION}:Address in the settings files.{only_one}')
    return Vault(label, address, token)


# --------------------------------------------------------------------------- project discovery

class Service:
    def __init__(self, root, directory, record_name):
        self.root = root
        self.directory = directory
        self.record_name = record_name
        self.base_path = root / directory / 'appsettings.json'
        self.development_path = root / directory / 'appsettings.Development.json'
        self.test_path = root / directory / 'appsettings.Test.json'
        self.relative_base = f'{directory}/appsettings.json'
        self.relative_development = f'{directory}/appsettings.Development.json'

    def record_path(self, project_name, reader):
        return f'{project_name}/{reader}/{self.record_name}'


def discover_services(root, project_name, only):
    services = []
    prefix = f'{project_name}.'.lower()
    for child in sorted(root.iterdir()):
        if not (child / 'appsettings.json').is_file() or not list(child.glob('*.csproj')):
            continue
        name = child.name
        record_name = (name[len(prefix):] if name.lower().startswith(prefix) else name).lower().replace('.', '-')
        if only and record_name not in only:
            continue
        services.append(Service(root, name, record_name))
    if not services:
        raise ConfigurationProblem(f'No service with an appsettings.json and a .csproj found under {root}.')
    return services


def read_vault_address(service, which):
    path = service.base_path if which == 'prod' else service.development_path
    return get_path(SettingsFile.read(path).content, (VAULT_SECTION, 'Address')) if path.is_file() else None


def resolve_vaults(arguments, services, need_prod=True):
    """One Vault or two. The prod address is the one every project has; a test Vault is a second server that may not exist.
    No test address anywhere (flag, settings files) means a single Vault, which is then treated as the prod Vault and also
    holds the test and local records."""
    prod_address = arguments.prod_vault_address or read_vault_address(services[0], 'prod')
    test_address = arguments.test_vault_address or read_vault_address(services[0], 'test') or prod_address
    if prod_address and test_address == prod_address:
        print(f'note: one Vault at {prod_address} holds the prod, test and local records.')
    test_vault = connect('test', test_address, arguments.test_token_env, allow_cli_token=True)
    prod_vault = connect('prod', prod_address, arguments.prod_token_env, token_file=arguments.prod_token_file) if need_prod else None
    return test_vault, prod_vault


# --------------------------------------------------------------------------- subcommands

def read_settings_to_move(service, baseline_ref):
    """The settings the plan is built from: the working tree, or the commit from before the move.

    After a first `apply` the working tree no longer holds the secrets, so a later run (the prod records) has to
    read the baseline commit instead.
    """
    if baseline_ref is None:
        base = SettingsFile.read(service.base_path).content
        development = SettingsFile.read(service.development_path).content if service.development_path.is_file() else {}
        return base, development
    base = SettingsFile.read_at_git_ref(service.root, baseline_ref, service.relative_base).content
    if not base:
        raise ConfigurationProblem(f'{service.relative_base} was not found at {baseline_ref}: check --baseline-ref and --project-root.')
    development = SettingsFile.read_at_git_ref(service.root, baseline_ref, service.relative_development).content
    return base, development


def plan_for(service, arguments):
    base, development = read_settings_to_move(service, arguments.baseline_ref)
    selected = select_keys(base, development, arguments.include, arguments.exclude)
    records, warnings = build_records(base, development, list(selected), arguments.test_from)
    return base, development, selected, records, warnings


def describe_value(value):
    return f'array of {len(value)}' if isinstance(value, list) else type(value).__name__


def warn_about_project_name(project_name):
    if project_name != project_name.lower():
        print(f'note: the project name "{project_name}" has upper-case letters. Vault paths are case sensitive and the standard spells '
              f'the project name in lower case ("{project_name.lower()}"): use that, unless records with this exact spelling already exist.')


def command_plan(arguments):
    warn_about_project_name(arguments.project_name)
    root = Path(arguments.project_root).resolve()
    services = discover_services(root, arguments.project_name, arguments.only)
    for service in services:
        base, _, selected, records, warnings = plan_for(service, arguments)
        print(f'\n{service.directory}  ->  record "{service.record_name}"')
        if not selected:
            print('   nothing to move')
            if VAULT_SECTION in base and not arguments.baseline_ref:
                warnings.append('the settings files already point at Vault. To plan from the commit before the move, pass --baseline-ref <that commit>.')
        for path, reason in selected.items():
            value = get_path(records['local'], path)
            print(f'   {":".join(path):62} {describe_value(value):12} {reason}')
        for warning in warnings:
            print(f'   WARNING: {warning}')
    print('\nPLAN ONLY - nothing was written. Adjust with --include / --exclude (patterns on the ":" separated key).')


def preflight(base, development, records, test_settings):
    """Every reader must see the same settings after the move as before. The test server is expected to match prod."""
    new_base, new_development = copy.deepcopy(base), copy.deepcopy(development)
    for path in leaves(records['local']):
        remove_path(new_base, path)
        remove_path(new_development, path)

    local_before = effective_settings(base, development)
    prod_before = effective_settings(base)
    local_after = effective_settings(new_base, new_development, records['local'])
    prod_after = effective_settings(new_base, records['prod'])
    test_after = effective_settings(new_base, test_settings, records['test'])
    return {
        'local': differing_keys(local_before, local_after),
        'prod': differing_keys(prod_before, prod_after),
        'test': differing_keys(prod_before, test_after),
    }


def differing_keys(before, after):
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def command_apply(arguments):
    warn_about_project_name(arguments.project_name)
    root = Path(arguments.project_root).resolve()
    if arguments.only_prod and arguments.skip_prod:
        raise ConfigurationProblem('--only-prod and --skip-prod contradict each other.')
    if arguments.only_prod and not arguments.baseline_ref:
        raise ConfigurationProblem('--only-prod needs --baseline-ref: after the first apply the settings files no longer hold the values, '
                                   'so the prod records are built from the commit from before the move.')
    services = discover_services(root, arguments.project_name, arguments.only)
    test_vault, prod_vault = resolve_vaults(arguments, services, need_prod=not arguments.skip_prod)
    prod_address = prod_vault.address if prod_vault else (arguments.prod_vault_address or read_vault_address(services[0], 'prod'))
    if not prod_address:
        raise ConfigurationProblem(f'No prod Vault address: pass --prod-vault-address or set {VAULT_SECTION}:Address in the settings files.')
    mount, project_name = arguments.mount, arguments.project_name
    writers = [(reader, vault) for reader, vault in (('prod', prod_vault), ('test', test_vault), ('local', test_vault))
               if vault and (reader == 'prod' or not arguments.only_prod)]

    for vault in dict.fromkeys(vault for _, vault in writers):
        vault.check_kv2_mount(mount)

    work = []
    for service in services:
        base, development, selected, records, warnings = plan_for(service, arguments)
        test_settings = {VAULT_SECTION: {'Address': test_vault.address, 'Path': service.record_path(project_name, 'test')}}
        differences = preflight(base, development, records, test_settings)
        problems = [f'{reader} reader would see different values for: {", ".join(keys)}' for reader, keys in differences.items() if keys]
        existing = [f'{vault.label}:{mount}/{service.record_path(project_name, reader)}'
                    for reader, vault in writers
                    if not arguments.overwrite and vault.read_record(mount, service.record_path(project_name, reader)) is not None]
        if not selected and VAULT_SECTION in base and not arguments.baseline_ref:
            warnings.append('nothing to move: the settings files already point at Vault. To (re)build the records from the commit '
                            'before the move, pass --baseline-ref <that commit>.')
        print(f'\n{service.directory}: {len(selected)} keys -> records {"/".join(reader for reader, _ in writers)}', end='')
        if problems or existing:
            print('   BLOCKED')
            for problem in problems:
                print(f'   {problem}')
            for record in existing:
                print(f'   record already exists (use --overwrite): {record}')
        else:
            print('   checks passed (every reader sees the same settings as before)')
        for warning in warnings:
            print(f'   WARNING: {warning}')
        work.append((service, records, bool(problems or existing), bool(selected)))

    if any(blocked for _, _, blocked, _ in work):
        raise ConfigurationProblem('Nothing was written: fix the blocked services first.')
    if not arguments.apply_changes:
        what = 'the prod records' if arguments.only_prod else 'the records and rewrite the settings files'
        print(f'\nDRY RUN - nothing was written. Re-run with --apply-changes to write {what}.')
        return

    for service, records, _, has_keys in work:
        if not has_keys:
            continue
        for reader, vault in writers:
            vault.write_record(mount, service.record_path(project_name, reader), records[reader])
        if not arguments.only_prod:
            rewrite_settings_files(service, records['local'], prod_address, test_vault.address, mount, project_name)
        print(f'written: {service.directory}')
    if arguments.skip_prod:
        print('\nThe prod Vault was NOT touched: the prod records do not exist yet and appsettings.json already points at them. '
              'After testing, create them with: apply --apply-changes --only-prod --baseline-ref <commit from before the move>.')
    print('\nAPPLIED. Now wire the package into each service (see the pinq_vault-config-setup skill), then run: verify'
          + (' --skip-prod' if arguments.skip_prod else ''))


def rewrite_settings_files(service, moved_values, prod_address, test_address, mount, project_name):
    """Removes the moved keys from the files as they are now and points them at the records. Safe to repeat."""
    base_file = SettingsFile.read(service.base_path)
    development_file = (SettingsFile.read(service.development_path) if service.development_path.is_file()
                        else SettingsFile(service.development_path, {}, base_file.has_bom, base_file.uses_crlf))
    moved_paths = list(leaves(moved_values))
    base_file.rewrite_without(moved_paths, VAULT_SECTION, {'Address': prod_address, 'Mount': mount, 'Path': service.record_path(project_name, 'prod')})
    development_file.rewrite_without(moved_paths, VAULT_SECTION, {'Address': test_address, 'Path': service.record_path(project_name, 'local')})
    SettingsFile(service.test_path, {VAULT_SECTION: {'Address': test_address, 'Path': service.record_path(project_name, 'test')}},
                 base_file.has_bom, base_file.uses_crlf, base_file.ends_with_newline).write()


def command_verify(arguments):
    root = Path(arguments.project_root).resolve()
    services = discover_services(root, arguments.project_name, arguments.only)
    test_vault, prod_vault = resolve_vaults(arguments, services, need_prod=not arguments.skip_prod)
    mount, project_name = arguments.mount, arguments.project_name
    readers = [reader for reader in READERS if not (arguments.skip_prod and reader == 'prod')]
    failures = 0
    for service in services:
        base_before = SettingsFile.read_at_git_ref(root, arguments.baseline_ref, service.relative_base).content
        development_before = SettingsFile.read_at_git_ref(root, arguments.baseline_ref, service.relative_development).content
        base_now = SettingsFile.read(service.base_path).content
        development_now = SettingsFile.read(service.development_path).content if service.development_path.is_file() else {}
        test_now = SettingsFile.read(service.test_path).content if service.test_path.is_file() else {}
        records = {reader: (prod_vault if reader == 'prod' else test_vault).read_record(mount, service.record_path(project_name, reader)) for reader in readers}
        missing = [reader for reader, record in records.items() if record is None]
        if missing:
            failures += 1
            print(f'FAIL  {service.directory}: no record for {", ".join(missing)}')
            continue

        local_before = effective_settings(base_before, development_before)
        prod_before = effective_settings(base_before)
        local_after = effective_settings(base_now, development_now, records['local'])
        test_after = effective_settings(base_now, test_now, records['test'])
        differences = {
            'local': differing_keys(local_before, local_after),
            'test': differing_keys(prod_before, test_after),
        }
        if 'prod' in readers:
            differences['prod'] = differing_keys(prod_before, effective_settings(base_now, records['prod']))
        accepted = {reader: [key for key in keys if matches_any(key, arguments.accept_differences)] for reader, keys in differences.items()}
        differences = {reader: [key for key in keys if key not in accepted[reader]] for reader, keys in differences.items()}
        left_in_files = [f'{file_name}: {":".join(path)}'
                         for file_name, content in (('appsettings.json', base_now), ('appsettings.Development.json', development_now))
                         for path, value in leaves(content).items()
                         if path[0] != VAULT_SECTION and is_secret_looking(path, value) and not matches_any(':'.join(path), arguments.exclude)]
        ok = not any(differences.values()) and not left_in_files
        failures += not ok
        prod_unchanged = 'not checked' if arguments.skip_prod else not differences['prod']
        print(f'{"PASS" if ok else "FAIL"}  {service.directory:34} keys in records: {len(leaves(records["local"])):3}  '
              f'prod unchanged: {prod_unchanged}  local unchanged: {not differences["local"]}  test matches prod: {not differences["test"]}')
        for reader, keys in differences.items():
            if keys:
                print(f'      {reader} differs: {", ".join(keys)}')
        for reader, keys in accepted.items():
            if keys:
                print(f'      {reader} accepted differences ({len(keys)}): {", ".join(keys)}')
        if left_in_files:
            print(f'      secret-looking values still in the settings files: {", ".join(left_in_files)}')
    print('ALL CHECKED SERVICES VERIFIED' if not failures else f'{failures} SERVICE(S) NEED ATTENTION')
    if arguments.skip_prod:
        print('PROD NOT VERIFIED: once the prod records are written, run verify again without --skip-prod.')
    return EXIT_PROBLEM if failures else 0


# --------------------------------------------------------------------------- entry point

def settings_location(service, reader):
    """The VaultConfiguration section the way .NET sees it for a reader: the base file with the environment file laid over it."""
    layers = [service.base_path, service.development_path if reader == 'local' else service.test_path]
    location = {}
    for layer_path in layers:
        section = get_path(SettingsFile.read(layer_path).content, (VAULT_SECTION,)) if layer_path.is_file() else None
        if isinstance(section, dict):
            location.update(section)
    return location


def probe_address(vault, token):
    """Why this machine and this login cannot use the Vault at all, or None. Reads no record and prints no token."""
    try:
        status, _ = vault.call('GET', 'sys/health')
    except ConfigurationProblem:
        return ('UNREACHABLE', f'Connect the VPN, then open {vault.address} in a browser.')
    if status == 503:
        return ('SEALED', f'The Vault at {vault.address} is sealed: tell the DevOps unit.')
    if status not in (200, 429, 472, 473):
        return (f'UNEXPECTED (status {status})', f'The Vault at {vault.address} answered an unexpected health status: tell the DevOps unit.')
    if not token:
        return ('NO TOKEN', f'Log in: vault login -address={vault.address} -method=userpass username=<your user name>')
    status, _ = vault.call('GET', 'auth/token/lookup-self')
    if status in (401, 403):
        return ('TOKEN REJECTED', f'The login has expired or was made against another Vault: log in again with vault login -address={vault.address} -method=userpass username=<your user name>')
    if status != 200:
        return (f'UNEXPECTED (status {status})', f'The Vault at {vault.address} could not check the login: tell the DevOps unit.')
    return None


def command_check(arguments):
    """Developer preflight: can this machine, with this login, read the records the services need?"""
    root = Path(arguments.project_root).resolve()
    services = discover_services(root, arguments.project_name, arguments.only)
    token = os.environ.get('VAULT_TOKEN') or read_cli_token()
    print(f'Vault check for the "{arguments.reader}" reader (settings: '
          f'{"appsettings.Development.json" if arguments.reader == "local" else "appsettings.Test.json"}). Nothing is written, no token or value is printed.')
    vaults, address_problems, hints = {}, {}, {}
    failures = reading = 0
    for service in services:
        location = settings_location(service, arguments.reader)
        address, mount, path = location.get('Address'), location.get('Mount'), location.get('Path')
        if not (address and mount and path):
            print(f'SKIP  {service.directory:34} the settings hold no complete VaultConfiguration: this service does not read from Vault')
            continue
        reading += 1
        if address not in vaults:
            vaults[address] = Vault('check', address, token or '')
            address_problems[address] = probe_address(vaults[address], token)
        problem = address_problems[address]
        if not problem:
            status, body = vaults[address].call('GET', f'{mount}/data/{path}')
            project = path.split('/')[0]
            if status == 200:
                print(f'PASS  {service.directory:34} {mount}/{path} ({len(leaves(body["data"]["data"]))} keys)')
                continue
            if status == 404:
                problem = ('MISSING RECORD', 'The record does not exist yet: ask the DevOps unit (or whoever moved the project to Vault) to create it.')
            elif status == 403:
                problem = ('NO ACCESS', f'Your account may not read {mount}/data/{path}: ask the DevOps unit for read access to {mount}/data/{project}/local/*.')
            else:
                problem = (f'UNEXPECTED (status {status})', f'Vault answered {status} for {mount}/{path}: tell the DevOps unit.')
        failures += 1
        print(f'FAIL  {service.directory:34} {problem[0]}')
        hints.setdefault(problem[1], None)
    if not reading:
        print('No service reads from Vault in this repository yet: the project has not been moved (pinq_vault-config-setup).')
    if hints:
        print('\nWhat to do:')
        for hint in hints:
            print(f'  - {hint}')
    print('ALL SERVICES CAN READ THEIR RECORDS' if reading and not failures else f'{failures} SERVICE(S) CANNOT READ THEIR RECORDS' if failures else '')
    return EXIT_PROBLEM if failures else 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    subcommands = parser.add_subparsers(dest='command', required=True)

    def common(command):
        command.add_argument('--project-root', required=True, help='Repository root that contains the service directories.')
        command.add_argument('--project-name', required=True, help='Name used as the first record path segment, e.g. pinqponq. '
                             'A service directory "<name>.Chat.Api" becomes the record "chat-api".')
        command.add_argument('--only', nargs='*', default=[], help='Limit to these record names (e.g. chat-api users-api).')
        command.add_argument('--include', nargs='*', default=[], help='Extra keys to move (patterns on the ":" separated key, * allowed).')
        command.add_argument('--exclude', nargs='*', default=[], help='Keys or sections to keep in the files.')
        command.add_argument('--test-from', choices=('prod', 'local'), default='prod',
                             help='Values the test record starts from. Default prod: test and prod servers usually share container names.')
        command.add_argument('--mount', default=DEFAULT_MOUNT, help=f'KV v2 mount for the records (default {DEFAULT_MOUNT}).')
        command.add_argument('--test-vault-address', help='Address of the test Vault (holds the test and local records). Leave out when there is only one Vault.')
        command.add_argument('--prod-vault-address', help='Address of the prod Vault. When it is the only Vault, it also holds the test and local records.')
        command.add_argument('--test-token-env', default=DEFAULT_TEST_TOKEN_ENV)
        command.add_argument('--prod-token-env', default=DEFAULT_PROD_TOKEN_ENV)
        command.add_argument('--prod-token-file', help='File holding a prod Vault token, used when the environment variable is unset. '
                             'An environment variable set in the user\'s own terminal is not visible to a tool started from elsewhere; a file is.')

    baseline_help = ('Git ref holding the settings files from before the move. Default: read the working tree. Needed once the files '
                     'have already been rewritten (for example to write the prod records after a --skip-prod run).')
    plan_command = subcommands.add_parser('plan', help='Show what would move. Writes nothing and needs no Vault access.')
    common(plan_command)
    plan_command.add_argument('--baseline-ref', default=None, help=baseline_help)
    apply_command = subcommands.add_parser('apply', help='Write the records and rewrite the settings files (dry run by default).')
    common(apply_command)
    apply_command.add_argument('--baseline-ref', default=None, help=baseline_help)
    apply_command.add_argument('--only-prod', action='store_true',
                               help='Write only the prod records and leave the settings files and the test Vault alone. Needs --baseline-ref.')
    apply_command.add_argument('--apply-changes', action='store_true', help='Actually write. Without it the checks run but nothing is written.')
    apply_command.add_argument('--overwrite', action='store_true', help='Replace records that already exist.')
    apply_command.add_argument('--skip-prod', action='store_true',
                               help='Do not contact or write the prod Vault (needs no prod token). appsettings.json still gets the prod path.')
    check_command = subcommands.add_parser('check', help='Developer preflight: can this machine and this login read the Vault records the services need? Writes nothing.')
    common(check_command)
    check_command.add_argument('--reader', choices=('local', 'test'), default='local',
                               help='Which settings file decides the record: local (appsettings.Development.json, default) or test (appsettings.Test.json).')
    verify_command = subcommands.add_parser('verify', help='Check each reader still sees the same settings as before the move.')
    common(verify_command)
    verify_command.add_argument('--baseline-ref', default='HEAD', help='Git ref holding the settings files from before the move (default HEAD).')
    verify_command.add_argument('--skip-prod', action='store_true',
                                help='Do not contact the prod Vault (needs no prod token) and do not check the prod reader. Use before the prod records exist.')
    verify_command.add_argument('--accept-differences', nargs='*', default=[],
                                help='Keys that were changed on purpose during the move (patterns on the ":" separated key). They are listed, not failed.')
    return parser


def main(argv=None):
    # Operating-system error texts arrive in the machine's language and code page (e.g. Turkish Windows);
    # pinning the streams to UTF-8 keeps the output readable and decodable wherever it is piped.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='replace')
    arguments = build_parser().parse_args(argv)
    try:
        handler = {'plan': command_plan, 'apply': command_apply, 'verify': command_verify, 'check': command_check}[arguments.command]
        return handler(arguments) or 0
    except ConfigurationProblem as problem:
        print(f'ERROR: {problem}', file=sys.stderr)
        return EXIT_PROBLEM


if __name__ == '__main__':
    sys.exit(main())
