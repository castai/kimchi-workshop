# Instructor guide (run-of-show)

For whoever runs the event - Cast AI or community. Anyone should be able to
run event #10 from this file as cheaply as event #1.

## Before the event (T-7 days)

1. **Fork the repo** to the event org, set the workshop tag: edit
   `.kimchi/tags.json` -> `workshop:<city-date>`. Commit. This is what makes
   every request from the room attributable on the console.
2. **Registration form** captures OS, shell, current tool (Claude Code /
   Cursor / OpenCode / none). Drives the personalized setup email.
3. **Setup email 1** (goes T-7): install instructions per OS from the
   README quick start, signup link, and "complete `kimchi` first run at
   home - the login flow includes a captcha and venue WiFi will hurt."
4. **Load-test the tier**: if the room will be on community tier, know how
   the shared queue behaves at N concurrent users before you promise it.

## T-1 day

5. **Setup email 2**: `kimchi --version` check, the verify command list,
   and a TA support address. Target: 80% arrive with a working install.

## Room setup

- Projector shows the instructor terminal, not slides. 5-minute welcome
  is the only slide content that exists.
- TA ratio 1:10-15. Module 0 is where they earn it.
- One presenter drives; one watches the stuck queue (form replies / hands).
- Print the one-pager: quick start, challenge list, tag command.

## Run of show (2.5h)

| Time | Module | What happens |
| --- | --- | --- |
| 0:00 | Welcome (5) | Tag yourself: this event's console filter is the scoreboard |
| 0:05 | 0 - Mise en place (20) | Clone, `/workshop-setup-check`, `/tags add attendee:<handle>` |
| 0:25 | 1 - First bite (10) | Challenge 1: Red to Green. Phase footer, verify don't trust |
| 0:35 | 2 - The five cooks (15) | Ctrl+P single vs multi, `/multi-model`, Challenge 2 + Same Dish Two Cooks |
| 0:50 | 3 - Teach it a recipe (15) | Challenge 3: write the release-notes skill |
| 1:05 | 4 - Plug in a tool (10) | Add an MCP server from the provided config |
| 1:15 | 5 - The long ferment (25) | Challenge 4/6: `/ferment new "..."` on a backlog level |
| 1:40 | 6 - Close your laptop (10) | `/teleport`, close, reconnect from Web IDE |
| 1:50 | 7 - The bill (10) | Console: filter by workshop tag, show the room's live spend |
| 2:00 | 8 - Take it home (10) | Submissions, self-paced lab, sprint invite |
| 2:10 | Wrap (5) | Feedback form (captures module-0 product findings), credits, community |

Timeboxes are hard. If the room is slow, cut module 4 (MCP), never module 7
(the bill) - the live cost view is the differentiator.

## Scoring at the end

- Attendees run `scripts/score.py` or file the submission issue.
- Organizer runs `scripts/leaderboard.py` on the fork, commits
  `leaderboard.json`, projects it.
- Prizes: credits + swag. The real prize is their own repo, features shipped.

## Failure modes

| Symptom | Fix |
| --- | --- |
| Login/captcha wall at the venue | They skipped setup email 1. TA side-channel: pair them with a neighbor for module 1, fix account after |
| `.kimchi` trust prompt surprise | Expected - approve it. Project tags need trust; covered in module 0 |
| Community tier queue slowdown | Have event-issued service keys ready (Budget Course needs them anyway) |
| Ferment runs long past timebox | `/ferment pause` + teleport it; it finishes overnight (that's the Pickle) |
| Web IDE track unavailable for an attendee | Move them to the managed CLI track; offline Ollama is the fallback |

## After

- Overnight: let the teleported ferments finish; send the "wake up to a PR"
  email at 9am with each attendee's link.
- 14-day activation: sessions carrying the event tag on your console. That's
  the funnel number - no other workshop can measure it.
- File module-0 setup failures as product issues; the workshop is also UX
  research for onboarding.
