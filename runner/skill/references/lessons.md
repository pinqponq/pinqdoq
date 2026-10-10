# Lessons from review → pinqdoq PR

Every change request is feedback that the shared standards did not prevent the mistake. Once a change request is implemented, turn the general part of it into a pinqdoq PR, so the same mistake is not made again in any repo. The owner (`config.json` → `lesson_pr_reviewer`) is assigned to the PR (not `--reviewer`: the runner uses the owner's own GitHub account, and GitHub refuses a review request from a PR's author): they merge what they want and close the rest. Closing a lesson PR is a normal outcome, not a failure.

## When
After a change request is implemented and pushed (step 5), in the same session, before step 6. A change request is any of: an org member's `Düzelt:` issue comment, a review comment by an org member on a runner PR, or an owner decision recorded from chat under the task's `change_requests`.

## Which change requests become a lesson
Only the general part. Ask: "would this have been wrong in another task, or another repo?"
- **Yes → lesson:** coding, naming, architecture or testing standards; how evidence, PR bodies or mails must look; a process step that was missed (e.g. "check the repo's open PRs before adding infrastructure"); a wrong assumption about a shared library or service.
- **No → no lesson:** product or scope decisions for this task, copy and wording for this feature, a plain bug in this task's code, anything that only restates the issue.
One change request can hold several lessons; one PR per lesson.

## Duplicate check (mandatory)
1. Fresh pinqdoq: in `<workspace_dir>/.task-runner-worktrees/pinqdoq-lessons`, `git fetch origin` and work from `origin/main` (clone `pinqponq/pinqdoq` there the first time).
2. `grep -rni` the key terms in `rules/`, `references/`, `skills/`, `CLAUDE.md`. If a rule already says it, see "Rule existed but was missed" below; do not add the same rule again.
3. `gh pr list -R pinqponq/pinqdoq --state open` and check the titles and bodies. If an open PR covers the same thing, comment on it with the new example instead of opening another one.

## Rule existed but was missed
This is the more serious case: the standard was there and the mistake happened anyway. It is **always reported**, never dropped silently.
1. **Find why it was missed.** Pick the cause that fits; check, don't guess:
   - **Not loaded:** the rule's `paths:` scope does not match the files that were changed, the consumer repo has an old `.pinq-doq` copy without it (compare the repo's `.claude/rules/` with pinqdoq `main`), or the rule sits in `references/` and nothing points to it.
   - **Unclear:** the wording allows the wrong reading, or it is buried in a long paragraph.
   - **Not enforced:** `pinq_code-review` (or the PR gate) does not check it, so nothing caught it before the PR.
   - **Ignored:** the rule was loaded and clear, and the runner did not follow it.
2. **Report it** in the run mail, under its own heading **"Kurala rağmen yapılan hatalar"**. For each one, write:
   - the PR and the change request it came from;
   - the rule's `file:line` and a one-line summary of it;
   - the cause from step 1 and its evidence (e.g. "rindle-cmp/.claude/rules/common.md, 3 commits behind pinqdoq main");
   - what was done about it.

   Post the same summary as a comment on the runner PR the change request came from.
3. **Fix the cause when pinqdoq can fix it,** with a PR that follows "Opening the PR" below (same reviewer, same body sections; under `## Ne yanlış gitti`, say that the rule existed and why it was missed):
   - Not loaded: widen the `paths:` scope, or add a one-line pointer in `rules/` to the reference.
   - Unclear: rewrite the rule shorter and more concrete.
   - Not enforced: add the check to `pinq_code-review`'s checklist.

   If the cause is an outdated copy in a consumer repo, do not open a PR. Write "this repo needs `update rules`" in the mail instead. If the cause is "ignored", there is nothing to change in pinqdoq. Put it under "Runner için öneri" with what the runner should check in future (e.g. re-read the rule before the PR gate).
4. Record it in the task, as `missed_rules: [{"rule": "<file:line>", "cause": "...", "pr": "<url or null>"}]`.

## Where the lesson goes
Follow pinqdoq's `CLAUDE.md` and `README.md`. Keep the existing heading structure, and never repeat a rule that lives in another file.
- A coding or testing rule for one stack goes in `rules/<stack>-*.md` (it auto-loads by `paths:`). A rule for every language goes in `rules/common.md`.
- A long explanation or example goes in `references/<stack>/…`, with a one-line rule in `rules/` pointing to it.
- How a skill should behave goes in `skills/<skill>/SKILL.md` (e.g. `pinq_code-review` should have caught it: add it to its checklist).
- If the lesson is only about this runner's own procedure, it does not go into pinqdoq. List it in the run mail under "Runner için öneri" so the owner can update the runner skill.
Write the rule as a short, concrete instruction in the file's own style. Add a ❌/✅ example only when the file already uses them. Do not cite the PR inside the rule text; put the source in the PR body.

## Opening the PR
- Branch `lesson/<repo>-<pr number>-<slug>` from `origin/main`, one commit (`docs(rules): …` / `feat(skills): …`), push, then:
  `gh pr create -R pinqponq/pinqdoq --base main --assignee <lesson_pr_reviewer> --title "<type>(<area>): <rule in a few words>" --body-file <file>`
- Write the body in Turkish (the team reads it), with these sections:
  - `## Kaynak`: link to the review comment, mail or chat decision, and the runner PR it came from. Summarize it; do not paste the whole text.
  - `## Ne yanlış gitti`: one or two sentences.
  - `## Eklenen kural`: the rule, and the file it went into.
  - `## Neden genel`: why it applies beyond this task.
  - End the body with the attribution line from the conversation's system reminder, if there is one.
- Never merge it, never push to `main`, and do not ping anyone but the reviewer.
- Record it in the task with `state_tx.py task <key>`, as `lesson_prs: [{"url": …, "from_change_request": "<received_at>"}]`, and list it in the run mail under "Tamamlananlar" (`Ders PR'ı: <link>, <rule in one line>`).
- The lesson PR is not part of the task's PR gate. If it fails (e.g. a push error), note it in the run mail and continue; never block the task on it.
