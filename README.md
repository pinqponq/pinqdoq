---
paths: ['__readme-not-a-rule__/**']
---

# pinq-doq

PinqPonq shared Claude rules and project standards.

---

## Setup — Option A: Let Claude do it

Open Claude inside your project and send this prompt:

```
Integrate pinq-doq into this project as a shared Claude rules submodule.

1. Run: git submodule add https://github.com/Deveng-Group/pinq-doq.git .claude/rules
2. Commit .gitmodules and .claude/rules with message: "Add pinq-doq as shared Claude rules submodule"
3. Create a CLAUDE.md at the project root with the appropriate imports:
   - Android or KMP project:
       @.claude/rules/common.md
       @.claude/rules/android-kotlin.md
       @.claude/rules/tasks/update-rules.md
   - C# backend project:
       @.claude/rules/common.md
       @.claude/rules/csharp-dotnet.md
       @.claude/rules/tasks/update-rules.md
4. Commit CLAUDE.md.
```

---

## Setup — Option B: Manual

**1. Add submodule**
```bash
git submodule add https://github.com/Deveng-Group/pinq-doq.git .claude/rules
```

This clones pinq-doq into `.claude/rules/` and auto-creates `.gitmodules`:
```
[submodule ".claude/rules"]
    path = .claude/rules
    url = https://github.com/Deveng-Group/pinq-doq.git
```

**2. Commit**
```bash
git add .gitmodules .claude/rules
git commit -m "Add pinq-doq as shared Claude rules submodule"
```

**3. Create `CLAUDE.md` at project root**

Android / KMP:
```
@.claude/rules/common.md
@.claude/rules/android-kotlin.md
@.claude/rules/tasks/update-rules.md
```

C# backend:
```
@.claude/rules/common.md
@.claude/rules/csharp-dotnet.md
@.claude/rules/tasks/update-rules.md
```

**4. Commit CLAUDE.md**
```bash
git add CLAUDE.md
git commit -m "Add CLAUDE.md"
```

---

## Cloning a project that already has pinq-doq

```bash
git clone --recurse-submodules <repo-url>
```

Already cloned without that flag?
```bash
git submodule update --init
```

---

## Updating rules

Your project only records **which commit of pinq-doq to use**, not the files themselves. When pinq-doq is updated and you want to adopt the changes:

**Option A: Let Claude do it**

Say this to Claude inside your project:
```
update rules
```

**Option B: Manual**

```bash
git submodule update --remote .claude/rules
git add .claude/rules
git commit -m "Update Claude rules"
```

The `git add .claude/rules` saves the new commit pointer. Without it, teammates would still get the old version.

---

## Files

| File | Scope |
|---|---|
| `common.md` | All projects, all languages |
| `android-kotlin.md` | Android, KMP, Compose projects |
| `csharp-dotnet.md` | C# / .NET backend projects |
| `tasks/update-rules.md` | Update rules via Claude |
| `references/deveng-core.md` | deveng-core-kmp API usage guide (+ `deveng-core-reference.md`) — read on mention (Android / KMP) |

`references/` holds reference guides that are **not** `@imported` into `CLAUDE.md`; they cost nothing until needed and are read on demand. Point Claude at one when relevant (e.g. "use the deveng-core-guide from pinq-doq"). `android-kotlin.md` also carries a pointer so Claude pulls the deveng-core guide in when working on deveng-core-kmp features.

---

## How rules load

This repo is mounted at each consumer's `.claude/rules/`, and Claude Code auto-loads **every** `.md` there into **every** session at startup — whether or not `CLAUDE.md` `@import`s it. Control loading per file with `paths:` YAML frontmatter:

- **Universal rules** (`common.md`) — no frontmatter, so they always load.
- **Stack-specific rules** (`android-kotlin.md`, `csharp-dotnet.md`) — scoped with `paths:` so they load only when Claude touches matching files (Kotlin rules stay out of a C# project, and vice versa):

  ```yaml
  ---
  paths: ['**/*.kt', '**/*.kts']
  ---
  ```

- **Reference docs / non-rules** (`references/*`, `README.md`, `CLAUDE.md`) — given a non-matching `paths:` glob so they never auto-load; they are read on demand instead:

  ```yaml
  ---
  paths: ['__not-a-rule__/**']
  ---
  ```

Two gotchas when adding files:

- A new stack-specific rule **without** `paths:` loads into **every** consumer (including unrelated stacks) — scope it.
- Do not `@import` a `paths`-scoped file from `CLAUDE.md`; `@import` force-loads it and defeats the scope.

---

## Contributing

Changes here affect all projects. Open a PR and get team review before merging.
