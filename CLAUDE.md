@rules/common.md

# pinq-doq

This repo contains shared Claude rules, skills, scripts, and references for PinqPonq projects.
When editing rule files, maintain the existing structure and heading hierarchy.
Do not add rules that are already covered in another file — check for duplication first.
Follow the layout and loading model in `README.md`: author rules under `rules/` (only these are copied into consumers and auto-load, scoped by `paths:`); keep skills under `skills/`, scripts under `scripts/`, deep references under `references/`, organizational context under `context/`, and authoring/meta docs under `meta/`.
`runner/` holds the pinqloq task runner (skill, agents; its web panel is the separate pinqponq/pinqponq-agents repo); it is linked into `~/.claude` per machine by `runner/skill/scripts/install.py`, never delivered into consumers. This repo is public: never put personal addresses, test account values, keys or project-internal environment details under `runner/` (they belong in the machine's `machine.json` or the project's `maestro/RUNNER.md`).
`context/` holds non-code organizational knowledge (project portfolio, team members, tool conventions) used in place by skills — never copied into consumers.
