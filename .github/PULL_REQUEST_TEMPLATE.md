### Submission

<!-- Fill attendee / email / event; those three are required. cost_usd is
     optional - an audit placeholder only. Your real spend, request count
     and model usage are pulled automatically from the Kimchi API (via your
     email) when the submission is accepted, so NO usage CSV upload is
     needed. -->

```
attendee: <your-handle>
email: <you@example.com>
event: <event-code>
cost_usd: <optional>
```

**What I completed:** (challenges / backlog levels)

**Notes:** (anything the facilitator should know)

---

**How scoring works:**

- **Visible tests**: `pytest tests/ -q` - your entry ticket (max 9 passing)
- **Production scenario**: a hidden suite simulates your app under real load, security probes, and recovery. Posted as a "Production Log" on this PR.
- **Code review**: Kimchi Code Review scores the diff (0-100)
- **Efficiency**: real Kimchi API spend vs the event budget (verified automatically at acceptance; the typed `cost_usd` is ignored for scoring)
- **Total** = tests + production + review + efficiency

A facilitator adds the `accepted` label when everything is in.
The leaderboard updates within a minute.
