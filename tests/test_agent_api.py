import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import agent_api
from agent_store import AgentStore


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AgentStore(Path(self.temp.name) / "db.sqlite")
        self.key = "test-manager-credential-with-32chars"
        self.patches = [patch.object(agent_api, "get_store", return_value=self.store),
                        patch.object(agent_api, "admin_key", return_value=self.key)]
        for p in self.patches: p.start()
        app = FastAPI(); app.include_router(agent_api.router)
        self.client = TestClient(app)
        self.headers = {"X-Agent-Key": self.key}

    def tearDown(self):
        self.client.close()
        for p in self.patches: p.stop()
        self.temp.cleanup()

    def test_unauthorized_access_cannot_read_or_change_knowledge(self):
        for method,path,body in [("get","/api/agent/state",None), ("post","/api/agent/memories",{"data":{"title":"x","body":"y"}}), ("delete","/api/agent/rooms/1",None)]:
            self.assertEqual(self.client.request(method, path, json=body).status_code, 401)
        self.assertEqual(self.client.get('/api/agent/state',headers={"X-Agent-Key":b"\xff"}).status_code, 401)

    def test_manager_create_edit_delete_and_cross_origin_rejection(self):
        body={"data":{"title":"ساعت کاری","body":"۹ تا ۵","kind":"fact"}}
        blocked=self.client.post('/api/agent/memories',json=body,headers={**self.headers,"Origin":"https://evil.example"})
        self.assertEqual(blocked.status_code,403)
        result=self.client.post('/api/agent/memories',json=body,headers=self.headers)
        self.assertEqual(result.status_code,200)
        item_id=result.json()['id']
        body['data']['body']='۹ تا ۴'
        self.assertEqual(self.client.put(f'/api/agent/memories/{item_id}',json=body,headers=self.headers).status_code,200)
        state=self.client.get('/api/agent/state',headers=self.headers).json()
        self.assertEqual(state['memories'][0]['body'],'۹ تا ۴')
        self.assertEqual(self.client.delete(f'/api/agent/memories/{item_id}',headers=self.headers).status_code,200)
        self.assertEqual(self.store.rows('memories'),[])

    def test_voice_proposal_cannot_be_confirmed_without_manager(self):
        proposal=self.store.propose('session','memory',dict(title='مدیر',body='آقای خدیوزاد',kind='fact'))
        body=dict(proposal_id=proposal['id'],session_id='session')
        self.assertEqual(self.client.post('/api/agent/confirm-memory',json=body).status_code,401)
        self.assertEqual(self.store.rows('memories'),[])
        self.assertEqual(self.client.post('/api/agent/confirm-memory',json=body,headers=self.headers).status_code,200)
        self.assertEqual(self.client.post('/api/agent/confirm-memory',json=body,headers=self.headers).status_code,400)

    def test_invalid_room_is_rejected_over_http(self):
        data=dict(name='اتاق فروش',aliases=[],map_name='A',x=1,y=2,z=0,rotation=180,enabled=True)
        self.assertEqual(self.client.post('/api/agent/rooms',json={'data':data},headers=self.headers).status_code,400)


if __name__ == '__main__': unittest.main()
