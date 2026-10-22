# Facilitator guide - running the Kimchi workshop

Everything you need to run the 2.5-hour tasting-menu session, from a
first-time TA to a repeat host. The participant-facing step-by-step is in
`workshop/PARTICIPANT.md` - this guide is about running the room.

Anyone should be able to run event #10 from this file as cheaply as
event #1. That is the whole design.

---

## What you are running

A hands-on lab, not a talk. 40-80 people, each at their own laptop, work
through a deliberately broken repo with the kimchi agent: fix the rot,
ship features, write a skill, run a ferment, teleport it to the cloud,
then look at the bill together. Two presenters, 1 TA per 10-15
attendees, no slides beyond a 5-minute welcome.

The three-beat promise to open with:

1. You will fix a broken repo with an agent and learn to verify, not
   trust.
2. You will delegate a whole feature to an autonomous run and watch it
   grade itself.
3. You will see exactly what it cost - per person, live, on the console.

---

## The two weeks before (T-14 to T-7)

1. **Fork this repo** to the event org. Edit `.kimchi/tags.json`:
   change `workshop:template` to `workshop:<city-date>`. That single
   edit is what makes every request from the room attributable on the
   console. Commit.
2. **Load-test the tier** if attendees will be on community tier: know
   how the shared queue behaves at N concurrent users before you promise
   it. Have event-issued service keys ready as the fallback (you need
   them for the Budget Course anyway).
3. **Registration form** captures: OS, shell, current tool (Claude
   Code / Cursor / OpenCode / none). This drives the personalized setup
   email and tells you how many import-migration wow-moments you will
   have in the room.
