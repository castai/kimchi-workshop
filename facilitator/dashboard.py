#!/usr/bin/env python3
"""Kimchi workshop facilitator dashboard - local edition.

Renders a single-page HTML report of registrations, participants, current
event, and leaderboards from the gh-pages branch of castai/kimchi-workshop.
Nothing leaves your machine: auth happens via the `gh` CLI's existing read
token; the only network calls go to api.github.com / raw.githubusercontent.com.

Usage
    python3 dashboard.py                  # build -> prints report path
    python3 dashboard.py --open           # build + open the file in a browser
    python3 dashboard.py --event TEST-002 # filter to one event code
    python3 dashboard.py --watch 30       # rebuild every 30s until Ctrl-C
                                          # (does not re-open the window)

Prerequisites on any machine (mac, linux, windows/WSL)
    python3 >= 3.9
    gh CLI installed and logged in as a user with read access to
        castai/kimchi-workshop        [brew install gh && gh auth login]
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = "castai/kimchi-workshop"
PAGES_BRANCH = "gh-pages"
HERE = pathlib.Path(__file__).resolve().parent
REPORTS_DIR = HERE / "dashboards"


def gh_token():
    proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit("gh CLI not logged in - run `gh auth login` first (needs read access to castai/kimchi-workshop)")
    return proc.stdout.strip()


def fetch_json(token, path):
    url = f"https://raw.githubusercontent.com/{REPO}/{PAGES_BRANCH}/{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def list_dir(token, path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={PAGES_BRANCH}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            items = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    return items if isinstance(items, list) else []


def collect(event_filter=None):
    token = gh_token()
    data = {}
    data["current_event"] = fetch_json(token, "current_event.json")
    data["leaderboard"] = fetch_json(token, "leaderboard.json")

    data["events"] = {}
    for item in list_dir(token, "events"):
        if item.get("type") != "dir":
            continue
        ev_name = item["name"]
        if event_filter and ev_name.upper() != event_filter.upper():
            continue
        regs = fetch_json(token, f"events/{ev_name}/registrations.json") or {"registrations": []}
        data["events"][ev_name] = regs.get("registrations", [])

    data["participants"] = {}
    for item in list_dir(token, "participants"):
        if item.get("type") != "file" or not item["name"].endswith(".json"):
            continue
        handle = item["name"].replace(".json", "")
        pdata = fetch_json(token, f"participants/{item['name']}")
        if not pdata:
            continue
        if event_filter and (pdata.get("event_code") or "").upper() != event_filter.upper():
            continue
        data["participants"][handle] = pdata
    return data


def esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def stat_bars(rows, key):
    tally = {}
    for r in rows:
        v = r.get(key) or "unset"
        tally[v] = tally.get(v, 0) + 1
    return tally


def render_html(data, event_filter):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ce = data.get("current_event") or {}
    events = data.get("events") or {}
    lb = data.get("leaderboard") or {}

    all_regs = []
    for ev_name, regs in events.items():
        for r in regs:
            r2 = dict(r)
            r2["_event"] = ev_name.upper()
            all_regs.append(r2)

    org_bars = stat_bars(all_regs, "org")
    desig_bars = stat_bars(all_regs, "designation")
    credit_pending = sum(1 for r in all_regs if (r.get("credit_status") or "pending") == "pending")
    credit_issued = sum(1 for r in all_regs if r.get("credit_status") == "issued")

    def card(title, body_html):
        return f"<section class='card'><h3>{title}</h3><div>{body_html}</div></section>"

    def dist_html(dist):
        if not dist:
            return "<p class='muted'>None yet.</p>"
        items = sorted(dist.items(), key=lambda kv: -kv[1])
        maxv = items[0][1] if items else 1
        out = []
        for k, v in items:
            pct = (v / maxv) * 100
            out.append(
                f"<div class='kv-row'><span class='k'>{esc(k)}</span>"
                f"<span class='v'>{v}</span>"
                f"<div class='bar'><i style='width:{pct}%'></i></div></div>"
            )
        return "".join(out)

    def table_for_regs(regs):
        if not regs:
            return "<p class='muted'>No registrations yet.</p>"
        cols = ["handle", "name", "org", "designation", "email", "event", "credit", "started"]
        head = "".join(f"<th>{c}</th>" for c in cols)
        rows_html = "".join(
            "<tr>"
            f"<td><code>{esc(r.get('github_handle') or '-')}</code></td>"
            f"<td>{esc(r.get('name') or '-')}</td>"
            f"<td>{esc(r.get('org') or '-')}</td>"
            f"<td>{esc(r.get('designation') or '-')}</td>"
            f"<td>{esc(r.get('email') or '-')}</td>"
            f"<td>{esc(r.get('_event') or r.get('event_code') or '-')}</td>"
            f"<td><span class='badge {esc((r.get('credit_status') or 'pending').lower())}'>{esc(r.get('credit_status') or 'pending')}</span></td>"
            f"<td class='mono-sm'>{esc((r.get('start_time') or '')[:19]).replace('T', ' ')}</td>"
            "</tr>"
            for r in sorted(regs, key=lambda x: x.get("joined_at", ""), reverse=True)
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table>"

    def table_lb(rows):
        if not rows:
            return "<p class='muted'>No accepted submissions yet.</p>"
        return (
            "<table><thead><tr><th>#</th><th>handle</th><th>attendee</th><th>tests</th><th>cost</th><th>points</th></tr></thead>"
            "<tbody>"
            + "".join(
                f"<tr><td>{r.get('rank')}</td>"
                f"<td><code>{esc(r.get('github') or '-')}</code></td>"
                f"<td>{esc(r.get('attendee') or '-')}</td>"
                f"<td>{r.get('tests_passed') or 0}/{(r.get('tests_passed') or 0) + (r.get('tests_failed') or 0)}</td>"
                f"<td>${r.get('cost_usd') or 0:.2f}</td>"
                f"<td>{r.get('points') or 0:.1f}</td></tr>"
                for r in rows
            )
            + "</tbody></table>"
        )

    lb_events = (lb.get("events") or {})
    lb_sections = []
    for ev_name, ev_blob in sorted(lb_events.items()):
        if event_filter and ev_name.upper() != event_filter.upper():
            continue
        rows = ev_blob.get("rows") or []
        lb_sections.append(
            f"<h4 style='margin:18px 0 6px;color:var(--muted)'>{esc(ev_name)} — {len(rows)} ranked</h4>"
            + table_lb(rows)
        )

    header_sub = f"generated {now}"
    if event_filter:
        header_sub += f" • event filter: {event_filter.upper()}"

    current_event_html = (
        f"<div class='ev-pill'><b>{esc(ce.get('event_code'))}</b> — {esc(ce.get('event_label'))}</div>"
        f"<div class='ev-meta'>started by <code>{esc(ce.get('started_by'))}</code> at {esc(ce.get('started_at'))}</div>"
        f"<div class='ev-meta'>credits per participant: <b>${ce.get('credits_amount_usd') or 0:.2f}</b></div>"
    ) if ce.get("event_code") else "<p class='muted'>No current_event.json on gh-pages.</p>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Kimchi facilitator dashboard - local</title>
<style>
:root{{--bg:#0f141a;--panel:#161c24;--panel-2:#1d242e;--border:#2a3340;
  --text:#e6eaef;--muted:#97a1ad;--accent:#4ade80;--warn:#fbbf24;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--text);padding:32px;max-width:1240px;margin:0 auto;}}
h1{{font-size:24px;font-weight:700;margin-bottom:4px;}}
.h-sub{{color:var(--muted);font-size:13px;margin-bottom:28px;}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:18px 22px;margin-bottom:18px;}}
.card h3{{font-size:14px;font-weight:700;margin-bottom:12px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.6px;}}
.ev-pill{{display:inline-block;background:rgba(74,222,128,.15);color:var(--accent);
  padding:6px 14px;border-radius:999px;font-size:14px;margin-bottom:8px;}}
.ev-meta{{color:var(--muted);font-size:13px;margin-bottom:4px;}}
.kv-row{{display:flex;align-items:center;gap:12px;padding:4px 0;}}
.kv-row .k{{width:200px;font-size:13px;color:var(--text);}}
.kv-row .v{{width:40px;text-align:right;font-size:13px;color:var(--accent);font-weight:700;}}
.kv-row .bar{{flex:1;height:6px;background:var(--panel-2);border-radius:3px;overflow:hidden;}}
.kv-row .bar i{{display:block;height:100%;background:var(--accent);border-radius:3px;}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);}}
th{{background:var(--panel-2);font-size:11px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.5px;}}
tr:hover td{{background:var(--panel-2);}}
.mono-sm{{font-family:"SF Mono",Consolas,monospace;font-size:12px;color:var(--muted);}}
.badge{{padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700;}}
.badge.pending{{background:rgba(251,191,36,.15);color:var(--warn);}}
.badge.issued{{background:rgba(74,222,128,.15);color:var(--accent);}}
.muted{{color:var(--muted);font-size:13px;line-height:1.6;}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:14px;margin-bottom:22px;}}
.summary-cell{{background:var(--panel);border:1px solid var(--border);
  border-radius:12px;padding:16px;}}
.summary-cell .stat{{font-size:30px;font-weight:800;color:var(--accent);}}
.summary-cell .label{{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.6px;margin-top:4px;}}
footer{{margin-top:32px;padding-top:18px;border-top:1px solid var(--border);
  font-size:12px;color:var(--muted);text-align:center;}}
</style></head><body>
<h1>Kimchi workshop facilitator dashboard</h1>
<div class="h-sub">{esc(header_sub)} • local-only - no data leaves this machine</div>

<div class="summary-grid">
  <div class="summary-cell"><div class="stat">{len(all_regs)}</div><div class="label">Registrations</div></div>
  <div class="summary-cell"><div class="stat">{len(set(r.get('github_handle') for r in all_regs))}</div><div class="label">Unique handles</div></div>
  <div class="summary-cell"><div class="stat">{credit_pending}</div><div class="label">Credits pending</div></div>
  <div class="summary-cell"><div class="stat">{credit_issued}</div><div class="label">Credits issued</div></div>
</div>

{card("Current event", current_event_html)}
{card("Registrations", table_for_regs(all_regs))}
{card("Distribution by org", dist_html(org_bars))}
{card("Distribution by designation", dist_html(desig_bars))}
{card("Leaderboards", "".join(lb_sections) if lb_sections else "<p class='muted'>None yet.</p>")}

<footer>local report - kimchi workshop facilitator tools</footer>
</body></html>"""


