"""Keep agent suggestions, human edits and explicit clears distinguishable."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


def entry_id(entry, kind, index):
    return str(entry.get('id') or '%s-%d' % (kind, index + 1))


def entries(plan):
    for si, slot in enumerate(plan.get('slots') or []):
        sid = entry_id(slot, 'slot', si)
        for oi, option in enumerate(slot.get('options') or []):
            oid = entry_id(option, 'option', oi)
            yield 'meal', sid, oid, option
    for ti, topup in enumerate(plan.get('topups') or []):
        yield 'topup', '', entry_id(topup, 'topup', ti), topup


def key_for(kind, sid, oid, entry):
    return entry.get('preference_key') or ('meal:%s:%s' % (sid, oid) if kind == 'meal'
                                          else 'item:%s' % (entry.get('noun') or oid))


def context(kind, sid, oid, entry, selection, profile):
    key = key_for(kind, sid, oid, entry)
    suggested = profile.get('preferences', {}).get(key, entry.get('preference', ''))
    override = profile.get('preference_overrides', {}).get(key)
    notes = selection.get('notes', {}).get(sid, {}) if kind == 'meal' else selection.get('topup_notes', {})
    current = override['text'] if override else notes.get(oid, suggested)
    return {'key': key, 'suggested': suggested, 'current': current,
            'user_edited': bool(override) or (oid in notes and current != suggested)}


def effective_selection(plan, selection, profile):
    result = deepcopy(selection)
    for kind, sid, oid, entry in entries(plan):
        info = context(kind, sid, oid, entry, selection, profile)
        if info['current'] or info['user_edited']:
            notes = result['notes'].setdefault(sid, {}) if kind == 'meal' else result['topup_notes']
            notes[oid] = info['current']
    return result


def record_edit(profile, info, text):
    if text == info['current']:
        return
    profile.setdefault('preference_overrides', {})[info['key']] = {
        'id': str(uuid4()), 'key': info['key'], 'suggested': info['suggested'],
        'previous': info['current'], 'text': text,
        'change': 'cleared' if text == '' else 'edited',
        'edited_at': datetime.now(timezone.utc).isoformat(),
    }


def learn_feedback(profile, selection, plan, feedback):
    """Fold exact acknowledged edits into defaults; stale exports cannot win."""
    learned = []
    overrides = profile.setdefault('preference_overrides', {})
    for edit in feedback:
        if not isinstance(edit, dict):
            raise ValueError('each feedback entry must be an object')
        key = edit.get('key')
        if not isinstance(key, str):
            raise ValueError('feedback key required')
        current = overrides.get(key)
        if not current or current['id'] != edit.get('id') or current['text'] != edit.get('text'):
            continue
        # Empty strings are durable preferences too, not missing values.
        profile.setdefault('preferences', {})[key] = current['text']
        del overrides[key]
        for kind, sid, oid, entry in entries(plan):
            if key_for(kind, sid, oid, entry) == key:
                notes = selection.get('notes', {}).get(sid, {}) if kind == 'meal' else selection.get('topup_notes', {})
                notes.pop(oid, None)
        learned.append(key)
    return learned
