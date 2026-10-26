### Submission

<!-- Fill this block exactly as shown - the scoring workflow parses it. -->

```
attendee: <your-handle>
email: <you@example.com>
event: <event-code>
cost_usd: <your spend, e.g. 0.84>
```

**Upload the Kimchi usage CSV** for your session: [app.kimchi.dev/usage](https://app.kimchi.dev/usage) -> filter by `attendee:<your-handle>` -> Export -> drag the file into a comment below. **Submissions without the CSV are not considered for the leaderboard.**

**What I completed:** (challenges / backlog levels)

**Notes:** (anything the facilitator should know)

---

**How scoring works:**

- **Visible tests**: `pytest tests/ -q` - your entry ticket (max 9 passing)
- **Production scenario**: a hidden suite simulates your app under real load, security probes, and recovery. Posted as a "Production Log" on this PR.
- **Code review**: Kimchi Code Review scores the diff (0-100)
- **Efficiency**: cost_usd vs the event budget
- **Total** = tests + production + review + efficiency

A facilitator adds the `accepted` label when everything is in.
The leaderboard updates within a minute.
