#!/usr/bin/env python3
"""Small JSON interface for a local planning agent. Python 3.9+, stdlib only."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from local_data import DATA_DIR, load_profile, save_profile


def request(path, body=None):
    base = os.environ.get('PROVISIONS_URL', 'http://127.0.0.1:8770').rstrip('/')
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(json.load(error).get('error', str(error))) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='create an empty private profile without replacing existing data')
    sub.add_parser('context', help='read profile, plan and effective selections from the running app')
    for command, help_text in [('import', 'import an agent-authored plan'),
                               ('profile', 'merge local settings and learned preference suggestions'),
                               ('learn', 'remember exact human edits from an export'),
                               ('articles', 'replace the proposed list with agent-prepared articles')]:
        p = sub.add_parser(command, help=help_text)
        p.add_argument('file', help='JSON file, or - for standard input')
    sub.add_parser('export', help='write and return the current handoff document')
    args = parser.parse_args()
    if args.command == 'init':
        path = os.path.join(DATA_DIR, 'profile.json')
        created = not os.path.exists(path)
        if created:
            save_profile(load_profile())
        result = {'profile': path, 'created': created}
    elif args.command == 'context':
        result = {name: request('/api/' + name) for name in ('profile', 'plan', 'selection')}
    elif args.command == 'export':
        result = request('/api/export', {})
    else:
        with sys.stdin if args.file == '-' else open(args.file) as stream:
            body = json.load(stream)
        endpoint = {'import': '/api/import', 'profile': '/api/profile', 'learn': '/api/learn', 'articles': '/api/articles/import'}[args.command]
        result = request(endpoint, body)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
