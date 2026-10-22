# Kimchi Workshop - build an app with the governed coding agent

A hands-on workshop repo: a deliberately broken task-tracker app, a ladder
of challenges, and a leaderboard that is literally the Kimchi console
filtered by your tags. You fix real repo rot, ship real features, write
your own skills, and watch what multi-model routing does to your bill.

**Everything here is open source (Apache-2.0). Fork it, run it, teach it.**

## Quick start

```bash
# 1. install the agent (pick one)
curl -fsSL https://github.com/getkimchi/kimchi/releases/latest/download/install.sh | bash
brew install getkimchi/tap/kimchi            # macOS / Linux

# 2. clone and enter
git clone https://github.com/<org>/kimchi-workshop.git
cd kimchi-workshop

# 3. python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. verify the seeded state (4 failing tests is correct - 3 seeded defects)
python3 -m pytest tests/ -q

# 5. start the agent in the repo
kimchi
```

On first launch: log in, then **trust the project** when asked (it has a
`.kimchi/` config) - project tags only load from trusted projects, so the
workshop tag won't attribute without it. Then tag yourself:

```
/tags add attendee:<handle>
```

Or just run `/workshop-setup-check` and the agent walks you through it.

## The challenges

Read `workshop/CHALLENGES.md`. Short version:

| # | Challenge | What it teaches |
| --- | --- | --- |
| 1 | Red to Green | prompting, verification, the phase footer |
| 2 | The Secret Ingredient | security review, diff review discipline |
| 3 | Teach It a Recipe | writing skills (portable, Agent Skills spec) |
| 4 | Backlog levels 1-4 | feature shipping, one PR each |
| 5 | The Budget Course | spend governance as a game |
| 6 | The Overnight Pickle | Ferment + Teleport, judged next morning |

Scoring: `workshop/SCORING.md`. Backlog: `workshop/BACKLOG.md`.
Run-of-show for organizers: `workshop/INSTRUCTOR.md`.

## Three access tracks

The workshop works even if you cannot sign up on the spot:

1. **Managed** - Kimchi account, full multi-model. The default path.
2. **Browser-only** - Remote Workspace + Web IDE, nothing installed. Needs
   a plan that includes Remote Workspaces.
3. **Offline** - Ollama locally: `ollama pull llama3.2:1b`, keep it running,
   start kimchi, pick `ollama/llama3.2:1b` in `/model`. No account, no spend.
   Local models join explorer/reviewer/builder pools automatically.

## Repo layout

```
app/                the broken task tracker (Flask)
tests/              the specs - fix the app, not the tests
workshop/           challenges, backlog, scoring, instructor guide
.kimchi/
  tags.json         project + workshop tags (10-tag cap, trust required)
  skills/           workshop skills - setup-check + skill template
scripts/            score.py, leaderboard.py, run.sh
submissions/        per-attendee scoring records (created on demand)
.github/            CI (tests + leaderboard rebuild) + submission issue template
```

## Submitting

Open a PR for challenges 4-6 (that is what Code Review scores). Then either
attach your console usage export to the submission issue, or run:

```bash
python scripts/score.py --attendee <handle> --usage export.csv --pr <PR URL>
```

The submission issue template (`.github/ISSUE_TEMPLATE/submission.yml`)
captures handle, PR, cost, and notes. Organizers merge everything into
`leaderboard.json` via `scripts/leaderboard.py`.

## License

Apache-2.0. The seeded app, the challenges, the skills, the scorer: all of
it. Run your own event without asking permission.
