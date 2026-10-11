# pinqloq Task Runner — run report format (steps 4 and 6)

Read this file before adding a run report. The runner sends no mail (owner, 2026-10-11): the owner reads reports and decisions in the web panel, the team reads the issues and PRs.

One report per run, written in Turkish, added with:

```
python3 ~/.claude/skills/pinqloq-task-runner/scripts/report.py add <session> < report.json
```

Write `report.json` in the session's scratchpad (never under `~/.claude`). Fields:
- `title` — one line: `<task title> — PR açıldı`, `Yeni öneriler (3)`, `Runner durdu: …`.
- `task` — the task key when the report is about one task; `pr_url` when a PR exists.
- `sections` — `{"<heading>": ["<line>", …]}`. Lines are short Markdown (links, `code`, **bold**). Headings, in this order, omit empty ones:
  1. **Yeni öneriler** — per task: title + issue link, repo, assignee, plan in one line, `Yapılabilirlik 4/5 · Risk Düşük`, human-required parts, decisions (`S<n>: … → öneri A`).
  2. **Tamamlananlar** — PR link, what changed, what was tested (unit/UI/PIT score, Maestro platforms, pinqloq), screenshot paths under `media/`. Lesson PRs: `Ders PR'ı: <link>, <rule in one line>`.
  3. **Alınan kararlar** — one line per decision exactly as in the task's `decisions` (`S<n>: <soru> → <seçilen> (diğer seçenekler: …); neden: …`), `❓` first when no option was clearly better, `⚠️` for payments/auth/data deletion.
  4. **Kurala rağmen yapılan hatalar** — rule file:line, why it was missed, what was done (`references/lessons.md`).
  5. **Runner için öneri** — lessons about the runner's own procedure.
  6. **İnsan gerekiyor** — blocked items and exactly what a person must do.
  7. **Yoksayılan yorumlar** — comments from non-members, per the trust rules.
- Store new proposal numbers in `proposals[]` (`{"reported_at": …, "items": {"1": "<task key>"}}`) through `state_tx.py`.
