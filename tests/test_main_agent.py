"""Test the integrated FastAPI app without loading a speech model or generating audio."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import agent_store
import prime_engine
import agent_graph


class MainAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = agent_store.AgentStore(Path(self.temp.name) / "agent.db")
        self.runtime = agent_graph.ChatRuntime(Path(self.temp.name)/'graph.db',provider='n8n',store=self.store)
        self.key = "test-admin-key-for-main-integration"
        self.patches = [patch.object(agent_store, "_store", self.store),
                        patch.object(agent_graph, "_runtime", self.runtime),
                        patch.object(agent_store, "admin_key", return_value=self.key)]
        for p in self.patches: p.start()
        fake_modules={"voice":types.SimpleNamespace(generate_voice=lambda text:None,AUDIO_DIR=str(Path(self.temp.name)/"audio")),
                      "speech_to_text":types.SimpleNamespace(transcribe_audio=lambda path:"متن آزمایشی",STTError=RuntimeError)}
        spec=importlib.util.spec_from_file_location("timo_main_integration",Path(__file__).resolve().parents[1]/"main.py")
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,fake_modules): spec.loader.exec_module(module)
        self.client=TestClient(module.app)

    def tearDown(self):
        self.client.close()
        self.runtime.close()
        for p in self.patches: p.stop()
        self.temp.cleanup()

    def test_chat_teach_confirm_and_recall_on_the_actual_app(self):
        value=self.client.post('/api/chat',json=dict(message='یاد بگیر سؤال: مدیر شرکت کیست؟ جواب: آقای خدیوزاد',session_id='abc',input_source='voice')).json()
        self.assertEqual(self.store.rows('memories'),[])
        body=dict(proposal_id=value['proposal']['id'],session_id='abc')
        with patch('agent_api.admin_key',return_value=self.key):
            self.assertEqual(self.client.post('/api/agent/confirm-memory',json=body,headers={'X-Agent-Key':self.key}).status_code,200)
        answer=self.client.post('/api/chat',json=dict(message='مدیر شرکت کیست؟',session_id='def')).json()
        self.assertEqual(answer['response'],'آقای خدیوزاد')
        self.assertEqual(answer['source'],'memory')

    def test_original_dialogue_contract_and_manager_template(self):
        with patch.object(prime_engine,'graph_reply',return_value=('پاسخ عمومی',[[],0,False,False],{})):
            result=self.client.post('/api/chat',json=dict(message='سلام')).json()
        self.assertEqual(result['response'],'پاسخ عمومی')
        self.assertEqual(result['response_language'],'fa-IR')
        self.assertIsInstance(result['face'],dict)
        response=self.client.get('/agent')
        self.assertEqual(response.status_code,200)
        self.assertIn('memoryForm',response.text)
        self.assertNotIn(self.key,response.text)
        self.assertEqual(self.client.get('/data/agent-admin.key').status_code,404)

    def test_invalid_chat_is_rejected_before_agent_execution(self):
        self.assertEqual(self.client.post('/api/chat',json=dict(message='x'*6001)).status_code,422)
        self.assertEqual(self.client.post('/api/chat',json=dict(message='سلام',session_id='x'*129)).status_code,422)


if __name__=='__main__': unittest.main()
