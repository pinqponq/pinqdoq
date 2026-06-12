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

---

## Contributing

Changes here affect all projects. Open a PR and get team review before merging.