4. **Setup email 1** (T-7). Include, personalized by OS:
   - install one-liner (from the README quick start)
   - signup link (app.kimchi.dev, no card)
   - "complete `kimchi` first run at home - the login flow includes a
     captcha and venue WiFi will hurt"
   - the repo clone + venv + pytest check ("5 passed, 4 failed is
     correct - the failures are the workshop")
   - a TA support address that actually gets answered

## The day before (T-1)

5. **Setup email 2**: the `kimchi --version` check, the verify-command
   list, and "reply if stuck". Target: 80% arrive with a working
   install. Track replies; convert the strugglers before the room.

## Room setup

- Projector shows the instructor terminal. Not slides.
- **Terminal window size matters**: the first-run trust-prompt options
  truncate in small windows. Demo the trust prompt on the projector
  before anyone launches, and tell attendees to open a full-size
  terminal (80x24+ at normal font).
- One presenter drives; one watches the stuck queue (raised hands, form
  replies).
- Print the one-pager: quick start, challenge list, the tag command.
- Spare event keys on cards for the login-wall cases.

## Run of show (2.5 hours)

| Clock | Module (participant guide section) | What you do |
| --- | --- | --- |
| 0:00 | Welcome (5) | Tag command on screen; "the console is the scoreboard" |
| 0:05 | Module 0 - setup check (20) | Everyone clones, runs `/workshop-setup-check`, `/tags add attendee:<handle>`. TAs walk the room. **Do not start until 80% show green** - this module is load-bearing. |
| 0:25 | Module 1 - Red to Green (10) | Challenge 1. Diagnose-first prompting on screen. Phase footer callout. |
| 0:35 | Module 2 - the five cooks (15) | Ctrl+P single vs multi on the same task. Challenge 2 (Secret Ingredient) + the Same Dish Two Cooks race. |
| 0:50 | Module 3 - teach it a recipe (15) | Challenge 3: write the release-notes skill. Show the cross-agent portability angle. |
| 1:05 | Module 4 - plug in a tool (10) | MCP server add + `/mcp`. Cut this module first if running late. |
| 1:15 | Module 5 - the long ferment (25) | Challenge 4/6: `/ferment new` on a backlog level. Show `/ferment progress` on the projector. |
| 1:40 | Module 6 - close your laptop (10) | `/teleport` the running ferment, close the terminal, reconnect from the Web IDE on the projector. The theater moment. |
| 1:50 | Module 7 - the bill (10) | Console filtered by the workshop tag: the room's live spend on screen. **Never cut this module** - it is the differentiator. |
| 2:00 | Module 8 - take it home (10) | Submissions, the self-paced lab, the sprint invite. |
| 2:10 | Wrap (5) | Feedback form; credits; community link. |

## Teaching notes per module

**Module 0.** The setup-check skill does the verification for you; your
job is the 20% who are stuck. Every setup failure here is also free UX
research - write them down and file them as product findings.

**Module 1.** The teaching point is verify-don't-trust: make them read
the diff the agent shows before accepting it. Call out the phase footer
(`↳ build`) when it changes - that is cost attribution happening live.

**Module 2.** Run the security audit prompt on the projector and let the
room race you. The "first correct diff on screen wins" energy is what
makes the security module fun instead of a lecture.

**Module 3.** The reveal: after they write their skill, point out that
anyone with existing `.claude/skills` or `.cursor/skills` already had
theirs discovered. Migration is a feature demo wearing a workshop hat.

**Module 5.** Two visible groups will form: the cautious (manual mode,
approving each phase) and the bold (auto). Both are correct - say so.
If a ferment runs long, that is not a failure: pause it, teleport it,
and let it become an Overnight Pickle entry.

**Module 6.** Do the teleport on the projector with your own session,
dramatically close the terminal window, then reopen from the browser.
Then let them do it. If Remote Workspaces are not on their plan, this
module becomes the projector demo - say that plainly.

**Module 7.** Filter the console by the event tag, then by one
attendee's handle. Show both views. Ask the room to guess the number
before you reveal the day's total. Then the comparison: the internal
hackathon ran ~1,580 sessions for about $4.4k - caching did 80% of the
work. Cost per task, not per token.

## Scoring at the end

Submissions arrive as PRs titled `[submission] <handle> - ...` with the
template block filled in (attendee / event / cost_usd). The flow:

1. **CI scores every submission PR automatically** the moment it opens
   (tests + points math, no secrets involved, safe from forks). The score
   appears as a check plus a summary on the PR.
2. **You review and evaluate.** Read the diff, look at the checks, run
   anything you want locally.
3. **Add the `accepted` label** - that is the whole evaluation action.
   The leaderboard workflow records the submission, rebuilds
   `leaderboard.json`, comments the score and rank on the PR, and
   redeploys the live board to GitHub Pages.
4. **Project the board** at the wrap-up: event dropdown (multiple
   workshops / a whole series in one repo), top-10/20/50 selector, and
   participant search. It auto-refreshes every 60 seconds, so the room
   watches ranks move as you accept.

Create the `accepted` label once per repo (Settings → Labels or
`gh label create accepted --color 0E8A16`).

```bash
python scripts/leaderboard.py --submissions submissions/ --out leaderboard.json
```

## After the event

- **Overnight Pickle**: let the teleported ferments finish. At 9am send
  each attendee their PR link. "The workshop that keeps running."
- **14-day activation**: sessions carrying your event tag on the
  console. That is your funnel number - no other workshop can measure
  it.
- **File the module-0 findings** as product issues. The workshop is
  also onboarding UX research.

## Failure modes (tested - these actually happen)

| Symptom | Fix |
| --- | --- |
| Login/captcha wall at the venue | Skipped setup email. Pair them with a neighbor; fix the account after |
| "No models available" on launch | Env-key setups don't persist: `kimchi setup`, `/login`, or shell-profile export |
| Typing at the first-run picker started a ferment | Picker default; arrow to just-chat, or lean into it (module 5 preview) |
| Trust-prompt options truncated | Window too small; resize, relaunch, projector-walk the choice |
| Tags missing in `/tags` | Project not trusted; relaunch and accept Trust |
| Community-tier queue slowdown | Event-issued service keys (Budget Course stock) |
| Ferment blows the timebox | `/ferment pause` + teleport; it finishes overnight |
| Headless/scripted runs print nothing | Exit code and file state are the truth; check tests, not stdout |

## The repeatable-kit checklist (why event #10 costs like #1)

- [ ] Repo forked, workshop tag set to `<city-date>`
- [ ] Setup emails 1 and 2 scheduled
- [ ] Registration form captures OS/shell/current-tool
- [ ] Event keys printed (login-wall + Budget Course)
- [ ] Console access for the room's tag filter
- [ ] TA ratio confirmed (1:10-15)
- [ ] One-pager printed
- [ ] Post-event: overnight PR links out by 9am; activation check at day 14
