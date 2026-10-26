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

> **Just here to play?** [`CHALLENGE.md`](CHALLENGE.md) — the brief,
> the rules, the submission path. No answers inside.
>
> **Facilitator pack?** Reference solutions, scoring design, and run-of-show
> live in the private `castai/kimchi-workshop-answers` repo.

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
git clone https://github.com/castai/kimchi-workshop.git
cd kimchi-workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**4. Verify the broken service**

```bash
python -m pytest tests/ -q
```

> ✅ **5 passed, 4 failed is the expected state.** The failures are the
> incident. See [`PRODUCTION-INCIDENT.md`](PRODUCTION-INCIDENT.md).

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

The service you are about to on-call for is broken in ways that interact:
the obvious fix in one place breaks something elsewhere. The visible test
suite is your entry ticket; the real bar is a verification suite the
scorer runs against your PR. Partial credit for depth, not speed.

> **Start here:** [`PRODUCTION-INCIDENT.md`](PRODUCTION-INCIDENT.md) for
> the incident context, then [`CHALLENGE.md`](CHALLENGE.md) for the rules
> and submission path.

Facilitators: the deeper design and reference material live in the private
`castai/kimchi-workshop-answers` repo on the `facilitator` branch.

---

## 🏆 Scoring

Full model is in `scripts/score.py` (`compute_points` docstring).

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

Every accepted submission lands on the [live workshop leaderboard](https://castai.github.io/kimchi-workshop/) - event dropdown (run a
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
app/                  the incident-damaged task tracker (Flask)
tests/                 the service contract - fix the app, not the tests
CHALLENGE.md           participant brief and rules
PRODUCTION-INCIDENT.md the incident report that explains the failures
.kimchi/
  tags.json           project + workshop tags (attribution)
  skills/             workshop-setup-check, skill template
scripts/              score.py, leaderboard.py, run.sh
.github/              CI (tests + leaderboard rebuild), submission issue form
```


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
