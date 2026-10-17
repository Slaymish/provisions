# Using Provisions with Hermes

The interface is shared code; each person supplies a private profile and plan.
No API key or Hermes installation is required to run the interface. Hermes (or
another local agent) supplies the judgement and personalization through plans
and the weekly paste.

## Setup

Clone the repository, then run from its root:

```sh
python3 agent.py init
python3 serve.py
```

Open `http://127.0.0.1:8770`. Enter the store and collection/delivery details in
the header. Both fields save to the local profile. New installations start empty.
`PROVISIONS_HOME` changes the private directory from `~/.provisions`;
`python3 serve.py 8772` changes the port. Set
`PROVISIONS_URL=http://127.0.0.1:8772` for agent commands on that port.

To let Hermes discover the bundled skill, copy the skill directory into its
personal skills directory (do not overwrite an existing customized skill):

```sh
mkdir -p ~/.hermes/skills
cp -R skills/provisions ~/.hermes/skills/provisions
```

The skill needs the location of your checkout. Tell Hermes where you cloned it,
or start Hermes in the checkout. You can also give Hermes this document directly.
It uses ordinary terminal/HTTP tools; there is no separate agent service, key,
account integration or background scheduler.

A starting request:

> Use Provisions in this checkout to plan my food for the week. Read my local
> profile, use what you know about my schedule and preferences, and ask about
> important gaps. Prefill meal and top-up preferences, include recipe photos and
> short reasons, and import the plan. When I paste my choices back, learn my
> edits and build the shop from them.

## Private files

The private directory holds:

- `profile.json`: store, fulfilment, catalogue, fees, durable preferences and human
  corrections not yet acknowledged by the agent.
- `plan.json`: the agent-authored meals and top-ups.
- `selection.json`: meal choices, include/skip states, current note drafts and extras.
- `state.json`: grocery proposal, product pins and price history.
- `exports/`: downloaded handoff copies. `snapshot.html` is private too.

The public checkout contains only code, this contract and clearly labeled sample
files. None of those samples is imported automatically. Keep personal JSON out of
Git. The `.gitignore` is an extra safeguard; review files before publishing.

## Agent commands

All mutations except `init` use the running local server, sharing its lock.
JSON paths may be `-` for standard input.

```sh
python3 agent.py context
python3 agent.py profile /private/path/settings.json
python3 agent.py import /private/path/week.json
python3 agent.py export
python3 agent.py articles /private/path/groceries.json
python3 agent.py learn /private/path/provisions-export.json
```

`context` returns the profile, plan and effective selections. `export` returns
`path` and `document`. **Download JSON** provides the same document;
**Copy for Hermes** is the primary handoff.

Profile updates merge these fields: `store`, `fulfilment`, `catalogue`, `fees`,
`preferences`, `resolver_rules`. An empty preference string is meaningful.
For example, `{"preferences":{"item:milk":"Light milk"}}` supplies a suggestion
for that stable key. Do not modify `preference_overrides` directly.

`catalogue` is `agent` by default. Hermes proposes products and prices for the
named shop. `woolworths-nz` enables the existing Woolworths NZ search resolver.
Changing the store text is not a store-specific availability check and does not
switch adapters. Pickup fees and bag fees are supplied locally, never assumed.
The app has no grocery list view. The agent builds the shop and can use
`GET /api/list?refresh=1` for new Woolworths prices when asked to price it.
The current resolver does not verify store-specific stock, pickup slots or checkout.

For Woolworths, `resolver_rules` maps nouns to objects containing `query`,
`require`, `avoid`, `size`, `by` (`kg` or `pack`) and optional `default_qty`.
These are personal matching settings, not shared brand defaults. Unit-price
comparison still applies, and a pinned SKU takes precedence if available.

## Plan shape

See `examples/plan.example.json`. The minimal document has a string `version`
and `slots` list; every slot has an `options` list. Optional `topups` is a list.
Slot, option and top-up IDs should be stable. Positional IDs remain supported
but cannot preserve meaning when entries move.

Each meal option and top-up can have:

- `name`, `items` (objects with `noun` and optional `label`).
- `preference_key`: a stable semantic key independent of weekly IDs, such as
  `meal:eggs-on-toast` or `item:milk`.
- `preference`: the agent's prefilled preference text, at most 4,000 characters.
- `reason`: optional short rationale, shown under a collapsed “Why this?” control.
- `summary` and `serves` for meal cards.
- `image`, `image_source`, `image_credit`: prepared-dish photo URL, recipe page,
  and publisher credit. Use real recipe photos, not product pack shots.

