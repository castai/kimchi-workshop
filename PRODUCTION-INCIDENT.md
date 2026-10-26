# Incident Report - task-api

**Date:** 2026-10-22
**Severity:** SEV2
**Status:** Resolved (upstream), reopened

---

## Summary

At 09:14 UTC on 2026-10-22 the `task-api` service began returning 500s
on a subset of `POST /tasks` requests. The on-call engineer paged the
original author at 09:41 UTC. A "quick patch" was merged at 10:03 UTC
without a full review. The patch passed the existing CI (5 of 9 tests
green) and was promoted at 10:22 UTC.

At 14:15 UTC, traffic monitoring flagged three anomalies:

1. **Error rate still elevated.** Roughly 3% of `POST /tasks` calls
   continued to 500, now with a different signature.
2. **Unexpected `SECRET_KEY` value.** A routine secret-scan detected
   a hardcoded `sk-` prefix key in the deployed config artifact.
3. **Unbounded response size.** `GET /tasks` began returning the full
   table on every request; the p99 jumped from 40 ms to 800 ms.

The service was rolled back at 15:07 UTC. The repo you are holding is
the state immediately before the hasty patch was merged.

## What "good" looks like

The store layer (`app/storage.py`) still carries the *intended* policy
docstrings - the author's original documentation of how the system was
supposed to behave. The hot-patch drifted from the docstrings in
several places.

Your job: bring the code back into alignment with the docstrings, get
the suite green, and do not break anything else.

## Service contract (excerpt)

| Endpoint | Method | Contract |
|---|---|---|
| `/health` | GET | `200 {"status":"ok"}` |
| `/tasks` | POST | `201` on success; `400` with `{"error":"bad_request"}` on invalid input |
| `/tasks` | GET | Optional `?status=open|completed`; `400` on any other status |
| `/tasks/<id>` | GET | `200` or `404` |
| `/tasks/<id>/complete` | PATCH | `200` on success |
| `/tasks/<id>` | DELETE | `200` or `404` |

## Known hot spots (do not trust this list)

- `app/app.py` - the hot-patch touched every route.
- `app/config.py` - the "quick fix" pasted a literal key.
- `app/errors.py` - error handlers that were written but never wired.

## Post-mortem excerpt

> The root cause was not a single bug. It was a chain of small
> assumptions that individually looked harmless: "title is just a
> string", "priority is just an int", "the store filters anyway",
> "we can hardcode this for the demo".
>
> Each assumption held in isolation. Together they made the service
> behave like a sieve: it accepted anything, leaked memory, and served
> stale data.
>
> The fix is not one line. It is a posture of suspicion.

---

*This incident is fictional. It is designed to teach verification,
not to shame any past employer.*
