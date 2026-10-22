# Workshop scoring

How points are computed for the leaderboard. The scoring is designed so
that **output first, cost second**: a high-output run always beats a cheap
no-op, but among equal outputs the cheaper run wins. There is no minimum
spend - doing nothing is never rewarded.

## Inputs

| Input | Source | Weight |
| --- | --- | --- |
| Tests passing | `scripts/run.sh` / CI | 10 points each |
| Kimchi Code Review score | Code Review add-on on your PR, 0-100 | up to 50 points |
| Token spend | Kimchi console usage export, per attendee tag | efficiency modifier |

## Formula

```
output  = tests_passed * 10 + (review_score / 100) * 50
cost    = total spend attributed to your attendee tag during the event window

if cost <= budget:      efficiency = (1 - cost/budget) * 20
else:                   efficiency = -min(cost - budget, budget)
points  = output + efficiency
```

The budget defaults to $2.00 per attendee and is set by the organizer per
event (`--budget` on `scripts/score.py`, or override per attendee for
special tracks). The over-budget penalty is capped at the budget value, so
overspending can never zero out real output.

## How to read the leaderboard on the Kimchi dashboard

The repo ships with `.kimchi/tags.json` containing `project:kimchi-workshop`
and `workshop:template`. Organizers fork the repo per event with
`workshop:<city-date>`, and every attendee adds:

```
/tags add attendee:<handle>
```

...on their first session. Every request then carries the project, workshop,
attendee tags, plus the automatic `model:` and `phase:` tags. The Usage and
Analytics pages filtered by those tags ARE the live leaderboard for cost,
requests, latency, and models used - the product is the scoreboard.

## Exporting your usage for scoring

1. Kimchi console -> Usage page.
2. Filter tags: `attendee:<your-handle>` + the event's workshop tag, date range = event day.
3. Export CSV.
4. Attach the CSV alongside your PR, or run:

```
python scripts/score.py --attendee <handle> --usage export.csv --pr <PR URL>
```

The scorer writes `submissions/<handle>.json`; the organizer (or CI on the
event fork) merges them into `leaderboard.json`.

## Attribution notes

- Tags resolve per session start. If you forget `/tags add attendee:<handle>`
  on day 1, your day-1 requests attribute to the project tag only. The
  workshop-setup-check skill reminds everyone in module 0.
- `model:` and `phase:` tags are automatic and reserved; they do not count
  toward the 10-tag cap.
- CI runs (`KIMCHI_TAGS="ci:true"`) can be excluded from scoring by the
  organizer filtering on the `ci:true` tag.
