# pinq-doq

PinqPonq shared Claude rules and project standards.

## Usage

Add this repo as a git submodule inside your project under `.claude/rules/`:

```bash
git submodule add https://github.com/Deveng-Group/pinq-doq.git .claude/rules
```

This command automatically creates a `.gitmodules` file at your project root:

```
[submodule ".claude/rules"]
    path = .claude/rules
    url = https://github.com/Deveng-Group/pinq-doq.git
```

Commit both `.gitmodules` and `.claude/rules` to your repo:

```bash
git add .gitmodules .claude/rules
git commit -m "Add pinq-doq as shared Claude rules submodule"
```

Then create a `CLAUDE.md` at the project root importing the relevant files:

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

When pinq-doq has new changes, run inside your project:
```bash
git submodule update --remote .claude/rules
git add .claude/rules
git commit -m "Update Claude rules"
```

## Files

| File | Scope |
|---|---|
| `common.md` | All projects, all languages |
| `android-kotlin.md` | Android, KMP, Compose projects |
| `csharp-dotnet.md` | C# / .NET backend projects |
| `tasks/prepare-release.md` | Release preparation workflow |

## Contributing

Changes to these standards affect all projects. Open a PR and get team review before merging.
