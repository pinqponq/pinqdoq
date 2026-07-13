# Project standards

Shared standards come from **pinq-doq**, vendored under `.pinq-doq/` and copied into `.claude/rules/` (auto-loaded — do not @import the scoped files). Skills are in `.claude/skills/`. Code-gen scripts: `.pinq-doq/scripts/`. Deep references: `.pinq-doq/references/`.

To pull newer standards later, tell Claude: **update rules**.

# pinq-doq

This repo contains shared Claude rules, skills, scripts, and references for PinqPonq projects.
When editing rule files, maintain the existing structure and heading hierarchy.
Do not add rules that are already covered in another file — check for duplication first.
Follow the layout and loading model in `README.md`: author rules under `rules/` (only these are copied into consumers and auto-load, scoped by `paths:`); keep skills under `skills/`, scripts under `scripts/`, deep references under `references/`, organizational context under `context/`, and authoring/meta docs under `meta/`.
`context/` holds non-code organizational knowledge (project portfolio, team members, tool conventions) used in place by skills — never copied into consumers.
