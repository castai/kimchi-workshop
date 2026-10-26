#!/usr/bin/env python3
"""Append an email to a participant's personal inbox on gh-pages.

Runs as a CI helper. Reads/writes the published site checkout of gh-pages.

Usage:
  append_personal_mail.py \
    --site-dir <path to gh-pages checkout> \
    --handle <github handle> \
    --id <unique email id> \
    --from-name "Marcus Okafor" \
    --from-role "Senior SRE" \
    --from-bg "#0b5394" \
    --subject "..." \
    --category production \
    --body-file <path to body text file> \
    [--pr-url <url>]

Idempotent per (handle, id): re-running with the same id replaces the
existing email body in place rather than duplicating it.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site-dir", required=True)
    p.add_argument("--handle", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--from-name", required=True)
    p.add_argument("--from-role", default="")
    p.add_argument("--from-bg", default="#374151")
    p.add_argument("--subject", required=True)
    p.add_argument("--category", default="personal")
    p.add_argument("--body-file", required=True)
    p.add_argument("--pr-url", default="")
    args = p.parse_args()

    with open(args.body_file) as f:
        body = f.read().strip()

    inbox_dir = os.path.join(args.site_dir, "personal")
    os.makedirs(inbox_dir, exist_ok=True)
    path = os.path.join(inbox_dir, f"{args.handle}.json")

    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {"version": 1, "emails": []}

    email = {
        "id": args.id,
        "from": {"name": args.from_name, "role": args.from_role, "bg": args.from_bg},
        "subject": args.subject,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "category": args.category,
        "body": body,
    }
    if args.pr_url:
        email["pr_url"] = args.pr_url

    replaced = False
    for i, e in enumerate(data["emails"]):
        if e.get("id") == args.id:
            data["emails"][i] = email
            replaced = True
            break
    if not replaced:
        data["emails"].append(email)

    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    print(f"inbox: {'updated' if replaced else 'added'} '{args.id}' for @{args.handle} -> {path}")


if __name__ == "__main__":
    sys.exit(main())
