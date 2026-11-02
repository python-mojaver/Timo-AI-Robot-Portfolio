"""Deliver fresh recognition greetings to one operator-paired robot session.

Single-process broker: run the existing uvicorn server with one worker.
Recognition never initiates movement or changes permanent knowledge.
"""
import hmac
import hashlib
import json
import math
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agent_api import require_manager

PROFILE_PATH = Path(__file__).resolve().parent / 'data' / 'agent-people.json'
DEFAULT_PEOPLE = {'Mojaver': {'display_name': 'آقای مجاور',
                            'greeting': 'سلام آقای مجاور، خوش اومدید. حالتون چطوره؟'}}


def load_people():
    if not PROFILE_PATH.exists():
        return DEFAULT_PEOPLE.copy()
    value = json.loads(PROFILE_PATH.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or len(value) > 100:
        raise ValueError('فایل معرفی افراد باید یک شیء با حداکثر ۱۰۰ فرد باشد.')
    result = {}
    for identity, item in value.items():
        if (not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', identity)
                or not isinstance(item, dict)):
            raise ValueError('شناسه و مشخصات فرد نامعتبر است.')
        display = item.get('display_name', '')
        greeting = item.get('greeting', '')
        if not isinstance(display, str) or not display.strip() or len(display) > 100:
            raise ValueError('نام نمایشی فرد نامعتبر است.')
        if not isinstance(greeting, str) or not greeting.strip() or len(greeting) > 600:
            raise ValueError('متن سلام باید بین ۱ تا ۶۰۰ نویسه باشد.')
        result[identity] = {'display_name': display.strip(), 'greeting': greeting.strip()}
    return result


class HostBroker:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.target = None
        self.pending = None
        self.last_greeted = {}
        self.speech_receipts = {}

    def pair(self, session_id):
        with self.lock:
            token = secrets.token_urlsafe(32)
            self.target = {'session_id': session_id, 'token': token, 'seen': self.clock()}
            self._finish_speech('cancelled')
            self.pending = None
            return {'token': token, 'session_id': session_id}

    def _finish_speech(self, state):
        if self.pending and self.pending.get('type') == 'operator_speech':
            item = self.speech_receipts.get(self.pending['request_id'])
            if item:
                item['state'] = state

    def _expire_pending(self):
        if self.pending and self.pending['expires'] <= self.clock():
            self._finish_speech('expired')
            self.pending = None

    def speech_status(self):
        with self.lock:
            self._expire_pending()
            return {'robot_connected': bool(self.target and self.clock() - self.target['seen'] <= 20),
                    'receipts': [{'request_id': k, 'state': v['state']} for k, v in self.speech_receipts.items()]}

    def say(self, text, request_id):
        # Operator text bypasses chat, intent routing and knowledge storage.
        with self.lock:
            now = self.clock()
            self._expire_pending()
            fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()
            previous = self.speech_receipts.get(request_id)
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise ValueError('شناسهٔ ارسال قبلاً برای متن دیگری استفاده شده است.')
                return {'request_id': request_id, 'status': previous['state']}
            if not self.target or now - self.target['seen'] > 20:
                raise ValueError('ابتدا روی ربات، «اتصال صدای ربات» را فعال کنید.')
            if self.pending:
                raise ValueError('یک پیام دیگر در انتظار پخش یا در حال پخش است؛ پس از پایان آن بفرستید.')
            self.pending = {'id': secrets.token_urlsafe(18), 'identity': '__operator__',
                            'type': 'operator_speech', 'request_id': request_id,
                            'display_name': 'متن ارسالی', 'response': text, 'expires': now + 30}
            self.speech_receipts[request_id] = {'fingerprint': fingerprint, 'state': 'queued'}
            while len(self.speech_receipts) > 100:
                self.speech_receipts.pop(next(iter(self.speech_receipts)))
            return {'request_id': request_id, 'status': 'queued'}

    def _authorize(self, token):
        if (not self.target or not token or
                not hmac.compare_digest(token.encode('utf-8'), self.target['token'].encode('utf-8')) or
                self.clock() - self.target['seen'] > 20):
            raise PermissionError('اتصال حالت میزبان منقضی شده؛ دوباره فعالش کنید.')
        self.target['seen'] = self.clock()

    def recognize(self, identity, confidence, people):
        with self.lock:
            now = self.clock()
            self._expire_pending()
            if not math.isfinite(confidence) or not 0.40 <= confidence <= 1:
                return {'status': 'ignored', 'reason': 'low_confidence'}
            if identity not in people:
                return {'status': 'ignored', 'reason': 'unregistered_person'}
            if not self.target or now - self.target['seen'] > 20:
                return {'status': 'ignored', 'reason': 'no_active_robot'}
            if now - self.last_greeted.get(identity, -1000000) < 300:
                return {'status': 'ignored', 'reason': 'cooldown'}
            if self.pending and self.pending['expires'] > now:
                return {'status': 'ignored', 'reason': 'greeting_pending'}
            profile = people[identity]
            self.pending = {'id': secrets.token_urlsafe(18), 'identity': identity,
                            'display_name': profile['display_name'],
                            'response': profile['greeting'], 'expires': now + 15}
            return {'status': 'queued'}

    def next(self, token):
        with self.lock:
            self._authorize(token)
            self._expire_pending()
            if not self.pending:
                return {'event': None}
            return {'event': {k: v for k, v in self.pending.items() if k != 'expires'}}

    def acknowledge(self, token, event_id, delivered):
        with self.lock:
            self._authorize(token)
            if not self.pending or self.pending['id'] != event_id:
                return {'status': 'stale'}
            if self.pending['expires'] <= self.clock():
                self._finish_speech('expired')
                self.pending = None
                return {'status': 'stale'}
            # Both attempts and successful playback are debounced. A failed TTS
            # connection must not make the robot repeat the same greeting forever.
            self.last_greeted[self.pending['identity']] = self.clock()
            self._finish_speech('delivered' if delivered else 'failed')
            self.pending = None
            return {'status': 'delivered' if delivered else 'dismissed'}

    def claim(self, token, event_id):
        with self.lock:
            self._authorize(token)
            if (not self.pending or self.pending['id'] != event_id or
                    self.pending['expires'] <= self.clock() or self.pending.get('claimed')):
                return {'status': 'stale'}
            self.pending['claimed'] = True
            self._finish_speech('playing')
            self.pending['expires'] = self.clock() + 120
            return {'status': 'claimed'}

    def unpair(self, token):
        with self.lock:
            self._authorize(token)
            self.target = None
            self._finish_speech('cancelled')
            self.pending = None
            return {'status': 'disabled'}


broker = HostBroker()
router = APIRouter(prefix='/api/agent/host')


class Pair(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


class Recognition(BaseModel):
    type: str = 'PERSON_RECOGNIZED'
    name: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class Acknowledgement(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    delivered: bool


class Claim(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)


def host_token(request: Request):
    return request.headers.get('X-Host-Token', '')


def authorized(callback):
    try:
        return callback()
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post('/pair', dependencies=[Depends(require_manager)])
def pair(data: Pair):
    return broker.pair(data.session_id)


@router.post('/recognition', dependencies=[Depends(require_manager)])
def recognition(data: Recognition):
    if data.type != 'PERSON_RECOGNIZED':
        raise HTTPException(400, 'نوع رویداد تشخیص چهره پشتیبانی نمی‌شود.')
    try:
        people = load_people()
    except (OSError, ValueError) as exc:
        raise HTTPException(400, 'فایل معرفی افراد معتبر نیست؛ data/agent-people.json را بررسی کنید.') from exc
    return broker.recognize(data.name, data.confidence, people)


@router.get('/next')
def next_event(token: str = Depends(host_token)):
    return authorized(lambda: broker.next(token))


@router.post('/ack')
def acknowledge(data: Acknowledgement, token: str = Depends(host_token)):
    return authorized(lambda: broker.acknowledge(token, data.event_id, data.delivered))


@router.post('/claim')
def claim(data: Claim, token: str = Depends(host_token)):
    return authorized(lambda: broker.claim(token, data.event_id))


@router.post('/unpair')
def unpair(token: str = Depends(host_token)):
    return authorized(lambda: broker.unpair(token))


class OperatorSpeech(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


@router.post('/say', dependencies=[Depends(require_manager)])
def operator_say(data: OperatorSpeech):
    text = data.text.strip()
    if not text:
        raise HTTPException(422, 'متنی برای گفتن وارد کنید.')
    try:
        return broker.say(text, data.request_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/speech-status', dependencies=[Depends(require_manager)])
def operator_speech_status():
    return broker.speech_status()
