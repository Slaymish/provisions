#!/usr/bin/env python3
"""Bake the current plan into a self-contained snapshot.html for previewing offline."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import provisions as P
from serve import load_plan, load_selection


def main():
    data = {"plan": load_plan(), "selection": load_selection(), "profile": P.profile()}
    with open(os.path.join(HERE, "index.html")) as f:
        html = f.read()
    # Keep authored text from terminating the script element in a snapshot.
    payload = json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    inject = "<script>window.__PRELOAD__ = %s;</script>\n" % payload
    marker = "<script>\nconst $ = s => document.querySelector(s);"
    if marker not in html:
        raise SystemExit("could not find script marker in index.html")
    html = html.replace(marker, inject + marker, 1)
    out = os.path.join(P.STATE_DIR, "snapshot.html")
    with open(out, "w") as f:
        f.write(html)
    print(out)


if __name__ == "__main__":
    main()
