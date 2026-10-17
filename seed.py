#!/usr/bin/env python3
"""Add nouns from a private JSON list; existing items are preserved."""
import json
import sys
import provisions as P

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python3 seed.py /path/to/items.json (a JSON list of nouns)')
    with open(sys.argv[1]) as stream:
        nouns = json.load(stream)
    if not isinstance(nouns, list) or not all(isinstance(n, str) and n.strip() for n in nouns):
        sys.exit('Expected a JSON list of nonempty nouns')
    for noun in nouns:
        P.add_item(noun)
    print('%d items' % len(P.load_state()['items']))
