# Task: update-rules

Steps to execute when asked to update Claude rules or pinq-doq:

1. Pull the latest pinq-doq commit into `.claude/rules`:
   ```bash
   git submodule update --remote .claude/rules
   ```
2. Check if anything changed:
   ```bash
   git diff .claude/rules
   ```
3. If there are changes, commit the updated submodule pointer:
   ```bash
   git add .claude/rules
   git commit -m "Update Claude rules"
   ```
4. If nothing changed, inform the user that rules are already up to date.
