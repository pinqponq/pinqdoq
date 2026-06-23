# Contributing to pinq-doq

How to extend pinq-doq — add a rule, a deep reference, a skill, a script, or a whole new stack. (For writing a *skill* specifically, see `authoring-guide.md`.)

## What goes where

| Put it in | When |
|---|---|
| `rules/common.md` | A rule for all projects and all languages |
| `rules/<stack>-<topic>.md` | A terse, always-applicable rule for one stack (e.g. `kotlin-architecture.md`, `dotnet-conventions.md`); scope it with `paths:` |
| `references/<stack>/*.md` | A deep dive, recipe, or long example — read on demand, not auto-loaded |
| `skills/<name>/SKILL.md` | A multi-step, intent-triggered capability |
| `scripts/*.py` | A code generator (or helper) invoked via CLI |
| `meta/` | Process/authoring docs about pinq-doq itself |

Decide by **load cost and audience**: if it should apply automatically while coding a given stack, it's a *rule* (keep it terse); if it's depth you only need sometimes, it's a *reference*; if it's a repeatable multi-step action, it's a *skill*.

## Conventions

- **Rule file names are flat and stack-prefixed:** `rules/<stack>-<topic>.md` (e.g. `kotlin-naming.md`, `dotnet-conventions.md`). No `rules/<stack>/` subdirs — flat keeps every editor tab uniquely named.
- **Scope every stack rule with `paths:`.** `common.md` has *no* frontmatter, so it always loads; stack rules use a `paths:` glob so they load only on matching files:
  ```yaml
  ---
  paths: ['**/*.kt', '**/*.kts']
  ---
  ```
  A stack rule **without** `paths:` would load into every consumer (including unrelated stacks). The only real loading gate is `paths:` — everything else below is navigation, not a gate.
- **Terse rule + deep reference.** Keep rules short; put long examples/recipes in `references/<stack>/*.md` and point to them. References carry **no** frontmatter (they're never auto-loaded).
- **Reference/script pointers use the mount path.** From a rule, link a reference as `.pinq-doq/references/<stack>/<file>.md` (in a consumer the rules live in `.claude/rules/` but references stay in the `.pinq-doq/` mount, so a bare relative path won't resolve). Within `references/`, link siblings by plain filename.
- **Do not `@import` a `paths`-scoped rule** from a consumer's `CLAUDE.md` — `@import` force-loads it and defeats the scoping. Let auto-load handle it.
- **No decorative emojis.** Keep the `✅`/`❌` do/don't markers (they carry meaning); drop ornamental icons and raw HTML callouts.
- **English only**, and don't duplicate a rule that already lives in another file — check first.

## Add a new stack (template)

Say the backend team wants to bring its standards into pinq-doq. Mirror what the Kotlin side does:

1. **Terse rule(s).** Add `rules/<stack>-conventions.md` (split by concern later if it grows — e.g. `<stack>-architecture.md`, `<stack>-naming.md`). Give each a `paths:` glob for that stack's file types (e.g. `['**/*.cs', '**/*.csproj', '**/*.sln']`).
2. **Stack pointer.** Add a bullet to the "Stack-specific rules" block in `rules/common.md` so the stack's rules and references are discoverable before one triggers.
3. **Deep references.** Put long-form material under `references/<stack>/*.md` and point to it from the rule(s) via `.pinq-doq/references/<stack>/…`.
4. **(Optional) Skills / scripts.** If there are repeatable multi-step actions or code generators, add `skills/<name>/` and/or `scripts/*.py` and wire the skill to call the scripts.
5. **README layout.** Add the new files to the layout tree in `README.md`.

Nothing else is required — `paths:` scoping and the copy delivery pick the new files up automatically.

## How delivery works (so you know what reaches consumers)

Only `rules/` and `skills/` are **copied** into a consumer's `.claude/` (by `tasks/integrate.md` / `tasks/update.md`, via `scripts/deliver.py`). `references/` and `scripts/` are used **in place** from the `.pinq-doq/` mount and are **not** copied. So: a rule auto-loads in consumers; a reference only helps if something points to it; a script only runs if a skill (or a person) calls it.
