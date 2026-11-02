import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_store import AgentStore
import agent_engine
import prime_engine


class UnifiedCommands(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AgentStore(Path(self.temp.name)/'agent.db')
        self.store.save_room(dict(name='سالن نمایش محصولات', aliases=['سالن'], map_name='demo-map',
                                  x=1, y=2, z=0, rotation=0, enabled=True))

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_persian_variants_use_the_registered_destination(self):
        for command in ['برو سالن', 'لطفاً برو به سالن', 'منو ببر سالن', 'من را ببر به سالن', 'ببرم سالن']:
            result = agent_engine.chat(command, 'robot', store=self.store)
            self.assertEqual(result['action']['map_name'], 'demo-map')
            self.assertEqual(result['action']['pose'], dict(x=1,y=2,z=0,rotation=0))

    def test_unregistered_negated_and_question_commands_do_not_move(self):
        with patch.object(prime_engine,'answer_query',return_value='پاسخ عمومی'):
            for command in ['منو نبر سالن', 'آیا میتونی منو ببر سالن؟', 'برو ناکجاآباد', 'برو سالن و بعد توقف کن']:
                self.assertNotIn('action', agent_engine.chat(command, 'robot', store=self.store))

    def test_product_introduction_uses_existing_catalog_dialogue(self):
        with patch.object(prime_engine,'answer_query',return_value='محصول ثبت‌شده') as call:
            result=agent_engine.chat('لطفاً محصولات رو معرفی کن','robot',store=self.store)
        call.assert_called_once_with('چه محصولاتی دارید؟','robot')
        self.assertEqual(result['response'],'محصول ثبت‌شده')


if __name__ == '__main__': unittest.main()
