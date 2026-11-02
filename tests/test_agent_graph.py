import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from agent_graph import ChatRuntime, MAX_MODEL_CALLS
from agent_store import AgentStore
import prime_engine


class SequenceModel:
    def __init__(self, responses):
        self.responses=list(responses)
        self.requests=[]
    def invoke(self, messages):
        self.requests.append(messages)
        return self.responses.pop(0)


def call(name,args=None,identifier='call1'):
    return AIMessage(content='', tool_calls=[{'name':name,'args':args or {},'id':identifier}])


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.store=AgentStore(self.root/'agent.db')
        self.runtimes=[]

    def tearDown(self):
        for runtime in self.runtimes: runtime.close()
        self.temp.cleanup()

    def runtime(self, **kwargs):
        runtime=ChatRuntime(self.root/'graph.db',store=self.store,**kwargs)
        self.runtimes.append(runtime)
        return runtime

    def test_actual_stategraph_nodes_are_on_the_live_chat_path(self):
        runtime=self.runtime(provider='n8n')
        self.assertTrue({'commands','model','tools','finish'} <= set(runtime.graph.get_graph().nodes))
        with patch.object(prime_engine,'graph_reply',return_value=('پاسخ',[[],0,False,False],{})):
            self.assertEqual(runtime.chat('سلام','A')['response'],'پاسخ')
        snapshot=runtime.graph.get_state({'configurable':{'thread_id':'A'}})
        self.assertEqual(snapshot.values['messages'][-1].content,'پاسخ')

    def test_history_survives_process_recreation_and_stays_private_by_thread(self):
        runtime=self.runtime(provider='n8n')
        with patch.object(prime_engine,'graph_reply',return_value=('سلام بابک',[[],0,False,False],{})):
            runtime.chat('من بابک هستم','A')
        runtime.close();self.runtimes.remove(runtime)
        second=self.runtime(provider='n8n')
        with patch.object(prime_engine,'graph_reply',return_value=('پاسخ',[[],0,False,False],{})) as reply:
            second.chat('اسم من چی بود؟','A')
            prior=reply.call_args.args[1]
            self.assertTrue(any('بابک' in item['content'] for item in prior))
            second.chat('سلام','B')
            self.assertEqual(reply.call_args.args[1],[])

    def test_tool_result_returns_to_model_before_final_answer(self):
        self.store.save_memory(dict(title='ساعت کاری',body='۹ تا ۵',kind='fact'))
        model=SequenceModel([call('lookup_knowledge',{'query':'ساعت کاری'}),AIMessage(content='ساعت کاری ۹ تا ۵ است.')])
        runtime=self.runtime(provider='groq',model=model)
        self.assertEqual(runtime.chat('چه زمانی باز هستید؟','A')['response'],'ساعت کاری ۹ تا ۵ است.')
        self.assertEqual(len(model.requests),2)
        observation=[m for m in model.requests[1] if isinstance(m,ToolMessage)][0]
        self.assertEqual(json.loads(observation.content)['references'][0]['body'],'۹ تا ۵')

    def test_catalog_tool_reads_registered_data_without_webhook(self):
        model=SequenceModel([call('search_products',{'query':'محصولات'}),AIMessage(content='اطلاعات کاتالوگ دریافت شد.')])
        runtime=self.runtime(provider='groq',model=model)
        with patch.object(prime_engine,'ask_general',side_effect=AssertionError('n8n must not be called')):
            runtime.chat('چه کالاهایی برای خرید دارید؟','A')
        observation=json.loads(next(m.content for m in model.requests[1] if isinstance(m,ToolMessage)))
        self.assertEqual(observation['source'],'recorded_catalog')
        self.assertTrue(observation['products'])
        self.assertFalse(observation['live_market_price'])

    def test_unknown_tool_and_extra_arguments_cannot_execute_commands(self):
        for message in [call('run_shell',{'command':'bad'}),call('list_destinations',{'x':10})]:
            model=SequenceModel([message,AIMessage(content='امکان اجرا نیست.')])
            runtime=self.runtime(provider='groq',model=model)
            result=runtime.chat('درخواست آزمایشی','A')
            self.assertNotIn('action',result)
            observation=json.loads(next(m.content for m in model.requests[1] if isinstance(m,ToolMessage)))
            self.assertEqual(observation['status'],'error')

    def test_model_cannot_move_from_a_general_conversation_or_invent_coordinates(self):
        self.store.save_room(dict(name='سالن',aliases=[],map_name='demo',x=1,y=2,z=0,rotation=0,enabled=True))
        model=SequenceModel([call('prepare_navigation',{'destination':'سالن'}),AIMessage(content='برای حرکت بگویید برو سالن.')])
        runtime=self.runtime(provider='groq',model=model)
        result=runtime.chat('درباره سالن توضیح بده','A')
        self.assertNotIn('action',result)
        observation=json.loads(next(m.content for m in model.requests[1] if isinstance(m,ToolMessage)))
        self.assertEqual(observation['status'],'explicit_request_needed')
        self.assertNotIn('pose',observation)

    def test_enabled_registered_navigation_keeps_existing_native_contract(self):
        self.store.save_room(dict(name='سالن',aliases=[],map_name='demo',x=1,y=2,z=0,rotation=0,enabled=True))
        model=SequenceModel([])
        result=self.runtime(provider='groq',model=model).chat('برو سالن','A')
        self.assertEqual(result['action']['pose'],dict(x=1,y=2,z=0,rotation=0))
        self.assertEqual(model.requests,[])

    def test_repeated_tool_calls_stop_at_a_finite_budget(self):
        model=SequenceModel([call('list_destinations',identifier='call'+str(i)) for i in range(MAX_MODEL_CALLS)])
        result=self.runtime(provider='groq',model=model).chat('ابزار را بررسی کن','A')
        self.assertEqual(len(model.requests),MAX_MODEL_CALLS)
        self.assertIn('نتیجهٔ کامل',result['response'])
        self.assertNotIn('action',result)

    def test_provider_failure_is_caught_and_does_not_expose_secrets(self):
        model=SequenceModel([])
        result=self.runtime(provider='groq',model=model).chat('سلام','A')
        self.assertIn('ارتباط با مدل',result['response'])
        self.assertNotIn('pop',result['response'])

    def test_saved_actions_are_reset_on_the_next_turn(self):
        self.store.save_room(dict(name='سالن',aliases=[],map_name='demo',x=1,y=2,z=0,rotation=0,enabled=True))
        runtime=self.runtime(provider='n8n')
        self.assertIn('action',runtime.chat('برو سالن','A'))
        with patch.object(prime_engine,'graph_reply',return_value=('پاسخ عمومی',[[],0,False,False],{})):
            self.assertNotIn('action',runtime.chat('سلام','A'))

    def test_catalog_context_survives_server_restart(self):
        runtime=self.runtime(provider='n8n')
        runtime.chat('چه محصولاتی دارید؟','A')
        runtime.close();self.runtimes.remove(runtime)
        runtime=self.runtime(provider='n8n')
        with patch.object(prime_engine,'ask_general',side_effect=AssertionError('catalog follow-up must stay local')):
            self.assertNotIn('پیدا نکردم',runtime.chat('قیمتش چنده','A')['response'])

    def test_stop_does_not_wait_for_a_slow_model_in_the_same_conversation(self):
        entered=threading.Event(); release=threading.Event()
        class BlockingModel:
            def invoke(self,messages):
                entered.set();release.wait(5)
                return AIMessage(content='پاسخ')
        runtime=self.runtime(provider='groq',model=BlockingModel())
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(runtime.chat,'سلام','A')
            self.assertTrue(entered.wait(2))
            stop=pool.submit(runtime.chat,'توقف','A')
            try: self.assertEqual(stop.result(timeout=1)['action']['type'],'stop')
            finally: release.set()
            future.result(timeout=3)

    def test_history_trimming_keeps_complete_recent_turns(self):
        runtime=self.runtime(provider='n8n')
        with patch.object(prime_engine,'graph_reply',return_value=('پاسخ',[[],0,False,False],{})):
            for i in range(12):runtime.chat('پیام '+str(i),'A')
        messages=runtime.graph.get_state({'configurable':{'thread_id':'A'}}).values['messages']
        self.assertEqual(sum(isinstance(m,HumanMessage) for m in messages),6)
        self.assertEqual(messages[0].content,'پیام 6')


if __name__=='__main__': unittest.main()
