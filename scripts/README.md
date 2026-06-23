# scripts

KMP Clean-Architecture code generators. These are plain Python 3 CLI programs (stdlib only) — **no MCP server, no Figma, no network**. The `api-endpoint-integration` skill drives them, but you can run any of them by hand.

They are **not** copied into a consumer; they run in place from the pinq-doq mount, e.g. `python .pinq-doq/scripts/<script>.py …`.

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
- **`--project-root <abs path>`** — file-reading / registration scripts: `add_repository_impl.py`, `add_repository_method.py`, `register_mapper.py`, `register_use_case.py`, `register_di_modules.py`. `add_repository_impl.py` reads the repository interface + service from disk, so this is load-bearing for it.
- **`AI_SCRIPTS_PROJECT_ROOT` env var** — `generate_use_case.py` only (it has no `--project-root` flag); falls back to the current directory.
- **cwd-relative config** — `add_service_method.py`, `generate_component_composable.py`, `register_navigation.py` read `config.json` relative to the working directory; run them from the project root (or pass `--config` where supported).

Run any script with `--help` (or read its header) for exact parameters. Use `--output-json` on the generators to print file contents as JSON instead of writing to disk.

## The three standalone UI scripts

These are not wired to the `api-endpoint-integration` flow; they are callable directly and a future "screen-scaffold" skill could wrap them:

- `add_string_resource.py` — add/update a Compose `strings.xml` resource (tr/en).
- `generate_component_composable.py` — scaffold a `@Composable` + `@Preview` under `presentation/component/`.
- `register_navigation.py` — register a screen into the navigation graph + `Screen.kt` sealed class.

## `path_utils.py`

Shared helper (no `main`) imported by almost every generator to turn `config.json` into paths/packages. It must stay alongside the other scripts.
