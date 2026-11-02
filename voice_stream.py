"""Progressive TTS for the main WebView; legacy /api/speak stays compatible."""
import asyncio
import hashlib
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time

import edge_tts
from voice import AUDIO_DIR

VOICES={'fa-IR':'fa-IR-FaridNeural','en-US':'en-US-GuyNeural',
        'tr-TR':'tr-TR-EmelNeural','az-AZ':'az-AZ-BabekNeural'}
RATE='+8%'
_jobs={}
_lock=threading.RLock()
_slots=threading.BoundedSemaphore(3)

def chosen_language(text, language='auto'):
    # Output script wins over the input preference: a Persian answer must not
    # be sent to an English voice merely because the question was in English.
    if any('\u0600'<=c<='\u06ff' and c.isalpha() for c in text):return 'fa-IR'
    if language in ('tr-TR','az-AZ'):return language
    if 'ə' in text.lower():return 'az-AZ'
    if any(c in text for c in 'ğĞıİşŞçÇöÖüÜ'):return 'tr-TR'
    return 'en-US' if any('a'<=c.lower()<='z' for c in text) else 'fa-IR'

def cache_path(text, language='auto'):
    voice=VOICES[chosen_language(text,language)]
    # زبان، صدا و سرعت هم جزو کلید کش هستند تا فایل تنظیمات متفاوت اشتباه استفاده نشود.
    key=hashlib.sha256((voice+'\0'+RATE+'\0'+text).encode()).hexdigest()
    return Path(AUDIO_DIR)/('tts_'+key+'.mp3'),voice

def prepare(text,language='auto'):
    text=text.strip()
    if not text or len(text)>6000:raise ValueError('متن پخش معتبر نیست.')
    if language not in (*VOICES,'auto'):raise ValueError('زبان پخش معتبر نیست.')
    path,voice=cache_path(text,language)
    if path.is_file() and path.stat().st_size:
        return {'status':'ok','audio_url':'/generated_audio/'+path.name,'streaming':False,'voice':voice}
    with _lock:
        now=time.monotonic()
        for key in list(_jobs):
            if _jobs[key]['expires']<=now:_jobs.pop(key,None)
        if len(_jobs)>=64:raise RuntimeError('درخواست‌های صدا پر شده‌اند؛ کمی صبر کنید.')
        # توکن تصادفی، متن آماده‌شده را برای مدت کوتاه به یک درخواست پخش وصل می‌کند.
        token=secrets.token_hex(24)
        _jobs[token]={'text':text,'voice':voice,'path':path,'expires':now+60}
    return {'status':'ok','audio_url':'/api/speak/stream/'+token,'streaming':True,'voice':voice}

def take(token):
    with _lock:
        # برداشت اتمی زیر قفل اجازه نمی‌دهد دو درخواست، یک کار صوتی را مصرف کنند.
        job=_jobs.pop(token,None)
    return job if job and job['expires']>time.monotonic() else None

async def audio_chunks(job):
    # حداکثر سه تولید هم‌زمان صدا؛ درخواست اضافی منتظر اشغال نامحدود منابع نمی‌ماند.
    if not _slots.acquire(blocking=False):raise RuntimeError('TTS busy')
    path=job['path'];path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None;started=time.perf_counter();size=0
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.tts-',suffix='.part',delete=False) as output:
            temporary=Path(output.name)
            communicate=edge_tts.Communicate(text=job['text'],voice=job['voice'],rate=RATE,volume='+0%')
            async for chunk in communicate.stream():
                if chunk['type']!='audio' or not chunk.get('data'):continue
                data=chunk['data'];output.write(data)
                if not size:print('[TIMING] tts_first_audio_ms='+str(round((time.perf_counter()-started)*1000)),flush=True)
                size+=len(data)
                yield data
        if not size:raise RuntimeError('No audio received')
        # فایل کامل‌شده جایگزین کش می‌شود؛ دانلود نیمه‌تمام نباید به‌عنوان صدای آماده دیده شود.
        os.replace(temporary,path);temporary=None
        print('[TIMING] tts_stream_complete_ms='+str(round((time.perf_counter()-started)*1000)),flush=True)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
        _slots.release()

async def warm_short_replies():
    for word in ('معمولی','عادی','شاد','خوشحال','غمگین','ناراحت','عصبانی','متعجب'):
        result=prepare('باشه، '+word+' شدم.','fa-IR')
        if result['streaming']:
            job=take(result['audio_url'].rsplit('/',1)[-1])
            async for _ in audio_chunks(job):pass

if __name__=='__main__':asyncio.run(warm_short_replies())
