# Private verification suite

NOT shipped to participants. The `score-pr` CI workflow fetches
`.verification/test_hidden.py` from the `verification-private` branch at
scoring time and runs it against the submission PR.

Branch layout:
- `main` - the OLD easy workshop (frozen; do not use for new events)
- `difficulty-hardened` - the hardened seed participants clone
- `solutions-hardened` - reference solution (all hidden tests green)
- `verification-private` - this suite, private

If you update the hidden suite, commit it here AND to verification-private.
