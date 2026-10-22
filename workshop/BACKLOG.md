# Feature backlog

Ship in any order, one PR per level. Tests for each level live in
`solutions/` on the solutions branch - do not peek before you ship.

## Level 1 - Filter

`GET /tasks?status=open` returns only open tasks.

- The store (`app/storage.py`) already has `list_tasks(status=...)`.
- The route (`app/app.py`) never passes the query param.
- Accept `open` and `completed`; anything else is a 400.

## Level 2 - Pagination

`GET /tasks?limit=N&offset=M` returns a page plus a `total` field.

- Defaults: `limit=20`, `offset=0`. Cap `limit` at 100.
- Response shape: `{"tasks": [...], "total": N, "limit": n, "offset": m}`.
- Combines with the level-1 filter.

## Level 3 - Export

`GET /tasks/export` returns CSV.

- Columns: id, title, status, priority, created_at, completed_at.
- Content-Type `text/csv`, `Content-Disposition` attachment header.
- Stream; do not load the whole file into memory twice.

## Level 4 - OAuth login

"Add Google OAuth login" - the canonical Ferment goal from the Kimchi docs.
Full flow: authorize URL, callback, session cookie, logout, tests. This is
the Ferment Marathon challenge; hand it to `/ferment` and let it run.
