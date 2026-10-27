# Facilitator playbook — running a Kimchi workshop

This is the document to read **before** and **during** a workshop event. It
covers: what you're operating, what happens automatically, where to look
for problems, and the commands to run at each step. No repo clone required.
Everything is visible to you only; participants see a different surface.

At-a-glance flow:

```
[Facilitator]                 [Workshop system]                    [Participants]
    |                                |                                    |
    |--(1) Rotate event code ------>|                                    |
    |--(2) Share event code + site  |                                    |
    |                               |<--(3) join via site modal ---------|
    |                               |--(4) validate + record            |
    |                               |--(5) welcome email to inbox       |
    |                               |                                    |
    |                               |                                     |
    |--(6) Monitor dashboard ------>|                                     |
    |                               |                                     |
    |     [participant runs workshop against fork; CI produces scores]    |
    |                               |                                     |
    |                               |<--(7) accept via auto-review -----|
    |                               |--(8) leaderboard row + emails ----|
    |                               |                                     |
    |--(9) Read final leaderboard ->|                                     |
    |--(10) Thank + close out event |                                     |
```

Where the system lives:

| Piece                          | Where                                                               |
|---------------------------------|---------------------------------------------------------------------|
| Public participant site         | https://castai.github.io/kimchi-workshop/                            |
| Underlying data branch          | `gh-pages` on this repo (only the workflows touch it)                |
| Automation logic                | `.github/workflows/` on this repo plus `kimchi-workshop-answers`     |
| Your monitoring dashboard       | the `facilitator/dashboard.py` script in this repo (you host it locally) |
| Private scoring/test harness    | `castai/kimchi-workshop-answers` (private; never shared)             |

---

## Step 0 — Prep once per event (you, ~2 minutes)

Make sure you have:

- Python 3 and `gh` CLI on whatever device you're watching the dashboard from.
- `gh auth login` done with an account that can read this repo (e.g. `kunalcast`).

Verify your `gh` has the right account:

```sh
gh auth status
gh api user --jq '.login'
```

If the answer isn't the facilitator's GitHub handle, run `gh auth login`
and choose the right one.

## Step 1 — Set the event code (you, ~30 sec)

You run this once per workshop. The code is the shared secret between you
and attendees.

1. Go to **Actions** in the `castai/kimchi-workshop` repo on GitHub.
2. Click **Rotate event code (facilitator)** on the left.
3. Click **Run workflow** (top-right of the page).
4. Fill the form:
   - `event_code`: e.g. `COHORT-A-OCT27`. Stick to uppercase letters,
     numbers, and dashes. Keep it short — participants type it.
   - `event_label`: friendly name participants will see in the dashboard.
     e.g. `Toronto cohort A — Oct 27 2026`.
   - `credits_amount_usd`: e.g. `5.00`. This is what you'll allocate per
     participant later.
5. Hit **Run workflow**.
6. Wait ~10s. Refresh Actions list if you want to verify it succeeded.

The event code is now live. The system re-displays it at
`https://castai.github.io/kimchi-workshop/current_event.json`; the join
workflow immediately starts accepting it.

## Step 2 — Share with attendees (you, ~1 min)

Two things to share:

- Public workshop URL: `https://castai.github.io/kimchi-workshop/`
- The **event code** you set in Step 1.

Drop both in whatever channel the cohort uses. Suggested minimal send:

> Welcome to the Kimchi workshop. Two things you need:
>
> 1. Open https://castai.github.io/kimchi-workshop/
> 2. Event code: `COHORT-A-OCT27`
>
> Click *Join event* on the left rail, register with your real name/org,
> and the system will welcome you in your private inbox within ~1 min.

## Step 3 — Participants join (system-side, automatic)

What happens behind the scenes when a participant joins:

1. They open the site, type their GitHub handle in the top-right pill,
   the gate bubble dismisses.
2. They click the **Join event** button in the left rail.
3. A modal pops up: full name, designation, organization, work email,
   event code. They fill it.
4. They click **Submit via GitHub** — a new tab opens to a pre-filled
   GitHub issue on this repo (`[join] <name>`).
5. They click **Submit new issue**.
6. The `join.yml` workflow fires in the repo: parses fields, validates
   the event code, writes to `events/<code>/registrations.json`,
   and posts a "Welcome aboard" comment to the issue.
7. A **welcome email** is appended to that participant's
   `personal/<handle>.json` inbox — visible next time they refresh the site.

You don't press any button during this. It's fully automatic.

## Step 4 — Watch registrations (you, as the day progresses)

Download and run the local dashboard (one curl, one command):

```sh
curl -O https://raw.githubusercontent.com/castai/kimchi-workshop/challenge/facilitator/dashboard.py
python3 dashboard.py --open
```

