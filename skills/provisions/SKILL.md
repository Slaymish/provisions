---
name: provisions
description: Read Provisions handoff pastes, author personal meal plans and learn preference corrections for a local Provisions installation. Use when the user asks to plan meals or groceries with Provisions, or supplies a Provisions paste or provisions.export.v1 file.
---

Provisions is the person’s input view for the week. It has no grocery list view
and runs no LLM. Read the paste, learn the edits and build the shop yourself;
price it if asked. Author the next plan for the app.

Locate the Provisions checkout and read `docs/hermes.md` there for the JSON
contract and commands. Run `python3 agent.py context` from that checkout to read
the current private profile, plan and selections. Start `python3 serve.py` if
needed. Use `PROVISIONS_HOME` and `PROVISIONS_URL` if this installation overrides
the defaults. Keep authored plans and exports in its private data directory.

Plan around what you already know of this person: schedule, budget, cooking
effort, dietary needs and tastes. Ask only for consequential missing information.
Use stable meal IDs and semantic `preference_key` values such as
`meal:eggs-on-toast` or `item:milk`. Prefill the `preference` text with known
preferences, and optionally provide concise `reason` text. Do not assume the
example plan's milk preference applies to them. Prefer photos of the prepared
dish from real recipe pages; include the image source and publisher credit.

The primary handoff is **Copy for Hermes** (`GET /api/handoff`). It lists choices,
included top-ups, extras and edited unchosen options. Treat `now:` as final;
`(cleared)` means empty text, and `was:` is what was edited away.

On receiving a JSON export, treat `preference_feedback` as explicit corrections.
A `text` of `""` is a deliberate clear. Use its `suggested`, `previous` and final
`text` to understand what changed. Removed qualifiers must not return in future
plans. A meal choice, skipped top-up or an empty untouched field alone is not a
new enduring preference. Treat extras as requests for this shop unless the person
says they are recurring. Never override allergy or other safety constraints based
only on a missing word; clarify a material conflict.

Build the shop from chosen meals, final notes, included top-ups and extras.
The paste has no feedback IDs. Obtain **Download JSON** or `agent.py export`
and use `agent.py learn` to acknowledge exact corrections locally. The JSON has
no `articles` or `totals`; it retains `preference_feedback`. Learning is
idempotent and ignores stale edits when the person has since changed the field.
The private profile is the app's durable preference store. Respect newer edits.

Import the next plan with `agent.py import`. Put new inferences in profile
`preferences` with `agent.py profile`; human edits take priority until learned.
Do not edit `preference_overrides` manually. Shop labels do not change the live
catalogue provider: only `woolworths-nz` has a built-in price adapter. For other
shops use `agent` mode and research products and prices yourself, stating
when a price is an estimate. `agent.py articles` and `/api/list` remain agent
price tools. Purchases and checkout remain separate user actions.
