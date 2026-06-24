# scripts

KMP Clean-Architecture code generators. These are plain Python 3 CLI programs (stdlib only) — **no MCP server, no Figma, no network**. The `api-endpoint-integration` skill drives them, but you can run any of them by hand.

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

**Standalone UI** — not part of the endpoint flow (see [The three standalone UI scripts](#the-three-standalone-ui-scripts)):

| Script | Purpose |
|---|---|
| `add_string_resource.py` | Add/update a Compose `strings.xml` resource (tr/en). |
| `generate_component_composable.py` | Scaffold a `@Composable` + `@Preview` under `presentation/component/`. |

**Not code generators:**

| Script | Purpose |
|---|---|
| `deliver.py` | Delivery helper — copies `rules/`+`skills/` into a consumer (driven by `tasks/`, not run by hand). |
| `path_utils.py` | Shared helper (no `main`); imported by the generators. Must stay alongside them. |

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

> Missing keys fall back to built-in defaults (`base_package` → `com.example.app`, `feature_root` → `feature`, `shared_root` → `shared`, …). Provide a **complete** config so generated packages/paths are correct for your project — don't rely on the fallbacks.

## How each script takes the target project

The interface is not uniform (these are copied verbatim from their origin; see the project plan):

- **`--config <path>`** — the layer scaffolds and model/mapper generators: `generate_data_layer.py`, `generate_domain_layer.py`, `generate_presentation_layer.py`, `generate_data_model.py`, `generate_domain_model.py`, `generate_mapper.py`. Resolve `base_path` from the config, so point `--config` at the target project's config to write into that project.
- **`--project-root <abs path>`** — file-reading / registration scripts: `add_repository_impl.py`, `add_repository_method.py`, `register_mapper.py`, `register_use_case.py`, `register_di_modules.py`, `add_string_resource.py` (default: cwd). `add_repository_impl.py` reads the repository interface + service from disk, so this is load-bearing for it.
- **`AI_SCRIPTS_PROJECT_ROOT` env var** — `generate_use_case.py` only (it has no `--project-root` flag); falls back to the current directory.
- **cwd-relative config** — `add_service_method.py`, `generate_component_composable.py`, `register_navigation.py` have no path flag; they read `config.json` from the working directory, so run them from the project root (where your `config.json` lives).

Run any script with `--help` (or read its header) for exact parameters. Use `--output-json` on the generators to print file contents as JSON instead of writing to disk.

## The three standalone UI scripts

These are not wired to the `api-endpoint-integration` flow; they are callable directly and a future "screen-scaffold" skill could wrap them:

- `add_string_resource.py` — add/update a Compose `strings.xml` resource (tr/en).
- `generate_component_composable.py` — scaffold a `@Composable` + `@Preview` under `presentation/component/`.
- `register_navigation.py` — register a screen into the navigation graph + `Screen.kt` sealed class.

## `path_utils.py`

Shared helper (no `main`) imported by almost every generator to turn `config.json` into paths/packages. It must stay alongside the other scripts.
