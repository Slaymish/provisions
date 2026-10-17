#!/usr/bin/env python3
"""Provisions server — stdlib only. Run: python3 serve.py [port]"""
import json
import os
import sys
import threading
import time
import math
import re
from datetime import date
from local_data import atomic_json, save_profile
import preferences as F
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import provisions as P

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
PLAN_FILE = os.path.join(P.STATE_DIR, "plan.json")
SELECTION_FILE = os.path.join(P.STATE_DIR, "selection.json")
PLAN_LOCK = threading.RLock()


def load_plan():
    try:
        with open(PLAN_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": "provisions.plan.v1", "slots": [], "topups": [],
                "articles": [], "plan_missing": True}


def load_selection(effective=True):
    try:
        with open(SELECTION_FILE) as f:
            selection = json.load(f)
    except FileNotFoundError:
        selection = {}
    result = {"chosen": selection.get("chosen") or {},
            "topups": selection.get("topups") or {},
            "notes": selection.get("notes") or {},
            "topup_notes": selection.get("topup_notes") or {},
            "extras": selection.get("extras") or {"snacks": "", "household": "", "other": ""}}

    return F.effective_selection(load_plan(), result, P.profile()) if effective else result


entry_id = F.entry_id


def validate_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("version"), str) or not plan["version"]:
        raise ValueError("plan version required")
    if not isinstance(plan.get("slots"), list):
        raise ValueError("slots list required")
    seen_slots = set()
    for si, slot in enumerate(plan["slots"]):
        if not isinstance(slot, dict) or not isinstance(slot.get("options"), list):
            raise ValueError("each slot requires an options list")
        sid = entry_id(slot, "slot", si)
        if sid in seen_slots:
            raise ValueError("duplicate slot ID")
        seen_slots.add(sid)
        seen_options = set()
        for oi, option in enumerate(slot["options"]):
            validate_entry(option)
            oid = entry_id(option, "option", oi)
            if oid in seen_options:
                raise ValueError("duplicate option ID")
            seen_options.add(oid)
    if not isinstance(plan.get("topups", []), list):
        raise ValueError("topups must be a list")
    seen_topups = set()
    for ti, topup in enumerate(plan.get("topups", [])):
        validate_entry(topup)
        tid = entry_id(topup, "topup", ti)
        if tid in seen_topups:
            raise ValueError("duplicate top-up ID")
        seen_topups.add(tid)


def validate_entry(entry):
    if not isinstance(entry, dict):
        raise ValueError("meal options and top-ups must be objects")
    for key in ("preference", "reason", "summary"):
        if key in entry and (not isinstance(entry[key], str) or len(entry[key]) > 4000):
            raise ValueError("%s must be text under 4000 characters" % key)
    if "preference_key" in entry and (not isinstance(entry["preference_key"], str) or not entry["preference_key"]):
        raise ValueError("preference_key must be a nonempty string")
    if not isinstance(entry.get("items", []), list) or not all(isinstance(i, dict) for i in entry.get("items", [])):
        raise ValueError("items must be a list of objects")


def import_plan(plan):
    validate_plan(plan)
    selection = load_selection(effective=False)
    # Preserve all old notes as stable local preferences before retiring per-plan drafts.
    profile = P.profile()
    for kind, sid, oid, entry in F.entries(load_plan()):
        notes = selection["notes"].get(sid, {}) if kind == "meal" else selection["topup_notes"]
        if oid in notes:
            info = F.context(kind, sid, oid, entry, {}, profile)
            F.record_edit(profile, info, notes[oid])
    save_profile(profile, P.STATE_DIR)
    atomic_json(PLAN_FILE, plan)
    selection["notes"], selection["topup_notes"] = {}, {}
    atomic_json(SELECTION_FILE, selection)


