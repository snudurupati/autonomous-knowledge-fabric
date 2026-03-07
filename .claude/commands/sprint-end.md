Do the following in order:

1. Run `pip freeze > requirements.txt` to capture all currently 
   installed packages

2. Write HANDOFF.md with these sections:
   - Sprint completed
   - What was built
   - What broke and how it was fixed
   - Real output observed (latency numbers, test results)
   - Next sprint goal

3. Run `git diff requirements.txt` and show me what new 
   libraries were added this sprint

4. Run `git add requirements.txt HANDOFF.md` and commit with 
   message: "Sprint [number] complete — update dependencies 
   and handoff notes"

5. Ask if any new conventions should be added to CLAUDE.md
