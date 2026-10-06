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
| `vault_config.py` | Plans, applies and verifies moving a project's secrets and per-reader settings into Vault records, and checks that a developer machine can read them. Driven by the `vault-config-setup` and `vault-dev-setup` skills. See [`vault_config.py`](#vault_configpy) below. |

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

## `vault_config.py`

A .NET helper (stdlib only) for the Vault configuration standard in [`references/dotnet/vault-configuration.md`](../references/dotnet/vault-configuration.md). The `vault-config-setup` skill drives it, but it runs on its own.

| Subcommand | Does |
|---|---|
| `plan` | Reads each service's `appsettings.json` and `appsettings.Development.json` and lists the keys that would move to Vault and why (secret name, or differs between server and developer machine). Writes nothing, needs no Vault access. |
| `apply` | Checks that every reader would see the same settings as before, then writes the three records per service (`prod`, `test`, `local`) and rewrites the settings files. The `apps` mount must already exist as KV version 2 (the script checks and never creates it). A dry run unless `--apply-changes` is given; `--skip-prod` leaves the prod Vault untouched. Once the files are rewritten, `--baseline-ref <commit>` builds the records from the commit before the move instead, and `--only-prod` writes just the prod records (without touching the settings files), which is how prod follows a `--skip-prod` run. |
| `verify` | Compares what each reader sees now (settings files plus live records) with the settings files at `--baseline-ref`, and flags secrets still left in `appsettings.json`. `--skip-prod` leaves the prod Vault and the prod reader out, for use before the prod records exist. Secret-looking values left in `appsettings.json` or `appsettings.Development.json` fail the check unless the key was kept on purpose and is named with `--exclude`. Differences you made on purpose (a setting that moved to a new place, an unused section you dropped) are acknowledged with `--accept-differences <keys>`; they are still listed. |
| `check` | Developer preflight on a project that is already moved: for each service it reads the record named in `appsettings.Development.json` (`--reader test` for `appsettings.Test.json`) with the login `vault login` saved (or `VAULT_TOKEN`) and says PASS or why not: `UNREACHABLE` (VPN), `NO TOKEN`, `TOKEN REJECTED`, `NO ACCESS` (ask the DevOps unit), `MISSING RECORD`. Writes nothing and prints only record paths and key counts. |

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

- Test Vault: `VAULT_TEST_TOKEN`, or the file `vault login` saved (`~/.vault-token`) when that is unset.
- Prod Vault: `VAULT_PROD_TOKEN`, or a file given with `--prod-token-file`. `~/.vault-token` is never used for prod, so a prod write is always deliberate.
- The variable names can be changed with `--test-token-env` and `--prod-token-env`.
- Tokens are never read from the command line, and no output contains a secret value.

### One Vault

With only one Vault, pass just `--prod-vault-address`: the test and local records then go to the same server. On later runs the addresses are found in the settings files.

### Settings files

The settings files are edited as text: only the moved keys disappear and the `VaultConfiguration` section is added. Indentation, inline arrays, key order and line endings of everything else stay as they were. The file is rewritten as a whole only if the text edit cannot be proven to give the intended settings.

### Options

- `--project-name`: use lower case. The script prints a note for capitals, because Vault paths are case sensitive.
- `--include` / `--exclude`: correct the plan. They are not remembered: pass the same flags to every later `apply` and `verify`.
- `--test-from local`: only if the test server really needs the developer-machine values.
- `--help` lists everything else.
