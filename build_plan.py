#!/usr/bin/env python3
"""Import an agent-authored plan. Personal plans live outside the checkout."""
import sys
from agent import request
import json

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python3 build_plan.py /path/to/plan.json (start serve.py first)')
    with open(sys.argv[1]) as stream:
        result = request('/api/import', json.load(stream))
    print(json.dumps(result))
