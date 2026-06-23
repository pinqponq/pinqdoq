# Task: update

Run these steps when asked to **update rules** or **update pinq-doq** (adopt newer shared standards in a project that already integrated pinq-doq).

This re-runs the copy delivery. The copy is idempotent: renamed or removed upstream files are pruned, and the version stamp is refreshed.

## 1. Pull the latest pinq-doq

```bash
git submodule update --remote .pinq-doq
# equivalently:
#   git -C .pinq-doq fetch origin && git -C .pinq-doq checkout main && git -C .pinq-doq pull --ff-only origin main
```

## 2. Re-copy `rules/` + `skills/` (idempotent: overwrite + prune)

Run the **exact same block** as `integrate.md` step 2 (it overwrites changed files, prunes stale ones, and rewrites `.claude/.pinq-doq-version`):

```bash
mkdir -p .claude/rules
rsync -a --delete --exclude='.git' .pinq-doq/rules/ .claude/rules/

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

sha="$(git -C .pinq-doq rev-parse HEAD)"
printf 'source_sha: %s\ndelivered_at: %s\n' "$sha" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .claude/.pinq-doq-version
```

## 3. Commit if anything changed

```bash
git add .gitmodules .pinq-doq .claude/rules .claude/skills .claude/.pinq-doq-version
git diff --cached --quiet && echo "Already up to date." || git commit -m "Update pinq-doq shared standards"
```

The `git add .pinq-doq` records the new submodule commit pointer. Without it, teammates would still get the old standards.
