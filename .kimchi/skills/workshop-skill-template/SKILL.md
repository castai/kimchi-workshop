---
name: workshop-skill-template
description: Fill-in-the-blank template for challenge 3 - teach the agent a recipe. Use when an attendee is asked to write their first Kimchi skill.
---

# Write your own skill

This file is the template for module 3 of the workshop. Fill in the blanks, save as a new directory under `.kimchi/skills/<name>/SKILL.md`, restart the session, invoke with `/<name>`.

## What goes in a skill

A skill is a directory with a SKILL.md like this one: YAML frontmatter (name, description) plus a markdown body of instructions. The description is what the agent matches on - make it say **when** to use the skill, not just what it does.

## Your turn

1. Create `.kimchi/skills/release-notes/SKILL.md`
2. Frontmatter: name `release-notes`, description "Generate release notes from recent commits; use when asked to draft release notes or a changelog."
3. Body: instructions you would give a new team member. Include at least:
   - how to list commits since the last tag (`git log <last-tag>..HEAD --oneline`)
   - group by Added / Changed / Fixed
   - end with the diffstat summary
4. Restart the session (skills load at session start), then run `/release-notes`

## Rules that make skills work

- Instructions specific and actionable; vague in, vague out.
- Under 5,000 tokens - long bodies dilute the signal.
- The slash command name must match the directory name.
