# Provisions

A quiet, brandless input view for your week’s food. Pick meals, adjust
preferences, add the extras and give the plan back to your agent.

Provisions keeps the choices about food in front of you. Product selection,
price comparisons and personal planning happen behind those choices. It is a
local app, with no account, advertising or hosted personal database.

## Run locally

Python 3.9+; no third-party dependencies.

```sh
git clone https://github.com/Slaymish/provisions.git
cd provisions
python3 agent.py init
python3 serve.py
```

Open [localhost:8770](http://127.0.0.1:8770). Enter your store and collection or
delivery details in the header. Ask Hermes to create your first plan using the
[Hermes guide](docs/hermes.md) and [bundled skill](skills/provisions/SKILL.md).
The app starts empty; the files under `examples/` demonstrate the format.

## How it fits together

1. Hermes reads your local profile and prepares meals suited to your life. It can
   include recipe photos, short reasons and prefilled preferences.
2. You choose meals and edit the details. Notes stay with the right meal. Top-ups,
   snacks, household items and other requests have their own fields.
3. Review the week and click **Copy for Hermes**. The text includes your choices,
   edits and extras, including corrections on meals you did not choose.
4. Paste it into Hermes. Hermes learns your corrections and builds the shop.

For example, if a milk preference says “Light milk, high protein” and you remove
“high protein”, the paste records the before and after text. Once Hermes
acknowledges it, “Light milk” becomes the local default. Clearing the field is
remembered too. New suggestions cannot silently undo a pending correction.

No LLM runs inside the app. The agent workflow uses ordinary JSON files and a
local HTTP API; it also works with another agent that follows the same contract.
The app has no grocery list view. Hermes builds the shop from the paste.
**Download JSON** provides the full feedback IDs for durable local learning.

## Stores and pricing

Every installation has its own editable store and fulfilment details. Hermes
selects products and prices the shop itself if asked. The local grocery APIs
remain available as an agent price tool, including an optional `woolworths-nz`
resolver with personal matching rules and product pins.

A store label does not verify branch stock or pickup times. Other retailers have
no built-in live price adapter. Purchasing and checkout are not automated.

## Personal data stays local

Plans, preferences, selections, product history, exports and snapshots live in
`~/.provisions`, outside this repository. Set `PROVISIONS_HOME` to use another
private directory. Nothing is sent to GitHub or Hermes automatically. Do not
commit your personal data, and avoid placing the private directory in a checkout.
Recipe photos load from the credited publishers.

`python3 make_snapshot.py` writes a read-only preview to the private directory.
It includes personal data and must not be published. Photos require an internet
connection.

## Development

```sh
python3 -m unittest -q
```

Tests use isolated temporary profiles and a stub catalogue. See
[docs/hermes.md](docs/hermes.md) for schemas and commands.

| File | Purpose |
| --- | --- |
| `index.html` | Input view, autosave, review and clipboard handoff |
| `serve.py` | Local HTTP API, plan validation and handoff |
| `preferences.py` | Suggestions, explicit edits and durable learning |
| `local_data.py` | Private storage and atomic JSON writes |
| `provisions.py` | Grocery proposal and optional Woolworths NZ resolver |
| `agent.py` | Agent commands and first-run initialization |
| `build_plan.py` | Import an agent-authored private plan |
| `seed.py` | Add nouns from a private list |

Released under the [MIT license](LICENSE). Recipe photographs remain the property
of their publishers and are not included in the source distribution.
