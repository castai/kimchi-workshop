# Workshop challenges - hardened edition

The repo you are holding is broken in ways that do NOT fall to a single
prompt. Every defect interacts with another system: fixing the obvious
one breaks a policy test you cannot see. The visible test suite
(`pytest tests/ -q`, 4 failing) is the entry ticket. The real bar is a
hidden verification suite (V1-V9) the scorer runs against your PR -
points come from how much of that contract you satisfy.

Expect: 2+ hours, multiple diagnosis-fix-verify loops, and reading code
you did not write. If a hundred people start, a handful finish.

## The seeded defect map

| Area | File | The rot | The intended policy |
| --- | --- | --- | --- |
| Secret hygiene | `app/config.py` | hardcoded `SECRET_KEY`, `DEBUG=True` | env-driven, debug off by default |
| Input validation | `app/app.py` create | KeyError 500s, accepts any priority | 400s with JSON bodies; priority int 1-5 |
| Error wiring | `app/errors.py` | handlers written, never registered | clean 400/404/429/500 JSON |
| Rate limiting | `app/app.py` | limiter built PER REQUEST (never limits) | one shared limiter; 429 + Retry-After |
| Caching | `app/app.py` list | one key, ignores params; never invalidated | key includes status/limit/offset; writes invalidate |
| Pagination | missing | no limit/offset | `{"tasks", "total", "limit", "offset"}`, cap 100 |
| CSV export | missing | none | right headers, right columns, reflects deletes |
| GC policy | `app/storage.py` | recency vs created_at; active olds reaped wrongly | last ACTIVITY (updated_at > completed_at > created_at) |
| Sync merge | `app/storage.py` | incoming always wins, even when older | later updated_at wins; tie keeps local |
| Timestamps | `app/storage.py` | naive `utcnow()`; comparisons break | UTC-aware everywhere, round-trips |

## The rules

- Fix the app, not the tests. `tests/` is read-only for scoring.
- The store's policy docstrings describe the INTENDED behavior; the
  code does something else. Trust the docstring, not the code.
- Route handlers, cache keys, and the limiter interact: a fix in one
  place can break a contract elsewhere. Verify after every change.
- Submit via PR (see workshop/PARTICIPANT.md). CI runs the visible
  suite; the hidden suite decides your score.

## Difficulty design (for facilitators)

- The visible 4 failures look like the old easy workshop. They are not:
  two of them (filter, validation) now require the pagination contract
  and the cache to be correct at the same time.
- The hidden suite has 26 checks across 9 sections. Solving everything
  took the reference implementer (an agent, unhindered) a full session
  with several subtle policy fixes; a human pairing with an agent
  should budget 2-3 hours.
- Partial credit is the design: each V-section passed is real progress,
  so the leaderboard rewards depth, not speed.
