# Kimchi workshop facilitator tools

This folder is for whoever is running the workshop today. Everything here
is designed to work without cloning the repo.

## Quick start (on any machine)

You'll need Python 3 and GitHub's `gh` CLI logged in with read access to
this repo. On a Mac:

```sh
brew install gh
gh auth login    # pick whichever account has read access to castai/kimchi-workshop
```

Then **one curl + one run**:

```sh
curl -O https://raw.githubusercontent.com/castai/kimchi-workshop/challenge/facilitator/dashboard.py
python3 dashboard.py --open
```

The command:

1. Hits the GitHub API with your `gh auth token` (already on your machine
   after `gh auth login`) and reads this repo's `gh-pages` branch — the
   same source that powers the public leaderboard.
2. Writes a dashboard at `./dashboards/dashboard-<UTC timestamp>.html`.
3. Opens it in your default browser (`--open` only).

Filtering:

```sh
# only one event
python3 dashboard.py --event TEST-002 --open

# auto-refresh every 30s in the background (Ctrl-C to stop)
python3 dashboard.py --watch 30
```

Windows: replace `curl -O` with `Invoke-WebRequest -Uri <url> -OutFile dashboard.py`
in PowerShell, then run `python dashboard.py --open`.

Linux: same as Mac; `--open` calls `xdg-open`.

## What it does NOT do

- It never mutates anything on GitHub. Read-only.
- It never touches participant PII beyond what's already on the leader board
  for anyone to see plus the join-issue data (name / org / email you
  collected at intake).
- It does not need the participant's permission or even awareness — useful
  for moderation tooling.

## Where the data comes from

| File on gh-pages branch                       | What it carries                              |
|-----------------------------------------------|----------------------------------------------|
| `current_event.json`                           | the active event code, when it started        |
| `events/<code>/registrations.json`             | per-event join ledger                         |
| `participants/<handle>.json`                   | per-participant side record                   |
| `leaderboard.json`                             | ranked rows scored by the leaderboard workflow |

If a file is absent (fresh day, no joins yet) the section stays empty.

## Workflow reminders

- Rotate the event code: Actions → *Rotate event code* workflow → Run.
- Join-intake flow (participant side): they hit *Join event* on the public
  site, fill the modal, GitHub pre-fills an issue, they submit. Workflow
  `join.yml` (in `.github/workflows/`) validates the event code against
  `current_event.json`, records the registration here, sends a welcome
  email to that participant's `<handle>.json` inbox.

## Internal layout

```
facilitator/
├── README.md         ← this file
└── dashboard.py      ← the only script you need
```