def update_profile(body):
    allowed = {"store", "fulfilment", "catalogue", "fees", "preferences", "resolver_rules"}
    if set(body) - allowed:
        raise ValueError("unsupported profile setting")
    for key in ("store", "fulfilment"):
        if key in body and (not isinstance(body[key], str) or len(body[key]) > 300):
            raise ValueError("%s must be text under 300 characters" % key)
    if "catalogue" in body and body["catalogue"] not in ("agent", "woolworths-nz"):
        raise ValueError("catalogue must be agent or woolworths-nz")
    if "preferences" in body and (not isinstance(body["preferences"], dict) or
            not all(isinstance(k, str) and k and isinstance(v, str) and len(v) <= 4000
                    for k, v in body["preferences"].items())):
        raise ValueError("preferences must map keys to text")
    if "fees" in body:
        fees = body["fees"]
        if (not isinstance(fees, dict) or set(fees) - {"pickup", "bags"} or
                not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in fees.values())):
            raise ValueError("fees must contain non-negative pickup/bags amounts")
    if "resolver_rules" in body and (not isinstance(body["resolver_rules"], dict) or
            not all(isinstance(k, str) and isinstance(v, dict) for k, v in body["resolver_rules"].items())):
        raise ValueError("resolver_rules must map nouns to rule objects")
    profile = P.profile()
    for key, value in body.items():
        if key in ("fees", "preferences", "resolver_rules"):
            profile.setdefault(key, {}).update(value)
        else:
            profile[key] = value
    save_profile(profile, P.STATE_DIR)
    return profile


def import_articles(body):
    if not isinstance(body.get("items"), list):
        raise ValueError("items list required")
    state = P.load_state()
    existing = {i["id"]: i for i in state["items"]}
    result, seen = [], set()
    for article in body["items"]:
        if not isinstance(article, dict) or not isinstance(article.get("noun"), str) or not article["noun"].strip():
            raise ValueError("each article requires a noun")
        noun = article["noun"].strip()
        identifier = str(article.get("id") or P.slug(noun))
        if identifier in seen:
            raise ValueError("duplicate article ID")
        seen.add(identifier)
        qty = article.get("qty", 1)
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or not math.isfinite(qty) or qty <= 0:
            raise ValueError("article qty must be a positive number")
        unit = article.get("unit", "ea")
        if unit not in ("ea", "kg"):
            raise ValueError("article unit must be ea or kg")
        item = {**existing.get(identifier, {}), "id": identifier, "noun": noun,
                "label": article.get("label") or noun, "qty": qty, "unit": unit}
        if "chosen" in article:
            product = article["chosen"]
            if product is not None:
                if not isinstance(product, dict) or not isinstance(product.get("name"), str):
                    raise ValueError("chosen requires a product name")
                product = dict(product)
                for key in ("price", "unit_price"):
                    value = product.get(key)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                        raise ValueError("chosen requires non-negative price and unit_price")
                product.setdefault("unit_str", P._money(product["unit_price"]) + "/" + unit)
            item.update(chosen=product, resolved_at=time.time(), flags=[], options=[])
        result.append(item)
    state["items"] = result
    P.save_state(state)
    return {"ok": True, "items": len(result)}


def preference_for(kind, sid, oid, entry):
    return F.context(kind, sid, oid, entry, load_selection(effective=False), P.profile())


def save_note(kind, sid, oid, entry, text):
    profile = P.profile()
    info = F.context(kind, sid, oid, entry, load_selection(effective=False), profile)
    F.record_edit(profile, info, text)
    save_profile(profile, P.STATE_DIR)


