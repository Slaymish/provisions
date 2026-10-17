"""Selection and Hermes handoff contract; all state and catalogue data are isolated."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import serve


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.patches = [patch.object(serve, 'PLAN_FILE', os.path.join(root, 'plan.json')),
                        patch.object(serve, 'SELECTION_FILE', os.path.join(root, 'selection.json')),
                        patch.object(serve.P, 'STATE_DIR', root),
                        patch.object(serve.P, 'STATE_FILE', os.path.join(root, 'state.json')),
                        patch.object(serve.P, 'resolved_list', return_value={
                            'items': [], 'subtotal': 0, 'pickup_fee': 0, 'bag_fee': 0, 'total': 0})]
        for p in self.patches:
            p.start()
        self.plan = {'version': 'provisions.plan.v1', 'slots': [
            {'id': 'breakfast', 'options': [
                {'id': 'eggs', 'name': 'Eggs on toast', 'items': [{'noun': 'eggs'}, {'noun': 'bread'}], 'serves': 5},
                {'id': 'oats', 'name': 'Oats'}]},
            {'options': [{'name': 'Lunch'}]}],
            'topups': [{'id': 'soap', 'name': 'Soap'}]}
        serve.atomic_json(serve.PLAN_FILE, self.plan)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:%s' % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.directory.cleanup()

    def post(self, path, body):
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def select(self, **body):
        return self.post('/api/selection', body)

    def test_notes_survive_switch_and_export_in_context(self):
        self.select(slot='breakfast', option='eggs')
        self.select(slot='breakfast', option='eggs', note='English muffins instead of bread')
        self.select(slot='breakfast', option='oats')
        result = self.post('/api/export', {})['document']
        self.assertEqual(result['chosen']['breakfast']['note'], '')
        self.select(slot='breakfast', option='eggs')
        result = self.post('/api/export', {})
        meal = result['document']['chosen']['breakfast']
        self.assertEqual(meal['note'], 'English muffins instead of bread')
        self.assertEqual(meal['items'][1]['noun'], 'bread')
        self.assertEqual(meal['serves'], 5)
        with open(result['path']) as f:
            self.assertEqual(json.load(f), result['document'])

    def test_topup_and_all_extra_fields_round_trip(self):
        self.select(topup='soap', on=True)
        self.select(topup='soap', note='Two refill packs')
        for kind in ('snacks', 'household', 'other'):
            self.select(extra=kind, text=kind + ' request')
        saved = serve.load_selection()
        self.assertEqual(saved['topup_notes']['soap'], 'Two refill packs')
        exported = self.post('/api/export', {})['document']
        self.assertEqual(exported['extras'], saved['extras'])
        self.assertEqual(exported['topups'][0]['note'], 'Two refill packs')
        self.assertTrue(exported['topups'][0]['on'])
        self.select(extra='snacks', text='')
        self.assertEqual(serve.load_selection()['extras']['snacks'], '')

    def test_legacy_selection_defaults_and_positional_ids(self):
        serve.atomic_json(serve.SELECTION_FILE, {'chosen': {'breakfast': 'eggs'}, 'topups': {}})
        self.assertEqual(serve.load_selection()['notes'], {})
        self.select(slot='slot-2', option='option-1')
        self.assertEqual(self.post('/api/export', {})['document']['chosen']['slot-2']['name'], 'Lunch')

    def test_stale_choices_are_omitted(self):
        self.select(slot='breakfast', option='eggs')
        self.plan['slots'][0]['options'] = []
        serve.atomic_json(serve.PLAN_FILE, self.plan)
        self.assertNotIn('breakfast', self.post('/api/export', {})['document']['chosen'])

    def test_unknown_and_invalid_updates_do_not_write(self):
        cases = [{'slot': 'breakfast', 'option': 'unknown'}, {'extra': 'unknown', 'text': 'x'},
                 {'topup': 'soap', 'on': 'yes'}, {'extra': 'snacks', 'text': 3},
                 {'slot': 'breakfast', 'option': 'eggs', 'note': 'x' * 4001}]
        for body in cases:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.post('/api/selection', body)
            self.assertEqual(ctx.exception.code, 400)
        self.assertFalse(os.path.exists(serve.SELECTION_FILE))

    def test_note_text_is_preserved_exactly(self):
        note = 'Muffins & eggs\nNo <script> surprises — café style.'
        self.select(slot='breakfast', option='eggs', note=note)
        self.assertEqual(serve.load_selection()['notes']['breakfast']['eggs'], note)
        self.select(slot='breakfast', option='eggs', note='')
        self.assertEqual(serve.load_selection()['notes']['breakfast']['eggs'], '')

    def add_preferences(self):
        self.plan['slots'][0]['options'][0].update(
            preference_key='meal:eggs-on-toast', preference='English muffins')
        self.plan['topups'][0].update(preference_key='item:milk', preference='Light milk, high protein')
        serve.atomic_json(serve.PLAN_FILE, self.plan)

    def test_agent_preferences_prefill_without_becoming_feedback(self):
        self.add_preferences()
        selected = serve.load_selection()
        self.assertEqual(selected['notes']['breakfast']['eggs'], 'English muffins')
        self.assertEqual(selected['topup_notes']['soap'], 'Light milk, high protein')
        self.assertEqual(self.post('/api/export', {})['document']['preference_feedback'], [])

    def test_partial_removal_learns_and_does_not_return_in_new_plan(self):
        self.add_preferences()
        self.select(topup='soap', on=True)
        self.select(topup='soap', note='Light milk')
        exported = self.post('/api/export', {})['document']
        feedback = exported['preference_feedback'][0]
        self.assertEqual(feedback['suggested'], 'Light milk, high protein')
        self.assertEqual(feedback['text'], 'Light milk')
        result = self.post('/api/learn', exported)
        self.assertEqual(result['learned'], ['item:milk'])
        self.assertEqual(self.post('/api/learn', exported)['learned'], [])
        self.plan['topups'][0]['id'] = 'milk-next-week'
        self.post('/api/import', self.plan)
        self.assertEqual(serve.load_selection()['topup_notes']['milk-next-week'], 'Light milk')
        self.assertEqual(serve.P.profile()['preferences']['item:milk'], 'Light milk')

    def test_explicit_clear_survives_import_before_and_after_learning(self):
        self.add_preferences()
        self.select(slot='breakfast', option='eggs', note='')
        exported = self.post('/api/export', {})['document']
        self.assertEqual(exported['preference_feedback'][0]['change'], 'cleared')
        self.plan['slots'][0]['options'][0]['id'] = 'eggs-v2'
        self.post('/api/import', self.plan)
        self.assertEqual(serve.load_selection()['notes']['breakfast']['eggs-v2'], '')
        self.post('/api/learn', exported)
        self.post('/api/import', self.plan)
        self.select(slot='breakfast', option='eggs-v2')
        self.assertEqual(self.post('/api/export', {})['document']['chosen']['breakfast']['note'], '')
        self.assertEqual(serve.P.profile()['preferences']['meal:eggs-on-toast'], '')

    def test_older_export_cannot_overwrite_a_newer_edit(self):
        self.add_preferences()
        self.select(topup='soap', note='Light milk')
        older = self.post('/api/export', {})['document']
        self.select(topup='soap', note='Oat milk')
        self.assertEqual(self.post('/api/learn', older)['learned'], [])
        self.assertEqual(serve.load_selection()['topup_notes']['soap'], 'Oat milk')
        self.assertEqual(serve.P.profile()['preference_overrides']['item:milk']['text'], 'Oat milk')

    def test_pending_human_edit_beats_new_agent_suggestion(self):
        self.add_preferences()
        self.select(topup='soap', note='Light milk')
        self.post('/api/profile', {'preferences': {'item:milk': 'Full cream milk'}})
        self.plan['topups'][0]['preference'] = 'New suggestion'
        self.post('/api/import', self.plan)
        self.assertEqual(serve.load_selection()['topup_notes']['soap'], 'Light milk')

    def test_store_settings_are_private_and_used_in_export(self):
        self.plan['store'] = 'Outdated store'
        serve.atomic_json(serve.PLAN_FILE, self.plan)
        self.post('/api/profile', {'store': 'Example local store', 'fulfilment': 'Saturday collection'})
        exported = self.post('/api/export', {})['document']
        self.assertEqual(exported['store'], 'Example local store')
        self.assertEqual(serve.P.profile()['fulfilment'], 'Saturday collection')
        with open(os.path.join(self.directory.name, 'profile.json')) as stream:
            self.assertEqual(json.load(stream)['store'], 'Example local store')

    def test_article_import_preserves_existing_products_and_validates_quantities(self):
        product = {'name': 'Example bread', 'price': 3, 'unit_price': 3}
        self.post('/api/articles/import', {'items': [{'noun': 'bread', 'chosen': product}]})
        self.post('/api/articles/import', {'items': [{'noun': 'bread', 'qty': 2}]})
        self.assertEqual(serve.P.load_state()['items'][0]['chosen']['name'], 'Example bread')
        self.assertEqual(serve.P.load_state()['items'][0]['qty'], 2)
        with self.assertRaises(urllib.error.HTTPError):
            self.post('/api/articles/import', {'items': [{'noun': 'bread', 'qty': -1}]})
        self.assertEqual(serve.P.load_state()['items'][0]['qty'], 2)

    def test_invalid_import_keeps_previous_plan(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.post('/api/import', {'version': 'v1', 'slots': [{'options': [{'preference': False}]}]})
        self.assertEqual(serve.load_plan(), self.plan)

    def test_cross_origin_write_is_rejected(self):
        req = urllib.request.Request(self.base + '/api/profile', data=b'{"store":"Changed"}',
            headers={'Content-Type': 'application/json', 'Origin': 'https://example.com'})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)
        self.assertEqual(serve.P.profile()['store'], '')


if __name__ == '__main__':
    unittest.main()