def run_once(event_filter, open_browser):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    data = collect(event_filter=event_filter)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    fname = f"dashboard-{ts}.html"
    out = REPORTS_DIR / fname
    with open(out, "w") as f:
        f.write(render_html(data, event_filter))
    latest = REPORTS_DIR / "latest.html"
    if latest.exists():
        latest.unlink()
    try:
        latest.symlink_to(fname)
    except OSError:
        pass
    print(f"report: {out.resolve()}")
    if open_browser:
        if sys.platform == "darwin":
            cmd = ["open", str(out.resolve())]
        elif sys.platform.startswith("linux"):
            cmd = ["xdg-open", str(out.resolve())]
        else:
            cmd = ["explorer", str(out.resolve())]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", help="filter to a single event code (e.g. TEST-002)")
    ap.add_argument("--open", action="store_true",
                    help="open the report in the default browser (macOS: `open`, Linux: `xdg-open`, Windows: `explorer`)")
    ap.add_argument("--watch", type=int, metavar="SECS",
                    help="rebuild every N seconds until Ctrl-C; does not reopen browsers automatically")
    args = ap.parse_args()

    if args.watch:
        print(f"watch mode - rebuilding every {args.watch}s, Ctrl-C to stop")
        try:
            first = True
            while True:
                run_once(args.event, args.open and first)
                first = False
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("stopped")
    else:
        run_once(args.event, args.open)


if __name__ == "__main__":
    main()