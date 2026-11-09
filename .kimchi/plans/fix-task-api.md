# Fix task-api (workshop incident)

## Goal
Bring the `task-api` service back into alignment with the policy docstrings
and the documented HTTP contract. 4 of 9 tests are failing in the rolled-back
state; this work makes all 9 pass and addresses the deeper docstring drift
called out in `PRODUCTION-INCIDENT.md`.

## Constraints
- Tests are read-only.
- Docstrings are the spec; where code and docstrings disagree, docstring wins.
- Never hardcode a secret.
- Every route must match the documented response shape.

## Failures observed
1. `test_secret_key_comes_from_environment` — `config.SECRET_KEY` is a literal
   `sk-live-…` string. Must come from the environment with a non-`sk-`
   fallback.
2. `test_create_task_requires_title` — `POST /tasks` crashes with `KeyError`
   when `title` is absent instead of returning 400.
3. `test_create_task_validates_priority` — Priority accepts `"high"` and
   `99`. Must be an integer in 1–5.
4. `test_list_tasks_status_filter` — `GET /tasks?status=open` returns the
   full unfiltered list. Two bugs: the route ignores `?status=`, and writes
   never invalidate the read cache so the GET serves stale data.

## Other drift from the spec
- `app/errors.py` defines error handlers but `create_app` never calls
  `register_error_handlers` → unmapped errors return HTML.
- `SlidingWindowLimiter.acquire()` blocks indefinitely; the docstring says
  the API should respond 429 when the limit is hit. `before_request` calls
  the blocking variant.
- `TaskStore.gc_stale_tasks` reaps by `updated_at` only when present, and
  uses an inconsistent `>` vs `>=` comparison. Docstring requires "age
  since LAST ACTIVITY (updated_at or created_at)".
- `TaskStore.merge_tasks` uses `>=` for incoming vs local; docstring says
  "on equal timestamps, keep local" → must be `>`.
- `datetime.utcnow()` is deprecated; comparisons across naive/aware values
  can silently misorder.

## Chunks

### 1. `app/config.py` — read SECRET_KEY from environment
Files: `app/config.py`
Accept: `SECRET_KEY` is sourced from `os.environ` and never begins with `sk-`.
Test coverage: `test_secret_key_comes_from_environment`.

### 2. `app/storage.py` — align with docstring policy
Files: `app/storage.py`
- `_now` → timezone-aware UTC.
- `_parse` → return timezone-aware datetime; safe on empty.
- `_iso` → normalize to UTC before serializing.
- `gc_stale_tasks` → reap open tasks whose last activity (`updated_at` or
  `created_at`) is strictly before `cutoff`. Keep non-open tasks.
- `merge_tasks` → overwrite local only when incoming `updated_at` is
  strictly later than local's.
Test coverage: covered transitively via `test_list_tasks_status_filter` and
the hidden review suite (docstring = spec).

### 3. `app/app.py` — fix routes, cache, and rate limit
Files: `app/app.py`
- `create_app` calls `register_error_handlers(app)`.
- `POST /tasks` validates `title` (non-empty string) and `priority`
  (integer 1–5 via `validate_priority`). On failure `abort(400, …)`.
- `GET /tasks` validates `?status=` is `open` or `completed`; any other
  value → 400. Passes the filter to `store.list_tasks`.
- Cache `tasks:list` is invalidated on create, complete, delete, sync, gc.
- Rate limiter uses `try_acquire` and returns a 429 JSON response with
  `Retry-After` when the limit is hit (instantiate once per app).
Test coverage: `test_create_task_requires_title`,
`test_create_task_validates_priority`, `test_list_tasks_status_filter`.

## Verification strategy
- `python -m pytest tests/ -q` → 9 passed.
- Manual smoke: `curl -s localhost:5000/health`, `POST /tasks`,
  `GET /tasks?status=open`.
- Confirm `git grep "sk-live"` returns nothing.

## Decision log
- Keep the test suite untouched. README is explicit.
- Use `abort(400, description=…)` so the wired error handler produces the
  exact `{"error":"bad_request"}` shape the contract requires.
- `validate_priority` already lives in `app/models.py` — reuse it.
- Limiter instantiated at app start (once) rather than per request; this
  also matches the docstring's sliding-window semantics over a process
  lifetime rather than per request.
- Cache key `tasks:list` matches the existing convention; we use
  `invalidate` rather than `invalidate_prefix` since the key is exact.

### Docstring rewrites — PR notes (per Part 1 of the agreement)

The following docstrings were rewritten from explicit `BUG:` placeholders
to plain policy statements. Behavior was restored to match each new
docstring in the same change; the notes below must travel with the PR
description so reviewers see the contract change explicitly.

- **`TaskStore.gc_stale_tasks`** (`app/storage.py`): old docstring carried
  a `BUG:` marker and `Fix so…` instruction. New docstring states the
  intended policy directly: reap open tasks whose last activity
  (`updated_at` if present, else `created_at`) is strictly older than the
  cutoff; non-open tasks are exempt. Code restored to match.
- **`TaskStore.merge_tasks`** (`app/storage.py`): old docstring carried a
  `BUG:` marker. New docstring states the policy directly: incoming
  `updated_at` must be strictly later than local's to overwrite; on
  equal timestamps, local wins. Code restored to match.
- **`TaskStore._parse`** (`app/storage.py`): docstring corrected from
  "the epoch (UTC)" to "the minimum representable datetime (UTC, year 1)"
  to match what `datetime.min` actually returns. No behavior change.
- **`config` module docstring** (`app/config.py`): rewritten from
  "Seed state: intentionally bad" to a policy statement forbidding
  embedded credentials. Reflects the incident finding.
- **`app/errors.py` module docstring**: added — declares the module as
  the single source of truth for HTTP error response shapes and forbids
  routes from building error responses directly.

## Risks
- Changing `datetime.utcnow` to aware UTC changes the serialized string
  shape. No test pins the format, but a hidden reviewer might. Acceptable:
  ISO-8601 with offset is the correct format and `_parse` handles it.
- Rate-limit fix changes a behavior no test exercises. Acceptable: the
  docstring mandates it and the current behavior would hang a process
  under load.
