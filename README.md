# pinq-doq

PinqPonq's shared AI knowledge hub: coding **rules**, reusable **skills**, code-generation **scripts**, and deep **references** for every project (mobile + backend).

## Layout

```
pinq-doq/
  rules/          → COPIED into a consumer's .claude/rules/   (auto-loaded, scoped by paths:)
    common.md                 always-on; carries a stack pointer to the files below
    kotlin-architecture.md    paths: ['**/*.kt','**/*.kts'] — Clean Arch, MVI, shared module
    kotlin-naming.md          paths: ['**/*.kt','**/*.kts']
    kotlin-conventions.md     paths: ['**/*.kt','**/*.kts'] — Compose, style, null-safety, DI
    kotlin-deveng-core.md     paths: ['**/*.kt','**/*.kts'] — cites references/kotlin/deveng-core-reference.md
    dotnet-conventions.md     paths: ['**/*.cs','**/*.csproj','**/*.sln']
  skills/         → COPIED into a consumer's .claude/skills/  (intent-discovered)
    api-endpoint-integration/   scaffold a Clean-Architecture API endpoint via scripts/
    kmp-theme-setup/            colors / typography / AppTheme wiring for deveng-core-kmp
    code-review/                review a diff against rules/ (no external services)
  scripts/        → NOT copied; run in place via CLI (KMP code generators + deliver.py, the copy helper)
  references/     → NOT copied; read on demand by path
    kotlin/
      deveng-core-reference.md  full deveng-core-kmp API map
      deep dives: architecture.md, data-layer.md, mvi-pattern.md, viewmodel-patterns.md,
      naming.md, error-handling.md, fake-data.md, formatting.md, shared-module.md
  tasks/          integrate.md (first-time setup), update.md (adopt newer standards)
  meta/           authoring-guide.md (write a skill), contributing.md (extend pinq-doq)
  README.md, CLAUDE.md   repo docs — never delivered into consumers
```

## Delivery model — copy, not live submodule

The repo is mounted **once** in a consumer at a neutral path (`.pinq-doq/`). From there:

- `rules/` and `skills/` are **copied** into the consumer's `.claude/` and **committed** (plus a `.claude/.pinq-doq-version` stamp recording the source SHA).
- `references/` and `scripts/` are used **in place** from the `.pinq-doq/` mount.

Why copy instead of mounting the rules straight at `.claude/rules`? Some teammates are on Windows (no symlinks), and committing the copies means the rules travel with the repo on a fresh clone — no `submodule update --init` needed to get them. The version stamp makes copy-staleness detectable.

## Setup

Tell Claude, inside your project:

> Install pinq-doq from https://github.com/pinqponq/pinqdoq — add it as a git submodule at `.pinq-doq`, then follow `.pinq-doq/tasks/integrate.md`.

That one sentence is all a teammate needs — nothing to copy or hand over. Claude adds the submodule, then runs [`tasks/integrate.md`](tasks/integrate.md): copies `rules/`+`skills/` into `.claude/`, writes the `.claude/.pinq-doq-version` stamp, wires `CLAUDE.md`, and commits. (Prefer to do it by hand? The same steps are in that file.)

## Updating

When pinq-doq changes and you want the newer standards, say to Claude inside your project:

```
update rules
```

Claude runs [`tasks/update.md`](tasks/update.md): pulls the latest pinq-doq, re-copies `rules/`+`skills/` via `.pinq-doq/scripts/deliver.py` (overwriting changed files and **pruning** stale/renamed ones), refreshes the version stamp, and commits. It also **auto-converts** a project still on the old layout (submodule mounted at `.claude/rules`) to the new copy model. Manual steps are in the same file.

## How rules load

Claude Code auto-loads **every** `.md` directly under a project's `.claude/rules/` into every session at startup. Because `integrate`/`update` copy `pinq-doq/rules/` into `.claude/rules/`, those rule files — and only those — auto-load in consumers. Control loading per file with `paths:` YAML frontmatter:

- **Universal rules** (`common.md`) — no frontmatter, so they always load. `common.md` also carries a short pointer to the stack-specific files so Claude knows they exist before one triggers.
- **Stack-specific rules** (`kotlin-architecture.md`, `kotlin-naming.md`, `kotlin-conventions.md`, `kotlin-deveng-core.md`, `dotnet-conventions.md`) — scoped with `paths:` so they load only when Claude touches a matching file (Kotlin rules stay out of a C# project, and vice versa):

  ```yaml
  ---
  paths: ['**/*.kt', '**/*.kts']
  ---
  ```

`skills/`, `scripts/`, `references/`, and the repo's own `README.md`/`CLAUDE.md` are **not** copied into `.claude/rules/`, so they never auto-load — skills are intent-discovered from `.claude/skills/`, and scripts/references are used on demand from the `.pinq-doq/` mount.

Two gotchas when adding rules:

- A new stack-specific rule **without** `paths:` loads into **every** consumer (including unrelated stacks) — scope it.
- Do not `@import` a `paths`-scoped rule from a consumer's `CLAUDE.md`; `@import` force-loads it and defeats the scope. Let auto-load handle it.

## Contributing

Changes here affect all projects. See [`meta/contributing.md`](meta/contributing.md) for how to add a rule, reference, skill, script, or a whole new stack. Open a PR and get team review before merging.
