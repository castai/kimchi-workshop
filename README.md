<div align="center">

# 🥬 kimchi-workshop

**A hands-on workshop for the [kimchi](https://kimchi.dev) coding agent.**

Fix a deliberately broken repo. Ship real features. Write your own skill.
Delegate a project to an autonomous agent. Then look at the bill
together - because the leaderboard *is* the product's cost console.

[Quick start](#-quick-start) · [The challenges](#-the-challenges) · [Scoring](#-scoring) · [License](#-license)

**Apache-2.0** - fork it, run it, teach it. No permission needed.

</div>

---

## 🧭 What this is

| | |
| --- | --- |
| **The repo** | A small task-tracker API (Flask + pytest), deliberately broken in 3 places, with 4 unimplemented features |
| **The agent** | [kimchi](https://github.com/getkimchi/kimchi) - a terminal coding agent that routes each step to the right model |
| **The game** | Points for output (tests, review score), points for efficiency (cost vs budget). Nothing for doing nothing |
| **The twist** | Every request you make carries your tags. The workshop leaderboard is literally the usage console filtered by them |

The workshop runs in three formats off this one repo: a 2.5h guided lab
(the **tasting menu**), a half-day **builder sprint**, and a **self-paced
codelab** (you are doing that one right now).

> **Participant walkthrough, step by step, with every solution in
> detail:** [`workshop/PARTICIPANT.md`](workshop/PARTICIPANT.md)
>
> **Running the event?** [`workshop/FACILITATOR.md`](workshop/FACILITATOR.md)

---

## 🚀 Quick start

**1. Install the agent**

```bash
curl -fsSL https://github.com/getkimchi/kimchi/releases/latest/download/install.sh | bash
# or: brew install getkimchi/tap/kimchi
```

**2. Get access** - sign up at [app.kimchi.dev](https://app.kimchi.dev)
(no card), or export an event key if you were given one:

```bash
export KIMCHI_API_KEY=<key>    # add to ~/.bashrc or ~/.zshrc - env keys don't persist
```

**3. Clone and set up**

```bash
git clone https://github.com/kunalworldwide/kimchi-workshop.git
cd kimchi-workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**4. Verify the seeded state**

```bash
python -m pytest tests/ -q
```

> ✅ **5 passed, 4 failed is correct.** The failures are the workshop -
> and they are deeper than they look. The full contract is bigger than
> the visible suite (see `workshop/CHALLENGES.md`).

**5. Launch the agent (full-size terminal, 80x24+)**

```bash
kimchi
```

On first run: **Trust** the project (it has a `.kimchi/` config - tags and
skills need trust to load), log in, then tag yourself:

```
/tags add attendee:<your-handle>
```

Shortcut: `/workshop-setup-check` verifies all of it for you.

---

## 🍽️ The challenges

The full ladder with rules and solutions: [`workshop/CHALLENGES.md`](workshop/CHALLENGES.md)

| # | Challenge | Teaches | Time |
| --- | --- | --- | --- |
| 1 | **Red to Green** - make the failing tests pass | Verify, don't trust; the phase footer | 10 min |
| 2 | **The Secret Ingredient** - find the hardcoded key, fix the config | Security review; diff discipline | 15 min |
| 3 | **Teach It a Recipe** - write your first skill | Portable SKILL.md authorship | 15 min |
| 4 | **Backlog levels** - filter → pagination → export → OAuth | Feature shipping, one PR each | 25 min |
| 5 | **The Budget Course** - ship under a hard cap | Spend governance as a game | 10 min |
| 6 | **The Overnight Pickle** - teleported ferments, judged next morning | Delegation, remote execution | overnight |

The seeded defects, mapped:

| Defect | Where | Caught by |
| --- | --- | --- |
| Hardcoded `SECRET_KEY` | `app/config.py` | `test_secret_key_is_not_hardcoded` |
| Unwired error handlers | `app/errors.py` (written, never registered) | validation tests |
| No input validation | `app/app.py` `create_task` | validation tests |
| Ignored `?status=` param | `app/app.py` `list_tasks` | filter test |

---

## 🏆 Scoring

Full model: [`workshop/SCORING.md`](workshop/SCORING.md)

```
output     = tests_passed × 10 + (review_score / 100) × 50
efficiency = ±20 based on your spend vs the budget
points     = output + efficiency
```

- **Output first**: a cheap no-op always loses to real work.
- **Evidence required**: no usage export, no efficiency points.
- The leaderboard is the console filtered by your tags - cost, requests,
  models, latency, all live.

### 📊 The live board

Every accepted submission lands on the [live workshop leaderboard](https://kunaldas.net/kimchi-workshop/) - event dropdown (run a
whole series off one repo), top-10/20/50 selector, participant search,
60-second auto-refresh. Facilitators: the `accepted` label on a PR is the
whole evaluation action.

**Submitting is a pull request.** Fork, solve, open a PR titled
`[submission] <handle> - ...` with the template block filled in. CI scores
it automatically; a facilitator adds the `accepted` label; the live
leaderboard updates. Manual fallback: `scripts/score.py`.

---

## 🗂️ Repo layout

```
app/               the broken task tracker (Flask)
tests/             the specs - fix the app, not the tests
workshop/          PARTICIPANT.md, FACILITATOR.md, CHALLENGES.md,
                   BACKLOG.md, SCORING.md, INSTRUCTOR.md (run-of-show)
.kimchi/
  tags.json        project + workshop tags (attribution)
  skills/          workshop-setup-check, skill template
scripts/           score.py, leaderboard.py, run.sh
.github/           CI (tests + leaderboard rebuild), submission issue form
```

`solutions` branch: reference fixes for every challenge, all tests green.

---

## 🔌 Three access tracks

| Track | How | For whom |
| --- | --- | --- |
| **Managed** | kimchi account, full multi-model | The default |
| **Browser-only** | Remote Workspace + Web IDE, zero install | Locked-down laptops (needs a plan with Remote Workspaces) |
| **Offline** | `ollama pull llama3.2:1b`, pick it in `/model` | No account, no spend, air-gapped rooms |

---

## 📜 License

Apache-2.0. The app, the challenges, the skills, the scorer - all of it.
Run your own event without asking.
