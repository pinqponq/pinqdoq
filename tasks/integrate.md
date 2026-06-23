# Task: integrate

Run these steps when asked to **integrate pinq-doq** into a project (first-time setup).

pinq-doq is delivered by **copy**, not as a live submodule mounted at `.claude/rules`. The repo is mounted once at a neutral path (`.pinq-doq/`), and its `rules/` and `skills/` are **copied** into the project's `.claude/` and committed (so they travel with the repo on a fresh clone — no submodule init needed to get the rules). `references/` and `scripts/` are used **in place** from the mount.

> Team note: copy delivery is used because some teammates are on Windows (no symlinks). The committed copies + a version stamp make staleness detectable.

## 1. Mount pinq-doq at the neutral path

```bash
git submodule add https://github.com/pinqponq/pinq-doq.git .pinq-doq
git -C .pinq-doq checkout main
```

If the canonical remote/org differs, use the correct pinq-doq URL. `.pinq-doq/` is the mount; never edit files inside it from the consumer.

## 2. Copy `rules/` + `skills/` into `.claude/` (idempotent: overwrite + prune)

Run this block verbatim from the **project root**. It is safe to re-run (that is exactly what `update` does).

```bash
# --- rules: full mirror; .claude/rules is owned entirely by pinq-doq ---
mkdir -p .claude/rules
rsync -a --delete --exclude='.git' .pinq-doq/rules/ .claude/rules/

# --- skills: merge into .claude/skills, preserving the project's own skills,
#     pruning only pinq-doq-managed skills that no longer ship upstream ---
mkdir -p .claude/skills
if [ -f .claude/skills/.pinq-doq-skills ]; then
  while IFS= read -r s; do
    [ -n "$s" ] && [ ! -d ".pinq-doq/skills/$s" ] && rm -rf ".claude/skills/$s"
  done < .claude/skills/.pinq-doq-skills
fi
: > .claude/skills/.pinq-doq-skills
for d in .pinq-doq/skills/*/; do
  name="$(basename "$d")"
  rm -rf ".claude/skills/$name"
  rsync -a --exclude='.git' "$d" ".claude/skills/$name/"
  echo "$name" >> .claude/skills/.pinq-doq-skills
done

# --- version stamp (lives OUTSIDE .claude/rules so the mirror sync never deletes it) ---
sha="$(git -C .pinq-doq rev-parse HEAD)"
printf 'source_sha: %s\ndelivered_at: %s\n' "$sha" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .claude/.pinq-doq-version
```

`--delete` on `rules/` keeps the copy idempotent: a rule renamed or removed upstream leaves no orphan. The skills loop prunes only what pinq-doq previously delivered (tracked in `.claude/skills/.pinq-doq-skills`), so the project's own skills are never touched.

## 3. Wire `CLAUDE.md`

The copied rules under `.claude/rules/` **auto-load** — `common.md` always, and the stack rules (`kotlin-architecture.md`, `kotlin-naming.md`, `kotlin-conventions.md`, `kotlin-deveng-core.md`, `dotnet-conventions.md`) only when you touch a matching file, via their `paths:` frontmatter. So you do **not** need to `@import` them.

Create or update the project-root `CLAUDE.md` with a short pointer (do not `@import` the scoped rule files — `@import` force-loads them and defeats the scoping):

```markdown
# Project standards

Shared standards come from **pinq-doq**, vendored under `.pinq-doq/` and copied into `.claude/rules/` (auto-loaded — do not @import the scoped files). Skills are in `.claude/skills/`. Code-gen scripts: `.pinq-doq/scripts/`. Deep references: `.pinq-doq/references/`.

To pull newer standards later, tell Claude: **update rules**.
```

## 4. Commit

```bash
git add .gitmodules .pinq-doq .claude/rules .claude/skills .claude/.pinq-doq-version CLAUDE.md
git commit -m "Integrate pinq-doq shared standards (copy delivery)"
```

## Verify

- `.claude/rules/common.md` and `.claude/rules/kotlin-conventions.md` (etc.) exist as real files.
- `.claude/.pinq-doq-version` records the source SHA.
- A fresh `git clone` of the project (without `--recurse-submodules`) still has the rules and skills (they are committed copies, not a submodule pointer).
