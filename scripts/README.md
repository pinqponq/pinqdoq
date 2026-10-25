# scripts

KMP Clean-Architecture code generators. These are plain Python 3 CLI programs (stdlib only) — **no MCP server, no Figma, no network**. The pinq-doq skills drive them — `api-endpoint-integration` (backend: data → domain → use case → DI), `presentation-scaffold` (presentation: screen/MVI, navigation, components, strings), and `add-feature` (orchestrates both) — but you can run any of them by hand.

They are **not** copied into a consumer; they run in place from the pinq-doq mount, e.g. `python .pinq-doq/scripts/<script>.py …`.

> Exception: `deliver.py` is **not** a code generator — it's the delivery helper that `tasks/integrate.md` and `tasks/update.md` call to copy `rules/`+`skills/` into a consumer's `.claude/` (mirror + prune) and write the version stamp. Cross-platform (stdlib only). You don't run it by hand; the integrate/update runbooks do.

## What each script does

**Every script below runs on its own — you don't need the `api-endpoint-integration` workflow to use one.** Reach for a single script when you've done the rest by hand and just need one piece (e.g. you built a feature but forgot its DI modules → `register_di_modules.py`). For exact parameters and how each takes the target project, see [How each script takes the target project](#how-each-script-takes-the-target-project) below, or run the script with `--help`.

**Feature layer scaffolds** — whole-layer boilerplate for a new feature:

| Script | Purpose |
|---|---|
| `generate_data_layer.py` | Scaffold a feature's `data/` boilerplate (service, repository impl, DI). |
| `generate_domain_layer.py` | Scaffold a feature's `domain/` boilerplate (repository interface, DI). |
| `generate_presentation_layer.py` | Scaffold a feature's `presentation/` (MVI) boilerplate. |

**Models & mappers:**

| Script | Purpose |
|---|---|
| `generate_data_model.py` | Generate data-layer request/response data classes. |
| `generate_domain_model.py` | Generate domain model data classes. |
| `generate_mapper.py` | Generate mapper class(es) (response → domain). |

**Service, repository & use case** — add one method/class to existing files:

| Script | Purpose |
|---|---|
| `add_service_method.py` | Add a service method (`DevengNetworkingModule.sendRequest`) to a service class. |
| `add_repository_method.py` | Add a method to the domain repository interface. |
| `add_repository_impl.py` | Add the matching method to `RepositoryImpl` (auto-injects the mapper). |
| `generate_use_case.py` | Generate a use case class from a repository method. |

**Registration** — wire generated artifacts into DI / navigation:

| Script | Purpose |
|---|---|
| `register_mapper.py` | Register a mapper in the data DI module. |
| `register_use_case.py` | Register a use case in the domain DI module. |
| `register_di_modules.py` | Register a feature's three DI modules in `initKoin.kt`. |
| `register_navigation.py` | Register a screen in the navigation graph + `Screen.kt`. |

**Standalone UI** — presentation-layer scripts, wrapped by the `presentation-scaffold` skill (see [Presentation and UI scripts](#presentation-and-ui-scripts)):

| Script | Purpose |
|---|---|
| `add_string_resource.py` | Add/update a Compose `strings.xml` resource (tr/en). |
| `generate_component_composable.py` | Scaffold a `@Composable` + `@Preview` under `presentation/component/`. |

**Not code generators:**

| Script | Purpose |
|---|---|
| `deliver.py` | Delivery helper — copies `rules/`+`skills/` into a consumer (driven by `tasks/`, not run by hand). |
| `path_utils.py` | Shared helper (no `main`); imported by the generators. Must stay alongside them. |
| `vault_config.py` | Moves a .NET project's secrets and per-reader settings into Vault records (see [below](#vault_configpy)). |
| `storage_keys.py` | Writes the Cloudflare R2 `Storage` section of one Vault record with hidden input (see [below](#storage_keyspy)). |
| `new_product.py` | Turns a template repo into a new product: identity, keys, modules, theme (see [below](#new_productpy)). |

## Configuration — `config.json`

All path and package decisions come from a `config.json` (the consumer supplies its own, describing its source layout). A sample lives next to these scripts; copy and edit it, then pass it with `--config`.

```jsonc
{
  // Source root under which generated Kotlin is written (relative to project root, or absolute).
  "base_path": "composeApp/src/commonMain/kotlin",
  // Package prefix prepended to generated packages. "" = rooted directly at feature_root/shared_root.
  "base_package": "",
  // Path + package segment for feature modules:  <base_path>/<feature_root>/<feature>/…  /  <…>.<feature_root>.<feature>…
  "feature_root": "feature",
  // Path + package segment for the shared layer (selected via --shared or feature == "shared").
  "shared_root": "shared",
  // OPTIONAL. Path (under base_path) to the Koin init file. Only register_di_modules.py reads it.
  "initKoin_path": "core/data/di/initKoin.kt"
}
```

> Missing keys fall back to built-in defaults (`base_package` → `""` (no prefix), `feature_root` → `feature`, `shared_root` → `shared`, …). `base_package` is prepended consistently across every generator and scaffold, so set it (or leave it `""`) and all generated packages agree. Provide a **complete** config so generated packages/paths are correct for your project — don't rely on the fallbacks.

## How each script takes the target project

The interface is not uniform (these are copied verbatim from their origin; see the project plan):

- **`--config <path>`** — the layer scaffolds and model/mapper generators: `generate_data_layer.py`, `generate_domain_layer.py`, `generate_presentation_layer.py`, `generate_data_model.py`, `generate_domain_model.py`, `generate_mapper.py`. Resolve `base_path` from the config, so point `--config` at the target project's config to write into that project.
- **`--project-root <abs path>`** — file-reading / registration scripts: `add_repository_impl.py`, `add_repository_method.py`, `register_mapper.py`, `register_use_case.py`, `register_di_modules.py`, `add_string_resource.py` (default: cwd). `add_repository_impl.py` reads the repository interface + service from disk, so this is load-bearing for it.
- **`AI_SCRIPTS_PROJECT_ROOT` env var** — `generate_use_case.py` only (it has no `--project-root` flag); falls back to the current directory.
- **cwd-relative config** — `add_service_method.py`, `generate_component_composable.py`, `register_navigation.py` have no path flag; they read `config.json` from the working directory, so run them from the project root (where your `config.json` lives).

Run any script with `--help` (or read its header) for exact parameters. Use `--output-json` on the generators to print file contents as JSON instead of writing to disk.

## Presentation and UI scripts

These build the presentation layer. The `presentation-scaffold` skill wraps them (and the `add-feature` orchestrator runs that skill alongside `api-endpoint-integration`), but each is callable directly:

- `generate_presentation_layer.py` — scaffold a feature's `presentation/` (MVI) boilerplate. Also listed under **Feature layer scaffolds** above.
- `register_navigation.py` — register a screen in the navigation graph + `Screen.kt`. Also listed under **Registration** above.
- `generate_component_composable.py` — scaffold a `@Composable` + `@Preview` under `presentation/component/`.
- `add_string_resource.py` — add/update a Compose `strings.xml` resource (tr/en).

## `path_utils.py`

Shared helper (no `main`) imported by almost every generator to turn `config.json` into paths/packages. It must stay alongside the other scripts.

## `new_product.py`

Driven by the `new-product` skill; the manifest and product file formats are in [`references/templates/new-product-starter.md`](../references/templates/new-product-starter.md). It prints a JSON summary, or a JSON error (`error_code`, `message`, `how_to_fix`) with exit code 2, and writes nothing when validation or the leftover-placeholder check fails.

```bash
python .pinq-doq/scripts/new_product.py --template <dir|git url> --product <product.json> --destination <new dir> --dry-run
python .pinq-doq/scripts/new_product.py --template <dir|git url> --product <product.json> --destination <new dir>
```

Tests: `python3 -m unittest discover -s scripts/tests`.

## `vault_config.py`

A .NET helper for the Vault configuration standard in [`references/dotnet/vault-configuration.md`](../references/dotnet/vault-configuration.md). The `vault-config-setup` and `vault-dev-setup` skills drive it, but it runs on its own.

| Subcommand | Does |
|---|---|
| `plan` | Lists the keys that would move to Vault per service, and why. Writes nothing, needs no Vault access. |
| `apply` | Checks that every reader would see the same settings, writes the `prod`, `test` and `local` records per service and rewrites the settings files. A dry run unless `--apply-changes` is given. |
| `verify` | Compares what each reader sees now with the settings files at `--baseline-ref`, and fails on secrets left in the settings files. |
| `check` | Developer preflight on a moved project: says per service whether this machine's login can read its record, or why not. Writes nothing. |

```bash
python .pinq-doq/scripts/vault_config.py plan   --project-root . --project-name <name>
python .pinq-doq/scripts/vault_config.py apply  --project-root . --project-name <name> --apply-changes --skip-prod
python .pinq-doq/scripts/vault_config.py verify --project-root . --project-name <name> --baseline-ref <commit before the move> --skip-prod
# on a developer machine, once logged in (vault login):
python .pinq-doq/scripts/vault_config.py check  --project-root . --project-name <name>
# after testing, with the prod token saved in a file (see references/dotnet/vault-cli-setup.md):
python .pinq-doq/scripts/vault_config.py apply  --project-root . --project-name <name> --apply-changes --only-prod --baseline-ref <commit before the move> --prod-token-file ~/.vault-token-prod
python .pinq-doq/scripts/vault_config.py verify --project-root . --project-name <name> --baseline-ref <commit before the move> --prod-token-file ~/.vault-token-prod
```

### Tokens

- Test Vault: `VAULT_TEST_TOKEN`, or the file `vault login` saved (`~/.vault-token`) when that is unset. `check` reads `VAULT_TOKEN` instead of `VAULT_TEST_TOKEN`, like a service does.
- Prod Vault: `VAULT_PROD_TOKEN`, or a file given with `--prod-token-file`. `~/.vault-token` is never used for prod, so a prod write is always deliberate.
- The variable names can be changed with `--test-token-env` and `--prod-token-env`.
- Tokens are never read from the command line, and no output contains a secret value.

### One Vault

With only one Vault, pass just `--prod-vault-address`: the test and local records then go to the same server. On later runs the addresses are found in the settings files.

### Settings files

The settings files are edited as text: only the moved keys disappear and the `VaultConfiguration` section is added. Indentation, lists written on one line, key order and line endings of everything else stay as they were. The file is rewritten as a whole only if the text edit cannot be proven to give the intended settings.

### Vault mount

`apply` needs the `apps` mount to exist as KV version 2. The script checks it and never creates it.

### Check results

`check` reads the record named in `appsettings.Development.json` (`--reader test` for `appsettings.Test.json`) and prints only record paths and key counts. Besides `PASS`, it reports:

- `UNREACHABLE`: no VPN, or a wrong address.
- `NO TOKEN` / `TOKEN REJECTED`: run `vault login` (again).
- `NO ACCESS`: ask the DevOps unit for read access.
- `MISSING RECORD`: the record has not been created yet.
- `SEALED` / `UNEXPECTED`: the Vault itself is unwell; tell the DevOps unit.

### Options

- `--project-name`: use lower case. The script prints a note for capitals, because Vault paths are case sensitive.
- `--include` / `--exclude`: correct the plan. They are not remembered: pass the same flags to every later `apply` and `verify`. A secret-looking key kept in the settings files on purpose must be named with `--exclude`, or `verify` fails.
- `--skip-prod`: `apply` and `verify` leave the prod Vault out, for use before the prod records exist.
- `--only-prod`: `apply` writes just the prod records and leaves the settings files alone. This is how prod follows a `--skip-prod` run.
- `--baseline-ref <commit>`: the commit before the move. `verify` compares against it; `apply` builds the records from it once the settings files are already rewritten.
- `--accept-differences <keys>`: `verify` accepts differences made on purpose (a setting moved to a new place, an unused section dropped). They are still listed.
- `--test-from local`: only if the test server really needs the developer-machine values.
- `--help` lists everything else.

## `verification/`

Build, test and mutation wrappers. The `pin-test` subagent runs them, but they need neither the task runner nor its state, so any project can call them directly. Defaults match the pinqloq task runner; a project overrides them in its own `verification-profile.json`.

| Script | Purpose |
|---|---|
| `run_build.py` | Runs a build/test command with full output in `build/runner-logs/` and prints only status, duration, test counts, failures and compiler errors. `--heartbeat '<command>'` keeps a caller's lock fresh; `--lock <key>` alone touches the task runner's lock. |
| `run_pit.py` | Diff-scoped PIT mutation run for Kotlin modules (JSON score and survivors on changed lines). |
| `run_stryker_js.py` | Diff-scoped StrykerJS run for TypeScript/JavaScript, same output and exit codes as `run_pit.py`. |
| `verification_profile.py` | Prints the project's `mutation_threshold`, `baseline_branch` and `dotnet_root` (defaults merged with `verification-profile.json`). |
| `shrink_images.py` | Small JPEG copies of screenshots for reading. |
| `clean_build_output.py` | Deletes build output only under `build/` or `_small/`. |
| `test-agent-template.md`, `device-agent-template.md`, `render_agent.py` | The subagents that drive these scripts: `--agent test` (builds, tests, mutation) and `--agent device` (Maestro and Playwright flows). `render_agent.py pinqloq` produces `runner/agents/pin-test.md` and `pin-device.md`; `render_agent.py generic --scripts-dir <folder>` produces the same agents without the task runner's locks and state or PinqPonq's log service. |
| `timings.py`, `android_sdk.py`, `pit.init.gradle` | Helpers for the scripts above (run timings in `~/.claude/pinqloq-task-runner/timings.jsonl`, `ANDROID_HOME` fallback, PIT classpath). |

The task runner keeps forwarding files with the same names in `runner/skill/scripts/`, so its existing paths keep working. Tests: `python3 -m unittest discover -s scripts/verification/tests`.

To use the subagent outside the task runner, render it into the project's (or your own) agents folder, pointing at wherever these scripts are on that machine:

```bash
python3 .pinq-doq/scripts/verification/render_agent.py generic --scripts-dir .pinq-doq/scripts/verification --out .claude/agents/verification-runner.md
```

```bash
python3 .pinq-doq/scripts/verification/render_agent.py generic --agent device --scripts-dir .pinq-doq/scripts/verification --out .claude/agents/device-runner.md
```

`pin-test.md` and `pin-device.md` are generated: change the template, then run `python3 scripts/verification/render_agent.py pinqloq --agent test --out runner/agents/pin-test.md` (or `--agent device --out runner/agents/pin-device.md`). A test fails while a file and its template differ.

## `storage_keys.py`

Writes the `Storage` section (`BucketName`, `AccountId`, `AccessKey`, `SecretKey`) of one Vault record for Cloudflare R2, with the secrets typed hidden. The `r2-upload-setup` skill hands it to the owner; it keeps every other key of the record and prints only the bucket name and the character counts (expected 32, 32 and 64).

```bash
export VAULT_ADDR=<vault address>
python .pinq-doq/scripts/storage_keys.py --product <product> --env test --service <service>
```

Tests: `python3 -m unittest discover -s scripts/tests`.
