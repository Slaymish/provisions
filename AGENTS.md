# Provisions

Python 3.9+ and the standard library only; the frontend is plain HTML/CSS/JS.
Run `python3 -m unittest -q` for backend and preference-learning checks.

Personal profiles, plans, grocery state, snapshots and exports belong under
`PROVISIONS_HOME` (default `~/.provisions`), outside this checkout. Never publish
them or bake private data into an HTML file tracked by Git. Keep examples
explicitly synthetic. Use an isolated `PROVISIONS_HOME` for manual testing.

Preserve the brandless interface and short copy. Keep recipe photo source links.
Human preference edits, including explicit empty text, override agent suggestions.
Do not drop pending corrections on plan import or let an older export acknowledge
a newer edit. Agent-facing schema changes belong in `docs/hermes.md` and the
bundled Provisions skill.
