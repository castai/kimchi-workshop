# Kimchi Workshop — getting started

Hey! Thanks for helping us test this thing. The whole flow is roughly:

1. **Join** the facilitator-led event so the scoring pipeline knows who's around.
2. **Read the briefings** in the workshop inbox (a fake Gmail inbox).
3. **Fork + fix** the broken Task-API on your machine with the Kimchi agent.
4. **Push commits** to your fork's `challenge` branch, watch the agent do its thing on every push.
5. **Raise a `[submission]` PR** against the facilitator repo and let the auto-review pipeline evaluate your work.
6. See yourself on the **leaderboard** with a weighted multi-factor score.

It's all set up like a fiction — briefings look like real emails, your commits trigger escalating "production unhappy" notes from Alex Rivera (Senior SRE), and Sam Carter (VP Engineering) mails you "you ranked" at the end. Kinda dumb, kinda fun. Don't take it too seriously.

---

## Prerequisites in 60 seconds

Before you start, you'll need:

- A **GitHub account** (any of yours works — personal, work, doesn't matter)
- A **Kimchi API key** from the facilitator (this is what lets you use Kimchi's agent to fix code; the facilitator generates one for you per event)
- About an hour of focus time (more if you also want to fuzz the production scenario)

That's genuinely it. No internal VPN, no special tooling.

---

## Step 1 — Register for the event

The facilitator gives you an **event code** (something like `TEST-001` or `KOL-001`). Keep it around.

1. Open [github.com/castai/kimchi-workshop/issues/new/choose](https://github.com/castai/kimchi-workshop/issues/new/choose).
2. Pick **"Join workshop event"** (template). 
3. Title: `[join] <your full name>` — anything else, the bot won't see you.
4. Fill out the body:
   - `full_name` — how you'd like the leaderboard to call you
   - `designation` — your role at Cast AI
   - `org` — usually "Cast AI"
   - `email` — any address where you'd actually receive Kimchi updates
   - `event_code` — the one your facilitator shared
   - `github_handle` — your GitHub username
5. Hit "Submit new issue".

Behind the scenes a bot registers you, stamps your **start_time** (which we use to compute "time-to-accept"), and drops a welcome comment on your issue. This timer gates the score, so register right when you're about to start work.

---

## Step 2 — Read the briefings

Open [castai.github.io/kimchi-workshop](https://castai.github.io/kimchi-workshop). You'll land on a Gmail-style inbox.

Look for the four briefings:

- **Start here: reclaiming task-api** — the framing story.
- **What actually happened (read once, remember)** — the production-incident context. Read this before forking.
- **The spec is the docstrings. That's it.** — critical contract detail.
- **How to submit your fix without breaking the pipeline** — how to push + title your PR.
- **The agent is a lever, not a driver** — Kimchi guidance.

You don't have to read them all at once, but they explain what broke and where the friction lives.

---

## Step 3 — Fork and run locally

1. [Fork castai/kimchi-workshop](https://github.com/castai/kimchi-workshop/fork) into your account.
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-handle>/kimchi-workshop.git
   cd kimchi-workshop
   ```
3. Switch to the `challenge` branch (this is the workshop's main):
   ```bash
   git checkout challenge
   ```
4. Sanity-check with `pytest`:
   ```bash
   pip install -r requirements.txt
   python -m pytest tests/ -q
   ```
   Expect: 4 failed, 5 passed. That's the rollback state.

---

## Step 4 — Use Kimchi to fix the bugs

Two ways to invoke the agent:

**A — Slash-commands from your terminal** (recommended):
```bash
agent/claude /fix failing-tests
agent/claude /fix debug-off-default
```
(You need to point Kimchi at the right model — see `/model` for options. We generally see best results with `kimi-k3` for the harder stages, `glm-5.3` for fast iterations, and `deepseek-v4-flash-0731` for the cheap loops.)

**B — Comment-driven PR reviews** — every commit triggers Kimchi to read your diff, post a code-review comment on your PR, and write a personalized email to your inbox (yes, the fake Gmail from step 2). It's verbose on purpose — the tone is "colleague watching you work," so take the praise with a grain of salt and the smirk with grace.

You don't need to write every fix yourself. Kimchi does most of the heavy lifting once the prompts point it in the right direction. The workshop's hidden mark is **how well you drive the agent**, not how fast you hand-write Flask code.

---

## Step 5 — Export your Kimchi usage CSV

When you finish iterating, download the **usage export** from [app.kimchi.dev/usage](https://app.kimchi.dev/usage). Whatever format the page gives you, keep it as `kimchi-usage.csv` (we look for that exact filename).

The pipeline parses the CSV to score:
- **Cost efficiency** (against a $2 budget — the closer you get without overshooting, the better)
- **Model diversity** (+2 points per distinct model you tried, max +10)
- **Request density** (log-scaled bonus for iterating smartly)

You have two ways to submit it:
1. **Best** — commit `kimchi-usage.csv` to the root of your fork's `challenge` branch and push.
2. **OK** — drag-drop the file as an attachment on a comment on your PR (yes, we read comment attachments).

If neither is present when your PR is scored, the auto-review **blocks** the acceptance. Hard rule, no exceptions. We've hit this exact failure mode multiple times in testing.

---

## Step 6 — Open your submission PR

1. Push your fixes on fork's `challenge` branch.
2. Head to your fork on GitHub → **Pull requests** → click **Compare & pull request**.
3. Base should be **`castai/kimchi-workshop` `challenge`**.
4. Title: `[submission]-<your-handle>-<event_code>` — keep this exact format, the workflows parse it (`[submission]-kunalworldwide-kol-001` for example).
5. Body — fill out the template:
   - `attendee:` — your display name (matches join)
   - `email:` — your contact (matches join)
   - `event:` — same code from join
   - `cost_usd:` — numeric total from the CSV you downloaded

6. Hit **Create pull request** and walk away for 5-7 minutes. The workflows will:
   - Run the visible test suite (9 tests)
   - Run the production scenario (26 hidden checks across 9 stages)
   - Fetch your CSV, validate cost, count models and requests
   - Have Kimchi's LLM do a code-review verdict
   - Tweet a verdict comment with the breakdown
   - Send you a "deployment is angry" or "production is happy" email via the on-site inbox

If all the gates pass, the `accepted` label gets added automatically, and a separate leaderboard workflow picks it up.

---

## Step 7 — See yourself on the leaderboard

Open [castai.github.io/kimchi-workshop](https://castai.github.io/kimchi-workshop), click the **Leaderboard** tab, and switch the Event dropdown to your event code.

Your row should show:
- Your **real name** (from the join form, not your handle)
- Your **weighted score breakdown** — visible tests, production tests, model diversity, request throughput, cost efficiency, time-to-accept, commit discipline, code-quality, and a full-clear bonus
- Your **score** — currently max theoretical ~116, with ~80-95 being a strong par score

If you don't appear, double-check the PR title starts with `[submission]` and the body has all four fields. The auto-review comment on your PR will tell you exactly what's blocking.

---

## What good runs look like

We've tested this internally a few times:

| Score pattern | What happened |
|---|---|
| **80+** | Used Kimchi efficiently, low cost, quick iterations, mixed models |
| **50-70** | Solid work, maybe overshot the $2 budget or took longer than 4h |
| **30-50** | Functional but slow — a lot of commits, one trick at a time, missed model diversity |
| **<30** | Struggled with the agent or brute-forced with too many commits / models |

There's no leaderboard shame — the highest score isn't necessarily the "winner" because the workshop is mostly about learning to drive Kimchi well.

---

## Getting stuck? Things that bite people

1. **"Auto-review blocked"** — read the PR comment carefully. The top blocking reason is usually a missing field or a missing CSV.
2. **"Visible suite 0/9"** — your code doesn't run. Don't panic — 9/9 isn't required; 8/9 still counts.
3. **"Production score N/26 below 15"** — the hidden tests found real bugs. Read the production log comment — Kimchi lists each failing scenario with a hint.
4. **CSV says $200+ but cost_usd=$2** — the auto-review will catch the mismatch. Read the error and re-submit with the right CSV.
5. **Nothing happens after my push** — check the workflow runs tab on the facilitator repo. If `Score submission PR` and `Production scenario` are both green but `Update leaderboard` never fired, something's blocking the auto-review (probably the CSV).

---

## Feedback (we explicitly want this)

When you finish — even if you bail halfway — drop your thoughts in:
- A Slack reply to the original announcement, OR
- An issue on [castai/kimchi-workshop](https://github.com/castai/kimchi-workshop/issues) with the title `[feedback] <one-line>`

Honest answers we want:
- Where did you lose context?
- Did you look at a briefing and still not know what to do?
- What did Kimchi do that was actually surprising?
- Where did the drama feel forced / fake?
- Would you onboard a new engineer with this?

Thanks for playing! 🥬
