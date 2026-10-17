"""Private per-installation data. Nothing here belongs in a public checkout."""
import json
import os
import tempfile

DATA_DIR = os.path.abspath(os.path.expanduser(os.environ.get('PROVISIONS_HOME', '~/.provisions')))


def atomic_json(path, document):
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.provisions-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path, default):
    try:
        with open(path) as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default


def load_profile(directory=DATA_DIR):
    saved = read_json(os.path.join(directory, 'profile.json'), {})
    return {'version': 'provisions.profile.v1', 'store': '', 'fulfilment': '',
            'catalogue': 'agent', 'fees': {'pickup': 0, 'bags': 0},
            'preferences': {}, 'preference_overrides': {}, 'resolver_rules': {}, **saved}


def save_profile(profile, directory=DATA_DIR):
    atomic_json(os.path.join(directory, 'profile.json'), profile)
