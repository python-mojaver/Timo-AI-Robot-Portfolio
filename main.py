import os
import tempfile
import uuid
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# تنظیمات را پیش از واردکردن ماژول‌های وابسته می‌خوانیم تا مسیرها و سرویس‌ها درست انتخاب شوند.
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.background import BackgroundTask
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

from agent_graph import chat as agent_chat
from face_reaction import reaction
from agent_api import router as agent_router
from agent_host import router as host_router
from agent_store import admin_key, get_store
from starlette.concurrency import run_in_threadpool
from voice import AUDIO_DIR, generate_voice
from database import create_tables
import voice_stream
from speech_to_text import transcribe_audio
from response_language import fixed_reply


app = FastAPI(
    title="HTN Prime",
    version="2.2.0-langgraph"
)


@app.middleware("http")
async def log_stage_duration(request: Request, call_next):
    if request.url.path not in {"/api/transcribe", "/api/chat", "/api/speak"}:
        return await call_next(request)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - started) * 1000)
    response.headers["Server-Timing"] = f"total;dur={elapsed}"
    print(f"[TIMING] {request.url.path} status={response.status_code} total_ms={elapsed}", flush=True)
    return response

# Create missing schemas without replacing existing data.
# فقط جدول‌های ناموجود ساخته می‌شوند؛ اطلاعات قبلی کاتالوگ جایگزین نمی‌شوند.
create_tables()
get_store()
admin_key()
app.include_router(agent_router)
app.include_router(host_router)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# پوشه‌ی generated_audio رو به صورت استاتیک در دسترس مرورگر/وب‌ویو قرار میده
# تا فایل‌های mp3 صدای ربات واقعاً قابل دانلود/پخش باشن
os.makedirs(AUDIO_DIR, exist_ok=True)

app.mount(
    "/generated_audio",
    StaticFiles(directory=AUDIO_DIR),
    name="generated_audio"
)


class ChatRequest(BaseModel):
    message: str = Field(max_length=6000)
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=128)
    input_source: Literal["text", "voice"] = "text"
    response_language: Literal["fa-IR", "en-US", "tr-TR", "az-AZ"] = "fa-IR"


class SpeakRequest(BaseModel):
    text: str

class StreamSpeakRequest(BaseModel):
    text: str = Field(min_length=1,max_length=6000)
    language: Literal['auto','fa-IR','en-US','tr-TR','az-AZ'] = 'auto'

@app.post('/api/speak/prepare')
def prepare_speech(data: StreamSpeakRequest):
    try:return voice_stream.prepare(data.text,data.language)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    except RuntimeError as exc:raise HTTPException(429,str(exc)) from exc

@app.get('/api/speak/stream/{token}')
async def stream_speech(token: str):
    if len(token)!=48 or any(c not in '0123456789abcdef' for c in token):raise HTTPException(404,'Audio not found')
    # هر توکن فقط یک بار مصرف می‌شود؛ درخواست منقضی‌شده باید دوباره آماده شود.
    job=voice_stream.take(token)
    if job is None:raise HTTPException(404,'Audio expired; prepare again')
    stream=voice_stream.audio_chunks(job)
    # پیش از شروع پاسخ استریم، اولین بخش صدا را می‌گیریم تا خطای سرویس قابل گزارش باشد.
    try:first=await asyncio.wait_for(anext(stream),timeout=15)
    except Exception as exc:
        await stream.aclose()
        raise HTTPException(502,'تولید صدای پاسخ آغاز نشد؛ اتصال سرویس صدا را بررسی کنید.') from exc
    async def body():
        try:
            yield first
            async for data in stream:yield data
        finally:await stream.aclose()
    return StreamingResponse(body(),media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'},background=BackgroundTask(stream.aclose))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/agent", response_class=HTMLResponse)
def agent_admin(request: Request):
    return templates.TemplateResponse(request=request, name="agent.html", context={})


@app.post("/api/chat")
def chat(data: ChatRequest):

    message = data.message.strip()

    if not message:
        return {
            "response": fixed_reply("لطفاً سوالتون رو دوباره بگید.", data.response_language),
            "response_language": data.response_language,
            "face": reaction("", "")
        }

    try:
        print("[CHAT-LANGUAGE] response_language=" + data.response_language, flush=True)
        # شناسهٔ جلسه، حافظهٔ همین گفتگو را از گفتگوهای دیگر جدا نگه می‌دارد.
        return agent_chat(message, data.session_id, data.input_source, response_language=data.response_language)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/speak")
def speak_response(data: SpeakRequest):

    text = data.text.strip()

    if not text:
        return {
            "status": "error",
            "audio_url": None
        }

    audio_path = generate_voice(text)

    if not audio_path:
        return {
            "status": "error",
            "audio_url": None
        }

    # audio_path مسیر فایل روی دیسکه (مثلا generated_audio/voice_xxx.mp3)
    # اینجا اون رو به یک URL قابل دسترس از مرورگر/وب‌ویو تبدیل می‌کنیم
    audio_filename = os.path.basename(audio_path)
    audio_url = f"/generated_audio/{audio_filename}"

    return {
        "status": "ok",
        "audio_url": audio_url
    }


@app.post("/api/transcribe")
async def transcribe(request: Request):
    from speech_to_text import STTError
    limit = 24 * 1024 * 1024
    try:
        if request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
            # Compatibility for older clients; updated clients send raw audio.
            async with request.form(max_files=1, max_fields=4) as form:
                upload = form.get("file")
                if upload is None or not hasattr(upload, "read"):
                    raise HTTPException(400, "فایل صدا دریافت نشد.")
                audio_bytes = await upload.read(limit + 1)
        else:
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "حجم صدا بیشتر از ۲۴ مگابایت است.")
                chunks.append(chunk)
            audio_bytes = b"".join(chunks)
        if len(audio_bytes) > limit:
            raise HTTPException(413, "حجم صدا بیشتر از ۲۴ مگابایت است.")
        if not audio_bytes:
            raise HTTPException(400, "صدای دریافتی خالی است.")
        # تماس مسدودکنندهٔ تشخیص گفتار را خارج از حلقهٔ رویداد اجرا می‌کنیم.
        text = await run_in_threadpool(transcribe_audio, audio_bytes)
        if not text:
            return {"status": "error", "text": "", "message": "صدایی تشخیص داده نشد؛ دوباره صحبت کنید."}
        return {"status": "ok", "text": text}
    except STTError as exc:
        return {"status": "error", "text": "", "message": str(exc)}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Transcribe API failed: {type(exc).__name__}", flush=True)
        return {"status": "error", "text": "", "message": "پردازش صدا ناموفق بود؛ اتصال و خروجی ترمینال را بررسی کنید."}



if __name__ == "__main__":
    import uvicorn

    # Loopback is the default. Use an explicit host only on a trusted network.
    uvicorn.run(app, host=os.getenv("TIMO_BIND_HOST", "127.0.0.1"), port=8000)
