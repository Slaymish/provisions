# Provisions

A quiet, brandless interface for your weekly food shop. Pick meals, adjust
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
3. Review and download one JSON file for Hermes. It includes both the suggestions
   and your corrections, so removing a preference is recorded explicitly.
4. Hermes updates the grocery proposal and learns your corrections for next time.

For example, if a milk preference says “Light milk, high protein” and you remove
“high protein”, the export records the before and after text. Once Hermes
acknowledges it, “Light milk” becomes the local default. Clearing the field is
remembered too. New suggestions cannot silently undo a pending correction.

No LLM runs inside the app. The agent workflow uses ordinary JSON files and a
local HTTP API; it also works with another agent that follows the same contract.
Your agent must process the export for learning and list reconciliation to happen.

## Stores and pricing

Every installation has its own editable store label, fulfilment details, fees and
matching preferences. Startup and exports use saved prices, so planning works
without a catalogue connection; refresh prices explicitly when needed. The default `agent` mode lets Hermes prepare a proposal for
your shop. An optional `woolworths-nz` adapter searches Woolworths NZ and selects
products by unit price, respecting local matching rules and product pins.

A store label does not verify branch stock or pickup times. Other retailers do
not have built-in live price adapters. Totals describe the existing grocery
proposal; Hermes must reconcile meal edits before treating it as the next shop.
Purchasing and checkout are not automated.

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
| `index.html` | Interface, autosave, review and JSON download |
| `serve.py` | Local HTTP API, plan validation and handoff |
| `preferences.py` | Suggestions, explicit edits and durable learning |
| `local_data.py` | Private storage and atomic JSON writes |
| `provisions.py` | Grocery proposal and optional Woolworths NZ resolver |
| `agent.py` | Agent commands and first-run initialization |
| `build_plan.py` | Import an agent-authored private plan |
| `seed.py` | Add nouns from a private list |

Released under the [MIT license](LICENSE). Recipe photographs remain the property
of their publishers and are not included in the source distribution.
