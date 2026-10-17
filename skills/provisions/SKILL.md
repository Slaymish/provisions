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

## First run: ask, then author

A fresh installation has an empty profile, so nothing about this person's habits
is recorded, and the plan under `examples/` is demo data rather than a default.
Before importing the first plan, ask one short message — five questions, not a
questionnaire:

1. Which shop, and when: store, collection or walk-in, and which day.
2. What they buy every week regardless of meals — milk, bread, eggs, coffee,
   drinks, cleaning, whatever it actually is. These belong as top-ups, because
   top-ups persist and a shop built only from meal ingredients arrives without
   them.
3. How breakfast and lunch really work: at home, at work, out, or skipped on
   some days.
4. How much cooking a weeknight gets, and which nights are hopeless.
5. Anything they do not eat, and anything they always want in the house.

Wait for the answers before importing a plan. One extra question round is cheaper
than a week of food they will not eat. On later runs ask only what changed.

## Authoring the plan

Plan around what you now know: schedule, budget, cooking effort, dietary needs and
tastes. Ask only for consequential missing information. Use stable meal IDs and
semantic `preference_key` values such as `meal:eggs-on-toast` or `item:milk`, and
give every top-up one too. Prefill the `preference` text with what you actually
know — portions, which meal consumes which article, what gets batch-cooked — and
optionally a concise `reason`. Do not assume the example plan's milk preference
applies to them. Prefer photos of the prepared dish from real recipe pages, with
the image source and publisher credit.

## Reading the paste

The primary handoff is **Copy for Hermes** (`GET /api/handoff`): a compact text
block, not JSON. It carries the settled preference text for every chosen entry, so
you do not need a profile to act on it:

- `pref:` is what they have settled on. Build from this, not from the meal name.
- If you did not author this week's plan, run `python3 agent.py context` first: the
  paste names the meals but not their ingredient nouns, and the plan holds those.
- `now:` / `was:` is an edit made this round. Learn `now:`; never restore `was:`.
- `(cleared)` is a deliberate empty text, not a missing value.
- `changed but not chosen` holds edits to meals that lost the vote this week.
- Included top-ups carry their final note; extras are one-offs unless they say
  otherwise.

## Learning from the JSON export

Treat `preference_feedback` as explicit corrections. A `text` of `""` is a
deliberate clear. Use `suggested`, `previous` and final `text` to understand what
changed. Removed qualifiers must not return in future plans. A meal choice, skipped
top-up or empty untouched field alone is not a new enduring preference. Never
override allergy or other safety constraints based on a missing word; clarify a
material conflict.

## Building the shop

Every chosen meal's ingredients, adjusted by its final preference, plus included
top-ups and extras. Say which articles came from a note rather than the meal's own
nouns, and flag minimum order quantities and near-duplicate products. The paste has
no feedback IDs: obtain **Download JSON** or `agent.py export` and run
`agent.py learn` to acknowledge exact corrections locally. The JSON has no
`articles` or `totals`; it retains `preference_feedback`. Learning is idempotent and
ignores stale edits when the person has since changed the field. The private profile
is the app's durable preference store; respect newer edits.

Import the next plan with `agent.py import`. Put new inferences in profile
`preferences` with `agent.py profile`; human edits take priority until learned. Do
not edit `preference_overrides` manually. Shop labels do not change the live
catalogue provider: only `woolworths-nz` has a built-in price adapter. For other
shops research products and prices yourself and state when a price is an estimate.
`agent.py articles` and `/api/list` remain the agent's price tools; the interface
calls none of them. Purchases and checkout remain separate user actions.
