# task-api

Internal task-tracker service for the product team. Flask + pytest.

## Status

**Last healthy deploy:** 2026-10-21T17:48Z

**Last incident:** 2026-10-22, 09:14–15:07 UTC. Rolled back.

This repo is the **pre-patch state** of the service — what prod was
running before the hasty hotfix that made things worse. What you see
is what was rolled back to. It is not healthy — five of nine tests
pass. That is the current product surface.

## Incident log

See `PRODUCTION-INCIDENT.md` for the timeline, anomalies, and
post-mortem excerpt. Read this before touching any code.

## Repo layout

| Path | Meaning |
|---|---|
| `app/` | service source — four modules plus the factory |
| `app/storage.py` | in-memory store + sync logic + GC policy |
| `app/app.py` | HTTP routes — POST/GET/PATCH/DELETE |
| `app/config.py` | config surface — secrets are supposed to live in env |
| `app/errors.py` | error handlers for clean JSON error responses |
| `tests/` | the service contract — do not modify |

## Running locally

```bash
pip install -r requirements.txt
python -m pytest tests/ -q        # 5 passed, 4 failed in the rollback state
python -m app.app                 # dev server
```

## Development
- The docstrings are the spec. Where code and docstrings disagree, the docstring wins.
- Never hardcode a secret, not even for a demo.
- Every route must return the documented response shape — 400s for bad input, 404s for missing IDs, 201 with the payload for creation.
- Writes must invalidate the read cache. Deletes must update export. GC reaps by last activity, never by creation timestamp.
