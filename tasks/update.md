# Task: update

Run these steps when asked to **update rules** or **update pinq-doq**. This works whether the project is already on the new copy model **or** still on the old layout (pinq-doq mounted directly as a submodule at `.claude/rules`) — it detects the old layout and converts it first, then pulls and re-copies.

## 1. If on the OLD layout, convert it (one-time)

**Detect** the old model: `.gitmodules` mounts pinq-doq at `.claude/rules` (instead of `.pinq-doq`).

```bash
if [ -f .gitmodules ] && grep -q 'path = .claude/rules' .gitmodules; then echo "OLD layout — convert"; fi
```

If old, convert to the neutral `.pinq-doq` mount:

```bash
git submodule deinit -f .claude/rules
git rm -f .claude/rules
git config -f .gitmodules --remove-section 'submodule..claude/rules' 2>/dev/null || true
rm -rf .git/modules/.claude/rules
# remount at the neutral path (canonical URL — note the repo was renamed pinq-doq -> pinqdoq)
git submodule add https://github.com/pinqponq/pinqdoq.git .pinq-doq
git -C .pinq-doq checkout main
```

Then fix the project's `CLAUDE.md`: **remove the old `@import`s** (e.g. `@.claude/rules/common.md`, `@.claude/rules/android-kotlin.md`, `@.claude/rules/tasks/update-rules.md`). The copied rules auto-load, so no `@import` is needed — replace them with the short pointer block from `integrate.md` step 3. (The old stack files `android-kotlin.md` / `csharp-dotnet.md` are now `kotlin-*.md` / `dotnet-conventions.md`; `tasks/update-rules.md` is now `integrate.md` + `update.md`.)

## 2. Pull the latest pinq-doq

```bash
git submodule update --remote .pinq-doq
# equivalently: git -C .pinq-doq fetch origin && git -C .pinq-doq checkout main && git -C .pinq-doq pull --ff-only origin main
```

## 3. Re-copy `rules/` + `skills/` (idempotent: overwrite + prune)

```bash
python .pinq-doq/scripts/deliver.py
```

Same script as `integrate.md` step 2 — it overwrites changed files, prunes stale/renamed ones, preserves the project's own skills, and refreshes `.claude/.pinq-doq-version`.

## 4. Commit if anything changed

```bash
git add .gitmodules .pinq-doq .claude/rules .claude/skills .claude/.pinq-doq-version CLAUDE.md
git diff --cached --quiet && echo "Already up to date." || git commit -m "Update pinq-doq shared standards"
```

The `git add .pinq-doq` records the new submodule commit pointer. Without it, teammates would still get the old standards.
