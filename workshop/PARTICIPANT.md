# Participant guide - the Kimchi workshop

This is the complete walkthrough. Follow it top to bottom and you will
finish every challenge. Each challenge has: what it is, why it exists,
how to solve it in detail, and how to verify you solved it.

If you get stuck for more than 10 minutes on anything, ask - that is what
the room (or the community channel) is for.

---

## What you are working with

- **The repo**: a small task-tracker API (Flask + pytest) that is
  deliberately broken in three places, with four unimplemented features.
- **The agent**: kimchi, a terminal coding agent that routes each step of
  a task to the right model. You drive; it reads, writes, runs, verifies.
- **The game**: fix the rot, ship the features, write your own skill, and
  keep an eye on what it all cost. Points for output, points for
  efficiency, nothing for doing nothing.

Everything is open source (Apache-2.0). What you build is yours.

---

## Step 0 - Setup (do this before the session if you can)

Venue WiFi plus 40 people signing up at once is the number one way to lose
your first 30 minutes. Do this at home.

### 0.1 Install the agent

macOS / Linux:

```bash
curl -fsSL https://github.com/getkimchi/kimchi/releases/latest/download/install.sh | bash
```

or with Homebrew:

```bash
brew install getkimchi/tap/kimchi
```

Windows (PowerShell):

```powershell
irm https://github.com/getkimchi/kimchi/releases/latest/download/install.ps1 | iex
```

Verify:

```bash
kimchi --version
```

### 0.2 Get access

Sign up at app.kimchi.dev (no credit card needed) and log in once:

```bash
kimchi
```

First launch shows a login selector - use a Kimchi account and the browser
flow, or paste an API key from app.kimchi.dev/settings. If your workshop
handed you a shared event key instead, export it in your shell profile:

```bash
export KIMCHI_API_KEY=<the key you were given>   # add to ~/.bashrc / ~/.zshrc
```

Env keys do not persist between launches - the profile line matters, or
run `kimchi setup` once to persist login.

### 0.3 Get the repo and its dependencies