What you see (refreshes each run):

- Summary cells: total registrations, unique handles, credits pending,
  credits issued.
- Current event card: the active code, who set it, when.
- Registrations table: everyone who joined, with `name`, `org`, `designation`,
  `email`, `event`, `credit status`, `start time`.
- Distribution bars by organization and designation — useful for the
  facilitator with mixed cohorts.
- Leaderboards section: ranked rows from the workshop leaderboard.

For live-ish updates during the day:

```sh
# Rebuild the dashboard every 30 seconds until you Ctrl-C
python3 dashboard.py --watch 30
```

(Auto-open happens only on the first build; rebuilds silently refresh the
same `latest.html` symlink.)

## Step 5 — Triage problems during the day

**A participant says "I submitted, but the site shows nothing yet."**

Probably jsut refresh-cadence: site auto-refreshes every 60s. Ask them
to hard-refresh (`Cmd+Shift+R`). If still nothing after ~3 min, check if
their issue landed in this repo:

https://github.com/castai/kimchi-workshop/issues?q=is%3Aissue+is%3Aopen+%5Bjoin%5D

If it landed, their `Join event` form data was valid but the event code
they supplied didn't match `current_event.json` (step 1). The workflow
will leave a clear comment on their issue with details.

**A participant complains about a wrong event code.**

They typed it wrong. Tell them your current code (check `current_event.json`
on gh-pages — the dashboard also shows it).

**A failed credit status.**

`credit_status` starts `pending`. Flipping to `issued` later is what the
credit-injector service does (not part of this release; placeholder under
`facilitator/credit_issuer.py` is on the roadmap). Until then, marking is
manual — useful ledger anyway.

**Participant shows up twice.**

They likely re-joined. Dedupe logic in `register_join.py` collapses by
`github_handle`. The ledger records one row per handle and a
`rejoined_count` instead of duplicating.

## Step 6 — After participants start shipping PRs

The scoring chain is automatic. Once a participant raises a PR with
title starting `[submission] `:

1. `score-pr.yml` runs the visible tests, posts a comment with the score.
2. `production.yml` runs the deeper production suite. Also comments + emails.
3. When score is good enough, `auto_review.py` (answers repo) auto-labels
   the PR `accepted`.
4. `leaderboard.yml` writes the leaderboard row + acceptance email.

You don't need to press anything. Just watch the leaderboard build in your
dashboard (`python3 dashboard.py --watch 30`).

## Step 7 — Close the event

When the workshop ends:

1. Actions → **Rotate event code** with a placeholder like `COHORT-A-OCT27-CLOSED`.
   This locks new joins against the old code immediately.
2. Grab the final leaderboard from the dashboard and screen-share it in
   your closing call.
3. Optional: make the leaderboard page public-shareable by exporting
   `leaderboard.json` to a JSON viewer (slide-deck plugin of choice, etc).

Rejoins during the closed window will be rejected with a "event code
mismatch" comment on their join issue. Reopen with a new code if you
need to.

---

## Troubleshooting quick reference

| Symptom                                    | Likely cause                       | Fix                                                                                        |
|--------------------------------------------|------------------------------------|--------------------------------------------------------------------------------------------|
| Join workflow run skipped                  | issue title doesn't start `[join]` | participant opens the wrong template; ask them to start over                               |
| Welcome email never arrives                | LLM frame failed or `KIMCHI_API_KEY` is not set on the repo | site still works; fall-back plain-text welcome writes successfully                      |
| `events/<code>/registrations.json` absent  | empty day so far                   | not an error, just graph noise                                                             |
| `dashboard.py` says "gh CLI not logged in" | wrong device or stale token        | `gh auth login` on that device                                                             |
| `dashboard.py: permission denied`          | file not executable                | `chmod +x dashboard.py` OR just run `python3 dashboard.py` (preferred)                     |
| You're running it on Windows               | PowerShell curl differs            | `Invoke-WebRequest -Uri <url> -OutFile dashboard.py`; rest the same                        |

## What's not in this playbook (deliberate)

- Scoring formula internals (that's in `kimchi-workshop-answers/.verification/auto_review.py`).
- Kimchi credit issuance (manual process for now; hooks left in participants JSON).
- The CastAI org secrets and secrets rotation (administers via Settings → Secrets).

## One-screen summary for co-hosts

> Workshop runs. Participants are joining. Watch the registrations with:
>
> `python3 dashboard.py --watch 30`
>
> If a participant says "I joined but nothing happened", ask for the issue
> link they just created; 99% of the time the event code didn't match.
>
> Closing time: rotate the code with `Run workflow` → `Rotate event code`.
> Final leaderboard is `events/<code>` in the dashboard.

Hand the co-host this README + the active event code. They don't need
anything else.