def handoff_text(plan, selection, profile):
    """Build the person's paste for Hermes without reading or changing state."""
    header = "Provisions"
    week = plan.get("week_of")
    if isinstance(week, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", week):
        try:
            day = date.fromisoformat(week)
        except ValueError:
            pass
        else:
            months = ("January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December")
            header += " · week of %d %s %d" % (day.day, months[day.month - 1], day.year)
    lines = [header]
    shop = " · ".join(profile.get(key, "").strip() for key in ("store", "fulfilment")
                      if profile.get(key, "").strip())
    if shop:
        lines.append(shop)
    lines.append("")

    def preference_lines(info):
        # A fresh agent reading the paste has no profile, so the settled text has
        # to travel here; an edit is the same line with what it replaced beside it.
        if info["user_edited"]:
            lines.append("  now: " + (info["current"] or "(cleared)"))
            if info["suggested"]:
                lines.append("  was: " + info["suggested"])
        elif info["current"]:
            lines.append("  pref: " + info["current"])

    unchosen = []
    for si, slot in enumerate(plan.get("slots") or []):
        sid = entry_id(slot, "slot", si)
        chosen = None
        for oi, option in enumerate(slot.get("options") or []):
            oid = entry_id(option, "option", oi)
            info = F.context("meal", sid, oid, option, selection, profile)
            if selection.get("chosen", {}).get(sid) == oid:
                chosen = (option, info)
            elif info["user_edited"]:
                unchosen.append((option, info))
        label = slot.get("title") or sid
        if chosen is None:
            lines.append(label + " · not chosen")
        else:
            option, info = chosen
            key = option.get("preference_key")
            lines.append(label + " · " + (option.get("name") or "") +
                         (" [" + key + "]" if key else ""))
            preference_lines(info)

    topups, edited_topups = [], []
    for ti, topup in enumerate(plan.get("topups") or []):
        tid = entry_id(topup, "topup", ti)
        if selection.get("topups", {}).get(tid) is True:
            info = F.context("topup", "", tid, topup, selection, profile)
            topups.append((topup.get("name") or "") +
                          (" (" + info["current"] + ")" if info["current"] else ""))
            edited_topups.append(info)
    lines.extend(["", "top-ups: " + (", ".join(topups) or "none")])
    for info in edited_topups:
        preference_lines(info)
    for key in ("snacks", "household", "other"):
        text = selection.get("extras", {}).get(key, "")
        if text.strip():
            lines.append(key + ": " + text)
    if unchosen:
        lines.extend(["", "changed but not chosen:"])
        for option, info in unchosen:
            lines.append("  " + (option.get("name") or "") + " [" + info["key"] + "]")
            preference_lines(info)
    lines.extend(["", 'For Hermes: rebuild the shop from these. "pref:" is what I have settled on; "now:" is an edit I just made to "was:", and nothing I removed should come back.'])
    return "\n".join(line.rstrip() for line in "\n".join(lines).splitlines()) + "\n"


def export_document():
    plan = load_plan()
    selection = load_selection()
    profile = P.profile()
    chosen = {}
    for si, slot in enumerate(plan.get("slots") or []):
        sid = entry_id(slot, "slot", si)
        for oi, option in enumerate(slot["options"]):
            oid = entry_id(option, "option", oi)
            if selection["chosen"].get(sid) == oid:
                chosen[sid] = {"option": oid, "name": option.get("name") or "",
                               "items": option.get("items") or [],
                               "serves": option.get("serves"),
                               "note": selection["notes"].get(sid, {}).get(oid, ""),
                               "preference": preference_for("meal", sid, oid, option)}
                break
    return {
        "type": "provisions.export.v1",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "week_of": plan.get("week_of"),
        "store": profile["store"], "fulfilment": profile["fulfilment"],
        "catalogue": profile["catalogue"],
        "preference_feedback": list(profile["preference_overrides"].values()),
        "chosen": chosen,
        "topups": [{"id": entry_id(topup, "topup", ti),
                    "name": topup.get("name") or "",
                    "on": selection["topups"].get(entry_id(topup, "topup", ti)) is True,
                    "note": selection["topup_notes"].get(entry_id(topup, "topup", ti), ""),
                    "preference": preference_for("topup", "", entry_id(topup, "topup", ti), topup)}
                   for ti, topup in enumerate(plan.get("topups") or [])],
        "extras": selection["extras"],
        "instructions": "Rebuild the shop from these choices. Treat each preference's current text as final; the suggested text is what was edited away.",
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, strict=False):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:
            if strict:
                raise ValueError("malformed JSON")
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/api/list":
            force = parse_qs(u.query).get("refresh") == ["1"]
            try:
                return self._send(200, P.resolved_list(force=force, cached_only=parse_qs(u.query).get("cached") == ["1"]))
            except Exception as e:
                return self._send(500, {"error": str(e)})
        if u.path in ("/api/plan", "/api/selection", "/api/profile", "/api/handoff"):
            try:
                with PLAN_LOCK:
                    if u.path == "/api/handoff":
                        plan = load_plan()
                        document = {"text": handoff_text(plan, load_selection(effective=False), P.profile()),
                                    "week_of": plan.get("week_of") or ""}
                    else:
                        document = (load_plan() if u.path == "/api/plan" else
                                    P.profile() if u.path == "/api/profile" else load_selection())
                return self._send(200, document)
            except Exception as e:
                return self._send(500, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def plan_post(self, path):
        try:
            body = self._body(strict=True)
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            with PLAN_LOCK:
                if path == "/api/import":
                    import_plan(body)
                    document = {"ok": True, "slots": len(body["slots"])}
                elif path == "/api/articles/import":
                    document = import_articles(body)
                elif path == "/api/profile":
                    document = update_profile(body)
                elif path == "/api/learn":
                    if body.get("type") != "provisions.export.v1" or not isinstance(body.get("preference_feedback"), list):
                        raise ValueError("a Provisions export with preference_feedback is required")
                    profile, selection = P.profile(), load_selection(effective=False)
                    learned = F.learn_feedback(profile, selection, load_plan(), body["preference_feedback"])
                    save_profile(profile, P.STATE_DIR)
                    atomic_json(SELECTION_FILE, selection)
                    document = {"ok": True, "learned": learned}
                elif path == "/api/selection":
                    selection = load_selection(effective=False)
                    if isinstance(body.get("slot"), str) and body["slot"]:
                        sid, oid = body["slot"], body.get("option")
                        if not isinstance(oid, str) or not oid:
                            raise ValueError("option required")
                        slot = next((s for i, s in enumerate(load_plan().get("slots") or [])
                                     if entry_id(s, "slot", i) == sid), None)
                        if slot is None or not any(entry_id(o, "option", i) == oid
                                                   for i, o in enumerate(slot["options"])):
                            raise ValueError("meal option no longer in the plan")
                        if "note" in body:
                            if not isinstance(body["note"], str) or len(body["note"]) > 4000:
                                raise ValueError("note must be text under 4000 characters")
                            option = next(o for i, o in enumerate(slot["options"]) if entry_id(o, "option", i) == oid)
                            save_note("meal", sid, oid, option, body["note"])
                            selection["notes"].setdefault(sid, {})[oid] = body["note"]
                        else:
                            selection["chosen"][sid] = oid
                    elif isinstance(body.get("topup"), str) and body["topup"]:
                        tid = body["topup"]
                        if not any(entry_id(t, "topup", i) == tid
                                   for i, t in enumerate(load_plan().get("topups") or [])):
                            raise ValueError("top-up no longer in the plan")
                        if "note" in body:
                            if not isinstance(body["note"], str) or len(body["note"]) > 4000:
                                raise ValueError("note must be text under 4000 characters")
                            topup = next(t for i, t in enumerate(load_plan().get("topups") or []) if entry_id(t, "topup", i) == tid)
                            save_note("topup", "", tid, topup, body["note"])
                            selection["topup_notes"][tid] = body["note"]
                        elif isinstance(body.get("on"), bool):
                            selection["topups"][tid] = body["on"]
                        else:
                            raise ValueError("boolean on or note required")
                    elif body.get("extra") in ("snacks", "household", "other"):
                        if not isinstance(body.get("text"), str) or len(body["text"]) > 4000:
                            raise ValueError("extra must be text under 4000 characters")
                        selection["extras"][body["extra"]] = body["text"]
                    else:
                        raise ValueError("meal choice, top-up, or extra required")
                    atomic_json(SELECTION_FILE, selection)
                    document = selection
                else:
                    exported = export_document()
                    destination = os.path.join(P.STATE_DIR, "exports",
                                               time.strftime("export-%Y%m%d-%H%M%S.json"))
                    atomic_json(destination, exported)
                    document = {"ok": True, "path": destination, "document": exported}
            return self._send(200, document)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        host = self.headers.get("Host", "")
        allowed = {"127.0.0.1:%d" % self.server.server_port, "localhost:%d" % self.server.server_port}
        if host not in allowed or self.headers.get("Origin", "http://" + host) != "http://" + host:
            return self._send(403, {"error": "local same-origin requests only"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return self._send(415, {"error": "application/json required"})
        u = urlparse(self.path)
        if u.path in ("/api/import", "/api/selection", "/api/export", "/api/profile", "/api/learn", "/api/articles/import"):
            return self.plan_post(u.path)
        b = self._body()
        try:
            if u.path == "/api/add":
                noun = (b.get("noun") or "").strip()
                if not noun:
                    return self._send(400, {"error": "noun required"})
                P.add_item(noun)
            elif u.path == "/api/qty":
                st = P.load_state()
                for it in st["items"]:
                    if it["id"] == b.get("id"):
                        it["qty"] = float(b.get("qty") or 1)
                P.save_state(st)
            elif u.path == "/api/pin":
                st = P.load_state()
                for it in st["items"]:
                    if it["id"] == b.get("id"):
                        it["pinned"] = b.get("sku") or None
                        it["resolved_at"] = 0
                P.save_state(st)
            elif u.path == "/api/remove":
                st = P.load_state()
                st["items"] = [i for i in st["items"] if i["id"] != b.get("id")]
                P.save_state(st)
            elif u.path == "/api/clear":
                st = P.load_state()
                st["items"] = []
                P.save_state(st)
            else:
                return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})
        try:
            return self._send(200, P.resolved_list())
        except Exception as e:
            return self._send(500, {"error": str(e)})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("provisions on http://127.0.0.1:%d" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
