# Workshop challenges

The repo you are holding is deliberately broken in three places, and its
backlog is deliberately unimplemented. Fix the app, not the tests. The
challenges below escalate; each one maps to a module of the tasting menu
(see workshop/AGENDA.md).

## How scoring works

Every challenge runs through your Kimchi session. Tag yourself first:

```
/tags add attendee:<handle>
```

Points: tests passing, PR review score, and cost efficiency. Full model in
workshop/SCORING.md. The leaderboard on the Kimchi console (filtered by
your event's tags) is the live scoreboard - cost, requests, models.

## The ladder

### Challenge 1 - Red to Green

`pytest` fails. Make it pass. Learn to prompt, watch the phase footer
(`↳ build`), and verify the result rather than trusting it.

- One failing test needs the API to reject bad input instead of crashing.
- There is an unwired helper in `app/errors.py` that renders a clean JSON
  400. Registering it is one line - finding where is the exercise.
- Bonus: `DEBUG = True` in `app/config.py` is production-adjacent rot.

### Challenge 2 - The Secret Ingredient

A secret key is hardcoded in `app/config.py`, and one endpoint trusts its
input more than it should. Find both with the agent, fix both, and check
the diff before you commit. First correct fix shown on the room screen
wins a prize.

### Challenge 3 - Teach It a Recipe

Write your first skill: `.kimchi/skills/release-notes/SKILL.md`. Fill in the
template in `.kimchi/skills/workshop-skill-template/SKILL.md`, restart the
session, invoke with `/release-notes`. Your skill must survive the
cross-agent test: it follows the open Agent Skills spec, so it also works
in Claude Code, Cursor, and any compliant agent.

### Challenge 4 - Backlog levels

Ship features from `workshop/BACKLOG.md`, in any order, one PR each:

- **Level 1 - Filter**: `GET /tasks?status=open` returns only open tasks.
  The store already filters; the route never asks it to.
- **Level 2 - Pagination**: `GET /tasks?limit=N&offset=M` with sane defaults
  and a `total` field in the response.
- **Level 3 - Export**: `GET /tasks/export` returns CSV; Content-Type right,
  streaming, no loading the whole file into memory twice.
- **Level 4 - OAuth**: "Add Google OAuth login" - the canonical Ferment
  goal from the Kimchi docs. This one is your Ferment Marathon entry.

### Challenge 5 - The Budget Course

Each attendee gets a service key with a hard cap. Ship a feature brief
under budget. The scorer computes your efficiency from your tagged usage;
the formula rewards output first, then cost. See workshop/SCORING.md.

### Challenge 6 - The Overnight Pickle

Still-running Ferment builds at the end of the day get teleported
(`/teleport`) and judged next morning. The room reviews the PRs together.

## Rules

- Fix the app, not the tests. Test files are read-only for scoring runs.
- Every challenge ends with a commit to your fork and (for challenges 4-6)
  a pull request - that is where the Code Review score comes from.
- Seeded defects are re-fixed per event run; the solutions branch
  (`solutions`) has per-module reference implementations.