```bash
git clone https://github.com/kunalcast/kimchi-workshop.git
cd kimchi-workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 0.4 Confirm the seeded state

```bash
python -m pytest tests/ -q
```

Expected: **5 passed, 4 failed**. The failures are the workshop. If you
see collection errors instead, your venv is wrong - redo 0.3.

### 0.5 Launch the agent in the repo

Open a full-size terminal window (at least 80x24 - the first-run dialogs
need the room), then:

```bash
cd kimchi-workshop
kimchi
```

Three things happen on first run:

1. **Trust prompt** - the repo ships a `.kimchi/` directory (tags, skills).
   Choose **Trust**. Without it, the project tags do not load and your
   session is not attributed to the workshop.
2. **Login** if you have not already.
3. **Session-mode picker** - "What would you like to ferment?" Typing a
   goal here starts Ferment (autonomous project mode). Pick the
   just-chat option (arrow keys) if you want plain chat first; Ferment
   comes back in module 5.

### 0.6 Tag yourself - this is your leaderboard identity

In the kimchi prompt:

```
/tags add attendee:<your-handle>
```

Verify with `/tags` - you should see the project tags plus your
`attendee:` tag. Every request you make now carries these. The workshop
leaderboard is literally the usage console filtered by these tags.

Shortcut: run `/workshop-setup-check` and the agent verifies all of the
above for you (python, deps, seeded tests, tags, git identity).

---

## Module 1 - Red to Green (challenge 1)

**What it is**: make the failing tests pass by fixing the app.

**Why it exists**: the first skill in agentic coding is not prompting -
it is verifying. The agent will propose fixes; your job is to check the
result instead of trusting it.

**Step by step:**

1. Ask the agent to diagnose, not fix, first:

   ```
   Run the tests (.venv/bin/python -m pytest tests/ -q) and tell me
   which tests fail and why. Don't fix anything yet.
   ```

   You will get a report like: missing-title test crashes with a
   KeyError, bad-priority test returns 201 instead of 400, the secret
   key is hardcoded, the status filter is ignored.

2. Understand the shape of the problem. Two of the failures are input
   validation failures:

   - `POST /tasks` with no title crashes with `KeyError: 'title'` and
     surfaces as a 500. The test wants a 400 with
     `{"error": "bad_request"}`.
   - `POST /tasks` with `priority: "high"` or `99` is accepted (201).
     The test wants a 400.

   Notice `app/errors.py`: it contains `register_error_handlers()` -
   clean JSON handlers for 400/404/500 - that were **written but never
   wired**. Nothing calls it. This is deliberate repo rot: the fix
   location is one line in `create_app()`:

   ```python
   from app.errors import register_error_handlers
   # inside create_app(), right after app = Flask(__name__):
   register_error_handlers(app)
   ```

   Wiring it means `abort(400, description=...)` in your routes now
   renders as `{"error": "bad_request", "message": ...}` - exactly what
   the tests assert.

3. Add validation to the `create_task` route in `app/app.py`:

   ```python
   payload = request.get_json(silent=True) or {}
   title = payload.get("title")
   if not isinstance(title, str) or not title.strip():
       abort(400, description="title is required")
   priority = payload.get("priority", 1)
   if isinstance(priority, bool) or not isinstance(priority, int) \
           or not 1 <= priority <= 5:
       abort(400, description="priority must be an integer 1-5")
   ```

4. Let the agent do it instead, with a good prompt:

   ```
   Fix the two validation failures (missing title, bad priority).
   Fix the app, not the tests. app/errors.py has an unwired helper
   you should use. Then run the tests and show me the result.
   ```

5. **Verify**: `python -m pytest tests/ -q` - the two validation tests
   go green. You should now be at 7 passed, 2 failed (secret key and
   filter remain - they are the next challenges).

**Learned**: prompting with constraints ("fix the app, not the tests"),
reading a diff before accepting it, and the habit of re-running the
suite yourself.

---

## Module 2 - The Secret Ingredient (challenge 2)

**What it is**: a security sweep - find the hardcoded secret, fix the
config, and flip the debug flag.

**Step by step:**

1. Point the agent at the class of problem, not the location:

   ```
   Audit this repo for security issues a reviewer would flag:
   secrets in source, debug flags, missing input validation. Report
   findings with file:line, then fix them. Show me the diff before
   committing.
   ```

2. What it should find in `app/config.py`:

   ```python
   SECRET_KEY = "sk-live-kimchi-workshop-9f8e7d6c5b4a"   # the leak
   DEBUG = True                                            # the flag
   ```

   The fix reads both from the environment:

   ```python
   import os
   SECRET_KEY = os.environ.get("TASK_API_SECRET", "dev-only-insecure-key")
   DEBUG = os.environ.get("TASK_API_DEBUG", "false").lower() == "true"
   ```

   The fallback is fine for a dev workshop; in a real service the
   process would fail fast if the env var is missing.

3. **Verify**: `test_secret_key_is_not_hardcoded` passes; the app still
   boots (`curl localhost:5000/health` after `flask run`, or just trust
   the suite). You should now be at 8 passed, 1 failed.

**Learned**: the reviewer role in action - the strongest-model pass over
your diff - and the discipline of showing diffs before commits.

**Bonus for the competitive**: first correct diff shown on the room
screen wins a prize.

---

## Module 3 - Teach it a recipe (challenge 3: write a skill)

**What it is**: skills are reusable instruction packs (a SKILL.md with
YAML frontmatter) that the agent loads on demand. You will write one.

**Step by step:**

1. Look at the shipped examples: `.kimchi/skills/workshop-setup-check/`
   and `.kimchi/skills/workshop-skill-template/`. A skill is just a
   directory with a `SKILL.md` inside.

2. Create `.kimchi/skills/release-notes/SKILL.md`:

   ```markdown
   ---
   name: release-notes
   description: Generate release notes from commits since the last tag.
     Use when asked to draft release notes or a changelog.
   ---

   # Release notes

   1. Find the most recent tag: `git describe --tags --abbrev=0`
   2. List commits since: `git log <tag>..HEAD --oneline`
   3. Group them under Added / Changed / Fixed
   4. End with `git diff --stat <tag>..HEAD` as a summary
   ```

   The `description` is what the agent matches on - say **when** to use
   the skill, not just what it does.

3. Restart the session (skills load at start), then invoke it:

   ```
   /release-notes
   ```

4. **Verify**: the agent produces grouped notes from the git history.

**Learned**: the portability trick - the SKILL.md format follows the
open Agent Skills spec, so the same file works in other agents that
support it (Claude Code, Cursor, ...). Kimchi also auto-discovers
existing skills from those tools' directories if you have them.

---

## Module 4 - Plug in a tool (MCP, 10 minutes)

**What it is**: connect one MCP server so the agent gains a tool it did
not have.

**Step by step:**

1. Open `~/.config/kimchi/harness/mcp.json` and add a stdio server:

   ```json
   {
     "mcpServers": {
       "everything": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-everything"]
       }
     }
   }
   ```

   (Any stdio MCP server works; `everything` is the standard test one.
   Needs Node installed.)

2. Restart kimchi, run `/mcp` to see it registered, then ask the agent
   to use one of its tools.

3. **Verify**: the agent calls the server's tool in the session.

If you already use Claude Code or Cursor: `kimchi setup` imports your
existing MCP servers automatically. Check `/mcp`.

---

## Module 5 - The long ferment (challenges 4 and 6)

**What it is**: Ferment is autonomous project mode - goal in, phases
out, subagent workers execute, results get graded. You will ship a
backlog feature with it.

**Step by step:**

1. Pick a backlog level from `workshop/BACKLOG.md`. Level 1 (the status
   filter) is the guided one:

   ```
   /ferment new "Implement backlog level 1: GET /tasks?status=open
   returns only open tasks; invalid status returns 400"
   ```

2. The scoping flow: it interviews you, proposes **completion criteria**
   (accept them), then a **plan** (one phase, a few steps). At the plan
   review you choose: execute locally, execute in auto mode, execute in
   a remote workspace, or revise.

3. Watch it work: the dashboard widget shows phases and steps; the
   status line shows which model is running what (`/ferment progress`
   for detail).

4. **The fix itself, for reference** - the store already filters
   (`TaskStore.list_tasks(status=...)` in `app/storage.py`); the route
   in `app/app.py` just never passed the query param:

   ```python
   @app.get("/tasks")
   def list_tasks():
       status = request.args.get("status")
       if status is not None and status not in ("open", "completed"):
           abort(400, description="status must be open or completed")
       return jsonify(store.list_tasks(status=status))
   ```

5. Higher levels (from `workshop/BACKLOG.md`):
   - **Level 2 - pagination**: `?limit=N&offset=M`, defaults 20/0, cap
     100, response `{"tasks": [...], "total": N, "limit": n, "offset": m}`.
   - **Level 3 - CSV export**: `GET /tasks/export`, right headers,
     streamed.
   - **Level 4 - OAuth**: "Add Google OAuth login" - the canonical
     Ferment goal. Hand it over completely:

     ```
     /ferment new "Add Google OAuth login" 
     ```

     ...and let it run. Manual mode if you want to approve each phase,
     auto mode if you trust it.

6. **Verify**: `python -m pytest tests/ -q` - the filter test goes
   green (9 passed if you did modules 1-2 first). For levels 2-4 you
   write the tests yourself first, then let the ferment satisfy them.

**Learned**: the difference between chatting an agent through a task and
delegating a project - and where each is right.

---

## Module 6 - Close your laptop (teleport)

**What it is**: move a running session to the cloud, disconnect,
reconnect from a browser.

**Step by step:**

1. With a ferment running (module 5), type:

   ```
   /teleport
   ```

2. Close the terminal. Walk away. The session keeps running in a remote
   workspace.

3. Reconnect from the browser: the Web IDE (full VS Code in the browser
   with the Kimchi extension) or `kimchi` on any machine plus
   `/remote-sessions`.

4. **Verify**: your session is alive with its history intact.

If your plan does not include Remote Workspaces, this module is a
live demo on the projector instead - same drama, someone else's
budget.

---

## Module 7 - The bill

Open the usage console (app.kimchi.dev) and filter by your
`attendee:<handle>` tag. That is your session: requests, models, tokens,
cost - the same view your team lead gets for the whole org.

Sanity checks: the room's aggregate for a full 2.5-hour event runs to a
few dollars per person on open-weight models (the reference internal
hackathon ran ~1,580 sessions for about $4.4k total, caching doing 80%
of the work).

---

## Submitting your run

**The way to submit is a pull request.** Fork the repo, push your work to
your fork, and open a PR back to this repo titled
`[submission] <handle> - what you built`. The PR template gives you a
block to fill in:

```
attendee: <your-handle>
event: <event-code>
cost_usd: <your spend, e.g. 0.84>
review_score:
```

- `attendee` must match the handle you used for `/tags add attendee:...`
- `event` is the workshop code your facilitator announced (e.g.
  `berlin-2026-10-22`)
- `cost_usd` comes from your console export (Usage page, filtered by your
  attendee tag). Running the offline Ollama track? Put `0`.

**Then what happens:**

1. CI scores your PR automatically the moment you open it - tests run,
   points are computed, and the score shows as a check on the PR.
2. A facilitator reviews your code and the checks.
3. When they add the **`accepted`** label, the leaderboard updates within
   a minute and you get a comment on your PR with your points and rank.
4. The live board (linked from the README) has an event dropdown, a
   top-10/20/50 selector, and search - your facilitator projects it at
   the wrap-up.

The manual fallback (submission issue + `scripts/score.py`) still works
if you cannot open a PR for some reason.

Scoring, in full detail, is in `workshop/SCORING.md`. The shape:

| Component | Points |
| --- | --- |
| Each passing test | 10 |
| Code review score on your PR (0-100) | up to 50 |
| Cost efficiency vs budget | up to 20, or a capped penalty |

Output first, efficiency second: a cheap no-op loses to real work.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "No models available" on launch | Env key not set (see 0.2), or run `kimchi setup` |
| Trust-prompt options look cut off | Terminal window too small; resize and relaunch |
| Typing at first-run picker started a ferment | That is the picker default; arrow to just-chat, or roll with it |
| Tags not showing in /tags | You did not trust the project; relaunch and accept Trust |
| Ferment runs past the timebox | `/ferment pause`, or teleport it and let it finish remotely |
| pip install fails | Check python3 version (need 3.10+); recreate the venv |

Stuck on something else? The workshop channel / TA queue is the place.
