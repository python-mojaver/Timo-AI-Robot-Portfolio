import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import agent_host
from agent_host import HostBroker, DEFAULT_PEOPLE


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.broker = HostBroker(lambda: self.now)
        self.token = self.broker.pair('robot-session')['token']

    def publish(self, **changes):
        values = dict(identity='Mojaver', confidence=0.8, people=DEFAULT_PEOPLE)
        values.update(changes)
        return self.broker.recognize(**values)

    def test_delivery_claim_and_repeat_suppression(self):
        self.assertEqual(self.publish()['status'], 'queued')
        event = self.broker.next(self.token)['event']
        self.assertNotIn('action', event)
        self.assertIn('مجاور', event['response'])
        self.assertEqual(self.publish()['reason'], 'greeting_pending')
        self.assertEqual(self.broker.claim(self.token, event['id'])['status'], 'claimed')
        self.assertEqual(self.broker.claim(self.token, event['id'])['status'], 'stale')
        self.assertEqual(self.broker.acknowledge(self.token, event['id'], True)['status'], 'delivered')
        self.assertEqual(self.publish()['reason'], 'cooldown')

    def test_stale_camera_event_is_discarded_after_15_seconds(self):
        self.publish()
        self.now += 16
        self.assertIsNone(self.broker.next(self.token)['event'])

    def test_long_playback_keeps_claim_with_heartbeat(self):
        self.publish()
        event = self.broker.next(self.token)['event']
        self.broker.claim(self.token, event['id'])
        for _ in range(6):
            self.now += 10
            self.assertEqual(self.broker.next(self.token)['event']['id'], event['id'])
        self.assertEqual(self.broker.acknowledge(self.token, event['id'], True)['status'], 'delivered')

    def test_untrusted_low_and_unknown_recognition_do_not_greet(self):
        for score in [0.39, float('nan'), float('inf'), -1]:
            self.assertEqual(self.publish(confidence=score)['status'], 'ignored')
        self.assertEqual(self.publish(identity='Unknown')['reason'], 'unregistered_person')
        self.assertIsNone(self.broker.next(self.token)['event'])

    def test_pairing_is_private_and_replacement_revokes_old_session(self):
        for token in ['', 'wrong', 'کلید اشتباه']:
            with self.assertRaises(PermissionError): self.broker.next(token)
        other = self.broker.pair('other-session')['token']
        with self.assertRaises(PermissionError): self.broker.next(self.token)
        self.assertIsNone(self.broker.next(other)['event'])

    def test_closed_or_expired_page_cannot_receive_recognition(self):
        self.now += 21
        self.assertEqual(self.publish()['reason'], 'no_active_robot')
        with self.assertRaises(PermissionError): self.broker.next(self.token)

    def test_failed_audio_attempt_is_debounced_and_unpair_drops_queue(self):
        self.publish()
        event = self.broker.next(self.token)['event']
        self.broker.acknowledge(self.token, event['id'], False)
        self.assertEqual(self.publish()['reason'], 'cooldown')
        self.broker.unpair(self.token)
        self.assertEqual(self.publish()['reason'], 'no_active_robot')


class HostApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(agent_host.router)
        self.client = TestClient(app)
        self.broker = HostBroker()
        self.patches = [patch.object(agent_host, 'broker', self.broker),
                        patch('agent_api.admin_key', return_value='test-key'),
                        patch.object(agent_host, 'load_people', return_value=DEFAULT_PEOPLE)]
        for p in self.patches: p.start()

    def tearDown(self):
        self.client.close()
        for p in self.patches: p.stop()

    def test_authentication_recognition_and_scoped_delivery_over_http(self):
        url = '/api/agent/host'
        self.assertEqual(self.client.post(url+'/pair', json={'session_id':'robot'}).status_code, 401)
        headers = {'X-Agent-Key':'test-key'}
        pair = self.client.post(url+'/pair', json={'session_id':'robot'}, headers=headers).json()
        recognition = {'name':'Mojaver','confidence':0.9}
        self.assertEqual(self.client.post(url+'/recognition', json=recognition).status_code, 401)
        self.assertEqual(self.client.post(url+'/recognition', json=recognition, headers=headers).json()['status'], 'queued')
        self.assertEqual(self.client.get(url+'/next').status_code, 401)
        token = {'X-Host-Token':pair['token']}
        event = self.client.get(url+'/next', headers=token).json()['event']
        self.assertEqual(self.client.post(url+'/claim', json={'event_id':event['id']}, headers=token).json()['status'], 'claimed')
        self.assertEqual(self.client.post(url+'/ack', json={'event_id':event['id'],'delivered':True}, headers=token).json()['status'], 'delivered')
        self.assertIsNone(self.client.get(url+'/next', headers=token).json()['event'])

    def test_external_origin_invalid_scores_and_unknown_event_are_rejected(self):
        url = '/api/agent/host'
        headers = {'X-Agent-Key':'test-key','Origin':'http://other.example'}
        self.assertEqual(self.client.post(url+'/pair', json={'session_id':'robot'}, headers=headers).status_code, 403)
        headers.pop('Origin')
        self.assertEqual(self.client.post(url+'/recognition',json={'name':'Mojaver','confidence':1.1},headers=headers).status_code,422)
        self.assertEqual(self.client.post(url+'/recognition',json={'name':'Mojaver','confidence':0.9,'type':'MOVE'},headers=headers).status_code,400)


if __name__ == '__main__': unittest.main()
