# The Challenge

You are looking at a task-tracker API that somebody shipped on a Friday
and never reviewed. It works well enough to demo and badly enough to be
a problem. Your job: get it production-ready and submit proof.

The visible test suite is your entry ticket:

```bash
git clone https://github.com/castai/kimchi-workshop.git
cd kimchi-workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

**4 failed, 5 passed.** Turn that red green. How is up to you.

That is the whole brief. Everything below is rules and logistics — not
hints.

---

## The rules

1. **Fix the app, not the tests.** Everything under `tests/` is
   read-only. If a test looks wrong, look again.
2. **The docstrings are the spec.** Where code and docstrings disagree,
   the docstring describes intended behavior. Make the code honest.
3. **Small, verifiable changes.** Re-run the suite after every edit.
   A broken intermediate step costs you time, not points.
4. **Use the agent.** This workshop exists to teach agent-assisted
   coding. Drive [kimchi](https://github.com/getkimchi/kimchi), verify
   what it produces, own every line you commit.
5. **Green visible suite is the floor, not the ceiling.** Your PR is
   also scored by a verification suite you cannot see. It checks the
   properties a reviewer would: not just "does this pass" but "is it
   actually right."

## Submitting

1. Fork this repo, push your work to your fork, open a PR titled
   `[submission] <your-handle> - <what you shipped>`.
2. Fill in the PR template block:

   ```text
   attendee: <your-handle>
   event: <event-code your facilitator announced>
   cost_usd: <session spend from app.kimchi.dev>
   review_score:
   ```

3. CI scores every PR automatically. A facilitator adds the `accepted`
   label when it passes review.
4. Watch the [live leaderboard](https://castai.github.io/kimchi-workshop/)
   — event dropdown, top-N, search, 60 s refresh.

## Scoring

```text
output     = tests_passed × 10 + (review_score / 100) × 50
efficiency = ±20 based on your spend vs the budget
points     = output + efficiency
```

A cheap no-op always loses to real work.

## Setup, if you have never used the agent

```bash
curl -fsSL https://github.com/getkimchi/kimchi/releases/latest/download/install.sh | bash
# or: brew install getkimchi/tap/kimchi

# Sign up at app.kimchi.dev (no card), or use the key your facilitator gave you
export KIMCHI_API_KEY=<key>
```

Inside the repo:

```text
kimchi            # Trust the project when asked — your tags need it
/tags add attendee:<your-handle>
```

Everything after that is the challenge.

---

Questions are free: ask the room. Answers are not — those you build.
