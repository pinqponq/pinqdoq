# pinq-doq

PinqPonq shared Claude rules and project standards.

## Claude prompt — first-time setup

Copy this prompt and send it to Claude inside your project:

```
Integrate pinq-doq into this project as a shared Claude rules submodule.

Steps:
1. Run: git submodule add https://github.com/Deveng-Group/pinq-doq.git .claude/rules
2. Commit .gitmodules and .claude/rules with message: "Add pinq-doq as shared Claude rules submodule"
3. Create a CLAUDE.md at the project root with the appropriate imports:
   - If this is an Android or KMP project:
       @.claude/rules/common.md
       @.claude/rules/android-kotlin.md
       @.claude/rules/tasks/prepare-release.md
       @.claude/rules/tasks/update-rules.md
   - If this is a C# backend project:
       @.claude/rules/common.md
       @.claude/rules/csharp-dotnet.md
       @.claude/rules/tasks/update-rules.md
4. Commit CLAUDE.md.
```

---

## Integrating into a new project

Do this once per project to wire up pinq-doq.

**1. Inside your project repo, run:**
```bash
git submodule add https://github.com/Deveng-Group/pinq-doq.git .claude/rules
```

This clones pinq-doq into `.claude/rules/` and auto-creates a `.gitmodules` file:
```
[submodule ".claude/rules"]
    path = .claude/rules
    url = https://github.com/Deveng-Group/pinq-doq.git
```

**2. Commit both files to your project:**
```bash
git add .gitmodules .claude/rules
git commit -m "Add pinq-doq as shared Claude rules submodule"
```

**3. Create a `CLAUDE.md` at your project root:**

For Android / KMP projects:
```markdown
@.claude/rules/common.md
@.claude/rules/android-kotlin.md
```

For C# backend projects:
```markdown
@.claude/rules/common.md
@.claude/rules/csharp-dotnet.md
```

## Cloning a project that already has pinq-doq

```bash
git clone --recurse-submodules <repo-url>
```

If you already cloned without `--recurse-submodules`:
```bash
git submodule update --init
```

## Updating rules

Your project does not track pinq-doq's files directly — it only records **which commit of pinq-doq to use**. When pinq-doq has new changes and you want to adopt them, run inside your project:

```bash
# Pull the latest pinq-doq commit into .claude/rules
git submodule update --remote .claude/rules

# Record the new commit reference in your project
git add .claude/rules
git commit -m "Update Claude rules"
```

The `git add .claude/rules` step saves the pointer update ("use pinq-doq commit X instead of Y") into your project's history. Without this commit, other team members would still get the old version.

## Files

| File | Scope |
|---|---|
| `common.md` | All projects, all languages |
| `android-kotlin.md` | Android, KMP, Compose projects |
| `csharp-dotnet.md` | C# / .NET backend projects |
| `tasks/prepare-release.md` | Release preparation workflow |

## Contributing

Changes to these standards affect all projects. Open a PR and get team review before merging.
