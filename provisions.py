#!/usr/bin/env python3
"""Provisions — the brandless supermarket layer over Woolworths NZ.

You ask for a noun ("apples", "milk", "cheese"). This module decides which SKU,
by your pinned preference first, then unit price, then this week's specials.
It never shows you marketing copy: label, amount, unit price, total.

Python 3.9 compatible. No third-party dependencies.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from local_data import DATA_DIR, load_profile

API = "https://www.woolworths.co.nz/api/v1/products"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"),
    "Accept": "application/json",
    "x-requested-with": "XMLHttpRequest",
    "Referer": "https://www.woolworths.co.nz/",
}

STATE_DIR = DATA_DIR
STATE_FILE = os.path.join(STATE_DIR, "state.json")
# Matching rules are private installation settings, authored by the user's agent.
RULES = {}


def profile():
    return load_profile(STATE_DIR)


def rules_for(noun):
    return profile().get("resolver_rules", {}).get(noun.lower(), RULES.get(noun.lower()))


def _money(x):
    return "${:,.2f}".format(float(x or 0))


def api_search(term, size=20):
    url = API + "?" + urllib.parse.urlencode({"target": "search", "search": term, "size": size})
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    return payload.get("products", {}).get("items", [])


def _unit(i):
    size = i.get("size") or {}
    cup = size.get("cupListPrice")
    price = i.get("price") or {}
    sp = float(price.get("salePrice") or price.get("originalPrice") or 0)
    if cup:
        return float(cup), "%s/%s" % (_money(cup), size.get("cupMeasure") or "ea")
    return sp, _money(sp)


def candidates(noun, rules):
    """All plausible SKUs for a noun, cheapest unit price first."""
    rules = rules or {}
    term = rules.get("query") or noun
    require = [t.lower() for t in rules.get("require") or [noun.lower()]]
    avoid = [t.lower() for t in rules.get("avoid") or []]
    size_hint = (rules.get("size") or "").lower()
    by = rules.get("by")
    out = []
    for i in api_search(term, 24):
        price = i.get("price") or {}
        if not price.get("salePrice"):
            continue                      # PromoTile and other non-products
        name = (i.get("name") or "").lower()
        size = i.get("size") or {}
        blob = " ".join([name, str(size.get("volumeSize") or ""),
                         str(size.get("packageType") or "")]).lower()
        if not all(t in blob for t in require):
            continue
        if any(t in blob for t in avoid):
            continue
        cup_measure = str(size.get("cupMeasure") or "").lower()
        if by == "kg":
            # loose produce: priced per kg and not a fixed-weight pack (e.g. a 400g tin)
            if "kg" not in cup_measure:
                continue
            if re.search(r"\d+\s*(g|ml|pack|each|ea)\b", str(size.get("volumeSize") or ""), re.I):
                continue
        if by == "pack":
            # a pack line must be a real fixed pack, not loose produce priced per kg
            vol = str(size.get("volumeSize") or "").strip().lower()
            if not vol or vol == "per kg":
                continue
        if size_hint and size_hint not in blob:
            continue
        up, upstr = _unit(i)
        out.append({
            "sku": i.get("sku"),
            "name": (i.get("name") or "").title(),
            "size": size.get("volumeSize") or "",
            "brand": (i.get("brand") or "").title(),
            "price": float(price.get("salePrice") or 0),
            "was": price.get("originalPrice"),
            "special": bool(price.get("isSpecial")),
            "save": float(price.get("savePrice") or 0),
            "unit_price": up,
            "unit_str": upstr,
            "stock": i.get("stockLevel"),
        })
    out.sort(key=lambda c: (c["unit_price"] or c["price"]))
    return out


def resolve(item, state=None, force=False):
    """Pick the SKU for one canonical item, honouring a pinned preference.

    Records what changed since the last look: price moves above/below a
    threshold, product swaps, stock trouble. Those become the only things the
    interface is allowed to shout about. `state` is passed in by the caller so
    price memory is written exactly once.
    """
    if profile().get("catalogue") != "woolworths-nz":
        return item
    if item.get("chosen") and not force and time.time() - item.get("resolved_at", 0) < 900:
        return item
    rules = rules_for(item["noun"])
    opts = candidates(item["noun"], rules)
    item["flags"] = []
    if not opts:
        item["chosen"] = None
        item["options"] = []
        item["error"] = "nothing matched"
        item["flags"].append({"kind": "no_match", "text": "no product matched"})
        return item
    pinned = item.get("pinned")
    chosen = None
    if pinned:
        chosen = next((o for o in opts if o["sku"] == pinned), None)
        if chosen is None:
            item["flags"].append({"kind": "unavailable", "text": "pinned product gone, substituted"})
    if not chosen:
        chosen = opts[0]

    # price memory, keyed by SKU, so week-on-week moves are visible
    if state is None:
        state = load_state()
    mem = state.setdefault("prices", {})
    prev = mem.get(str(chosen["sku"]))
    basis = chosen["unit_price"] or chosen["price"]
    if prev:
        old = float(prev.get("basis") or 0)
        if old > 0:
            pct = (basis - old) / old * 100.0
            if pct >= 8:
                item["flags"].append({"kind": "price_up", "text": "up %d%% since last week" % round(pct)})
            elif pct <= -8:
                item["flags"].append({"kind": "price_down", "text": "down %d%% since last week" % abs(round(pct))})
    mem[str(chosen["sku"])] = {"basis": basis, "price": chosen["price"], "ts": time.time()}

    last_sku = item.get("last_sku")
    if last_sku and str(last_sku) != str(chosen["sku"]):
        item["flags"].append({"kind": "swapped", "text": "different product than last week"})
    item["last_sku"] = chosen["sku"]

    if chosen.get("stock") is not None and chosen["stock"] <= 2:
        item["flags"].append({"kind": "low_stock", "text": "low stock"})
    if chosen.get("special") and (chosen.get("save") or 0) > 0:
        item["flags"].append({"kind": "special", "text": "on special"})

    item["chosen"] = chosen
    item["options"] = opts[:5]
    item["resolved_at"] = time.time()
    item["error"] = None
    if item.get("unit") is None:
        item["unit"] = "kg" if (rules or {}).get("by") == "kg" else "ea"
    save_state(state)
    return item


def line_total(item):
    c = item.get("chosen")
    if not c:
        return 0.0
    qty = float(item.get("qty") or 1)
    if item.get("unit") == "kg":
        return round(c["unit_price"] * qty, 2)
    return round(c["price"] * qty, 2)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"items": [], "updated": None}
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    """Persist state, but never let a wipe go unrecorded.

    If the previous file held markedly more items than the new one (a clear, a
    bad request, a race between two processes), keep the previous version beside
    it first so nothing is lost silently.
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE) as f:
            prev = json.load(f)
        prev_n = len(prev.get("items") or [])
        new_n = len(state.get("items") or [])
        if prev_n > 0 and new_n < max(1, prev_n // 2):
            with open(STATE_FILE + ".bak", "w") as f:
                json.dump(prev, f, indent=1)
    except Exception:
        pass
    state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def resolved_list(force=False, cached_only=False):
    state = load_state()
    items = []
    for it in state["items"]:
        if not cached_only:
            resolve(it, state=state, force=force)
        items.append({
            "id": it["id"],
            "noun": it["noun"],
            "label": it.get("label") or it["noun"],
            "qty": float(it.get("qty") or 1),
            "unit": it.get("unit") or "ea",
            "pinned": it.get("pinned"),
            "chosen": it.get("chosen"),
            "options": it.get("options", []),
            "flags": it.get("flags", []),
            "line_total": line_total(it),
            "error": it.get("error"),
            "note": it.get("note"),
        })
    save_state(state)
    subtotal = round(sum(i["line_total"] for i in items), 2)
    attention = []
    for i in items:
        for f in i["flags"]:
            if f["kind"] in ("no_match", "unavailable", "price_up", "swapped", "low_stock"):
                attention.append({"item": i["label"], "text": f["text"], "kind": f["kind"]})
    settings = profile()
    fees = settings.get("fees") or {}
    pickup_fee, bag_fee = float(fees.get("pickup", 0)), float(fees.get("bags", 0))
    return {
        "items": items,
        "subtotal": subtotal,
        "unpriced": sum(1 for i in items if not i.get("chosen")),
        "pickup_fee": pickup_fee,
        "bag_fee": bag_fee,
        "total": round(subtotal + pickup_fee + bag_fee, 2),
        "specials": sum(1 for i in items if (i["chosen"] or {}).get("special")),
        "saving": round(sum((i["chosen"] or {}).get("save", 0) for i in items if (i["chosen"] or {}).get("special")), 2),
        "attention": attention,
        "updated": state.get("updated"),
        "store": settings.get("store", ""),
        "fulfilment": settings.get("fulfilment", ""),
        "catalogue": settings.get("catalogue", "agent"),
    }


def default_qty(noun):
    rules = rules_for(noun) or {}
    if rules.get("default_qty"):
        return float(rules["default_qty"])
    return 1.0


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def add_item(noun):
    state = load_state()
    nid = slug(noun)
    if any(i["id"] == nid for i in state["items"]):
        return state
    rules = rules_for(noun) or {}
    state["items"].append({
        "id": nid,
        "noun": noun.lower().strip(),
        "label": noun.lower().strip(),
        "qty": default_qty(noun),
        "unit": "kg" if rules.get("by") == "kg" else "ea",
        "pinned": None,
        "note": None,
        "resolved_at": 0,
    })
    save_state(state)
    return state
