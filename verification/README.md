# verification/

Supplementary contract tests for the task API. They encode the policies the
module docstrings document (the spec per the challenge rules) and the
behaviors added during the incident fix and code review:

- request validation → `400 {"error": "bad_request"}` (title, priority,
  JSON object shape, malformed bodies — no 500/415 leaks)
- `GET /tasks?status=open|completed` filter and its 400 path
- cache honesty: every write invalidates listings (no stale reads)
- rate limiting: `429 {"error": "rate_limited"}` past the limit;
  `/health` exempt so LB/K8s probes never see throttling
- `merge_tasks`: equal timestamps keep local (docstring contract)
- `gc_stale_tasks`: age = last activity (`updated_at` or `completed_at`);
  records without parseable timestamps are kept, never silently reaped

`tests/` is the challenge's read-only scoring suite and is intentionally
untouched. Run both suites:

```bash
python -m pytest tests/ verification/ -v
```
