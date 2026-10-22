---
name: workshop-setup-check
description: Verify the workshop environment - python, deps, repo state, tags. Use when an attendee runs this at the start of a Kimchi workshop session.
---

# Workshop setup check

Run these checks in order and report a compact table of results. Fix what you can (missing deps); report what you cannot (auth problems).

1. **Python**: `python3 --version` - need 3.10+.
2. **Dependencies**: `pip install -r requirements.txt` if imports fail. Run `python3 -c "import flask, pytest"`.
3. **Seeded state**: run `python3 -m pytest tests/ -q --no-header --tb=no`. Report the pass/fail counts. The seeded repo has failing tests on purpose - 5 passed, 4 failed means the environment is correct.
4. **Tags**: check that `.kimchi/tags.json` exists at the repo root and contains `project:kimchi-workshop`. Remind the user to run `/tags add attendee:<handle>` so their requests are attributed to them on the workshop leaderboard.
5. **Git identity**: `git config user.email` - needed for the pull request step.

End by telling the user exactly which challenge to start with (see workshop/CHALLENGES.md) and to run `/tags` to confirm attribution.
