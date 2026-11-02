import json
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Config loading is unrelated to routing; allow these unit tests without installed extras.
try:
    import dotenv
except ImportError:
    sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda: None)
import prime_engine as engine


class DialogueTests(unittest.TestCase):
    def setUp(self):
        engine._sessions.clear()

    def test_four_general_questions_never_redirect_to_products(self):
        with patch.object(engine, 'ask_general', return_value=('پاسخ عمومی', True)) as ask:
            for text in ['سلام خوبی', 'چرا آسمان آبی است', 'گرانش چیست', 'بیشتر توضیح بده']:
                self.assertEqual(engine.answer_query(text, 'a'), 'پاسخ عمومی')
            self.assertEqual(ask.call_count, 4)
            self.assertEqual(len(ask.call_args.args[1]), 6)

    def test_catalog_uses_real_database_and_subject_can_change(self):
        product = engine.catalog.get_all_products()[0]
        with patch.object(engine, 'ask_general', return_value=('جواب علمی', True)) as ask:
            result = engine.answer_query(product['product_code'], 'a')
            self.assertIn(product['product_name'], result)
            ask.assert_not_called()
            self.assertTrue(engine._session('a')['catalog'][3])
            self.assertFalse(engine._session('b')['catalog'][3])
            self.assertEqual(engine.answer_query('چرا آسمان آبی است', 'a'), 'جواب علمی')
            self.assertFalse(engine._session('a')['catalog'][3])
            engine.answer_query('بله', 'a')
            self.assertEqual(ask.call_count, 2)

    def test_histories_are_separate_and_bounded(self):
        with patch.object(engine, 'ask_general', return_value=('جواب', True)):
            for i in range(10): engine.answer_query('سلام ' + str(i), 'a')
        self.assertEqual(len(engine._session('a')['history']), 12)
        self.assertEqual(engine._session('b')['history'], [])

    def test_failure_does_not_pollute_history(self):
        with patch.object(engine, 'ask_general', return_value=('خطا', False)):
            engine.answer_query('سلام', 'a')
        self.assertEqual(engine._session('a')['history'], [])

    def test_webhook_contract(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({'reply': 'پاسخ'}).encode()
        with patch.object(engine.request, 'urlopen', return_value=Response()) as call:
            self.assertEqual(engine.ask_general('سلام', []), ('پاسخ', True))
            payload = json.loads(call.call_args.args[0].data)
            self.assertEqual(payload['message'], 'سلام')
            self.assertIn('HTN Prime', payload['system_prompt'])
            self.assertEqual(payload['history'], [])


if __name__ == '__main__': unittest.main()