A stored profile preference takes precedence over the plan's suggested text.
An unacknowledged human correction takes precedence over both. New plan imports
retire per-plan note drafts while retaining human corrections by stable key.
Choices and extras remain local; old choices no longer in the plan are omitted
from exports. A `store` in an old plan is not the current store setting; use the
profile endpoint instead.

## Edits and learning

The frontend prefills notes via `GET /api/selection`. It saves human changes with:

```json
{"slot":"breakfast","option":"eggs-on-toast","note":"English muffins instead of bread"}
```

```json
{"topup":"milk","note":"Light milk"}
```

An empty `note` is an explicit clear, not permission to use a default again.
The export retains the usual chosen meals, all top-ups and their include/skip
states and extras. It has no `articles` or `totals` keys. Each chosen meal and
top-up carries `note` plus `preference` with the stable key, suggestion, final text and edited
state. Top-level `preference_feedback` also includes corrections from unchosen
meals and earlier plan entries so they cannot disappear just because the meal
wasn't selected this week.

Example feedback:

```json
{
  "id": "unique-edit-id",
  "key": "item:milk",
  "suggested": "Light milk, high protein",
  "previous": "Light milk, high protein",
  "text": "Light milk",
  "change": "edited",
  "edited_at": "<UTC timestamp>"
}
```

Hermes should interpret the removed qualifier as a correction to its remembered
preference. It should not infer an ongoing taste from a meal choice, a skipped
item or an untouched blank field. Extras are for this shop unless explicitly
stated otherwise. Clarify contradictions with safety-critical constraints.

After processing the export, run `agent.py learn` with that exact file. This
folds final text into `profile.preferences` and acknowledges the matching edit
IDs. It is safe to repeat. An older export cannot erase a newer human edit.
Learning changes preferences, not purchases or agent pricing state.
Keep other agent memories consistent with these explicit corrections, without
copying the person's private history into the public checkout.

The app stores only the latest pending correction per key. The suggestion and
final text remain in feedback even if autosave captured several interim edits.
Acknowledged edits remain in the user's saved export files.

## Clipboard handoff

`GET /api/handoff` returns `{"text": "...", "week_of": "..."}`. `week_of` is the
plan's date or an empty string. The text starts with the week, store and fulfilment,
then lists every slot in plan order with its choice (or `not chosen`) and any
explicit preference key.

Every chosen entry then carries one indented preference block, and the receiving
agent is expected to have no profile of its own, so the settled text always travels:
`pref:` is the final text when nothing changed this round, `now:` with `was:` is an
edit made in the app (an empty final text is `(cleared)`, and an empty suggestion
omits `was:`), and an entry with no settled text and no edit has no line at all.

Included top-ups follow as `name (note)`, or `top-ups: none`, with the same
preference block beneath them. Non-empty snacks, household and other extras follow.
Edited meal options that were not chosen appear under `changed but not chosen:` with
their keys and preference blocks, so a correction on a meal that lost the vote is
still visible. The final instruction tells Hermes to rebuild the shop, to treat
`pref:` as settled and `now:` as an edit of `was:`, and never to restore removed
text. The paste ends in one newline. A valid plain `YYYY-MM-DD` week is shown with
an English month name.

The app is the person’s input view and has no list view. Read the paste, apply
final preferences and build the shop yourself. If durable local acknowledgement
is needed, obtain the JSON export and use `agent.py learn` with its exact feedback
IDs; the paste does not contain acknowledgement IDs.

The grocery APIs remain an agent price tool. `agent.py articles` accepts
`{"items": [...]}` with `noun`, optional `id`/`label`, positive `qty` (default 1),
and `unit` (`ea` or `kg`). Optional `chosen` supplies a product resolution with
`name`, `price`, `unit_price` and optional `sku`, `size`, `unit_str`; `null` clears
it. Omitted resolutions are retained for matching IDs. See
`examples/articles.example.json`. Agent prices are proposals, and kilogram unit
prices must be per kilogram. Checkout remains a separate user action.

## HTTP equivalents

- `GET /api/profile`, `/api/plan`, `/api/selection`, `/api/handoff`
- `GET /api/list`: agent pricing tool; `?cached=1` uses saved prices, `?refresh=1` refreshes
- `POST /api/profile`: merge allowed settings and preference suggestions
- `POST /api/import`: import a validated plan
- `POST /api/selection`: save a meal choice, note, top-up or extra
- `POST /api/articles/import`: replace the grocery proposal
- `POST /api/export`: save and return the JSON learning document
- `POST /api/learn`: acknowledge feedback from the full export document

Requests use `Content-Type: application/json`. The server binds to loopback
and accepts browser writes only from its own origin. It serves only app routes;
it does not expose the private data directory as static files.
