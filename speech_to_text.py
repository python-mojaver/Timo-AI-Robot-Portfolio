"""Persian speech recognition: Groq in memory, with explicit local opt-in.

No audio is written to disk here. No local model is imported or loaded in
Groq mode. This is turn-based transcription, not a native speech-to-speech API.
"""
import io
import array
import hashlib
import sys
import wave
import json
import os
import re
import socket
import threading
import time
import uuid
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DEBUG = os.getenv("TIMO_STT_DEBUG", "").strip() == "1"
PROVIDER = os.getenv("TIMO_STT_PROVIDER", "groq").strip().lower()
MODEL_NAME = os.getenv("TIMO_STT_MODEL", "small").strip() or "small"
GROQ_MODEL = os.getenv("TIMO_GROQ_STT_MODEL", "whisper-large-v3").strip()
PERSIAN_PROMPT = os.getenv("TIMO_STT_PROMPT", "گفت‌وگوی فارسی با ربات تیمو، HTN Prime.")
STT_DEVICE = os.getenv("TIMO_STT_DEVICE", "cpu").strip() or "cpu"
COMPUTE_TYPE = os.getenv("TIMO_STT_COMPUTE_TYPE", "int8").strip() or "int8"
CPU_THREADS = max(4, min(os.cpu_count() or 4, 8))
BEAM_SIZE = max(1, min(10, int(os.getenv("TIMO_STT_BEAM_SIZE", "3"))))
MAX_AUDIO_BYTES = 24 * 1024 * 1024
_transcribe_lock = threading.Lock()
model = None


class STTError(RuntimeError):
    """Safe error text intended for the user; never includes API credentials."""


def normalize_persian(text):
    return re.sub(r"\s+", " ", (text or "").replace("ي", "ی")
                  .replace("ك", "ک").replace("ۀ", "ه")).strip()


def _audio_bytes(audio):
    if isinstance(audio, (bytes, bytearray, memoryview)):
        data = bytes(audio)
    else:
        with open(audio, "rb") as source:
            data = source.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise STTError("صدای دریافتی خالی است؛ دوباره صحبت کنید.")
    if len(data) > MAX_AUDIO_BYTES:
        raise STTError("حجم صدا بیشتر از ۲۴ مگابایت است؛ ضبط کوتاه‌تری بفرستید.")
    return data


def _audio_type(data):
    # فرمت را از امضای بایت‌ها می‌خوانیم؛ پسوند نام فایل به‌تنهایی قابل اتکا نیست.
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "speech.wav", "audio/wav"
    if data[:4] == b"fLaC":
        return "speech.flac", "audio/flac"
    if data[:4] == b"OggS":
        return "speech.ogg", "audio/ogg"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "speech.webm", "audio/webm"
    if data[4:8] == b"ftyp":
        return "speech.m4a", "audio/mp4"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224):
        return "speech.mp3", "audio/mpeg"
    raise STTError("فرمت صدا شناسایی نشد؛ فایل WAV یا WebM معتبر بفرستید.")



def inspect_wav(data):
    """Inspect original bytes without changing or saving them.

    PCM statistics are measured on signed 16-bit little-endian samples.
    Edge RMS is descriptive only; it cannot prove that a word was clipped.
    """
    info = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        info["wav_status"] = "not_wav"
        return info
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            ch, sw, sr, n = (audio.getnchannels(), audio.getsampwidth(),
                             audio.getframerate(), audio.getnframes())
            frames = audio.readframes(n)
        expected = n * ch * sw
        info.update(wav_status="ok" if len(frames) == expected else "truncated",
                    channels=ch, bits=sw * 8, sample_rate=sr, frames=n,
                    duration_s=round(n / sr, 4), frame_bytes=len(frames),
                    expected_frame_bytes=expected)
        if sw == 2 and frames:
            samples = array.array("h")
            samples.frombytes(frames[:len(frames) // 2 * 2])
            if sys.byteorder != "little":
                samples.byteswap()
            def rms(values):
                return round((sum(x * x for x in values) / max(len(values), 1)) ** 0.5, 2)
            k = max(1, round(sr * 0.3)) * ch
            info.update(peak=max(abs(x) for x in samples), rms=rms(samples),
                        clip_fraction=round(sum(x <= -32768 or x >= 32767
                                                for x in samples) / len(samples), 6),
                        head300ms_rms=rms(samples[:k]), tail300ms_rms=rms(samples[-k:]))
        return info
    except Exception as exc:
        info.update(wav_status="unreadable_or_unsupported", error_type=type(exc).__name__)
        return info


def _debug_log(request_id, event, details):
    # Optional diagnostics must never fail a successful recognition request.
    if DEBUG:
        try:
            line = json.dumps({"request_id": request_id, "event": event, **details},
                              ensure_ascii=False, allow_nan=False)
            print("[STT-DEBUG] " + line, flush=True)
        except Exception:
            pass


def _groq_transcribe(audio):
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise STTError("کلید Groq تنظیم نشده است؛ GROQ_API_KEY را در .env بگذارید و سرور را دوباره اجرا کنید.")
    if GROQ_MODEL not in {"whisper-large-v3", "whisper-large-v3-turbo"}:
        raise STTError("TIMO_GROQ_STT_MODEL باید whisper-large-v3 یا whisper-large-v3-turbo باشد.")
    data = _audio_bytes(audio)
    filename, mime = _audio_type(data)
    boundary = "timo-" + uuid.uuid4().hex
    fields = {"model": GROQ_MODEL, "language": "fa", "response_format": "json", "temperature": "0"}
    if PERSIAN_PROMPT.strip():
        fields["prompt"] = PERSIAN_PROMPT.strip()
    debug_id = uuid.uuid4().hex[:12] if DEBUG else ""
    if DEBUG:
        # حالت عیب‌یابی جزئیات قطعه‌های تشخیص را می‌گیرد؛ ممکن است متن گفتار در لاگ ثبت شود.
        fields["response_format"] = "verbose_json"
        _debug_log(debug_id, "input", {**inspect_wav(data), "model": GROQ_MODEL,
                                     "language": "fa", "temperature": 0,
                                     "prompt_len": len(PERSIAN_PROMPT.strip()),
                                     "prompt_sha256": hashlib.sha256(PERSIAN_PROMPT.strip().encode("utf-8")).hexdigest()})
    # بدنهٔ درخواست Groq در حافظه ساخته می‌شود؛ این مسیر فایل صوتی روی دیسک نمی‌نویسد.
    chunks = []
    for name, value in fields.items():
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode("utf-8"))
    chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode("ascii"))
    chunks.extend([data, f"\r\n--{boundary}--\r\n".encode("ascii")])
    req = request.Request("https://api.groq.com/openai/v1/audio/transcriptions",
                          data=b"".join(chunks), method="POST",
                          headers={"Authorization": "Bearer " + key,
                                   "Content-Type": "multipart/form-data; boundary=" + boundary,
                                   "User-Agent": "Timo-Voice/1.0"})
    try:
        timeout = max(5.0, min(60.0, float(os.getenv("TIMO_GROQ_STT_TIMEOUT", "20"))))
        with request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read())
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        messages = {
            400: "Groq صدا یا تنظیمات مدل را نپذیرفت؛ فرمت صدا و نام مدل را بررسی کنید.",
            401: "کلید Groq نامعتبر است؛ GROQ_API_KEY را بررسی کنید.",
            403: "دسترسی حساب یا اتصال به Groq مجاز نیست؛ وضعیت حساب و دسترسی را بررسی کنید.",
            413: "Groq حجم صدا را نپذیرفت؛ ضبط کوتاه‌تری بفرستید.",
            429: "به سقف درخواست یا سهمیهٔ Groq رسیدید؛ کمی بعد دوباره تلاش کنید."
        }
        raise STTError(messages.get(code, "سرویس Groq در دسترس نیست؛ کمی بعد دوباره تلاش کنید.")) from None
    except (socket.timeout, TimeoutError):
        raise STTError("پاسخ Groq طول کشید؛ اتصال اینترنت را بررسی و دوباره تلاش کنید.") from None
    except error.URLError:
        raise STTError("اتصال به Groq برقرار نشد؛ اینترنت و دسترسی به api.groq.com را بررسی کنید.") from None
    except (ValueError, OSError):
        raise STTError("پاسخ Groq قابل پردازش نبود؛ اتصال و تنظیم زمان انتظار را بررسی کنید.") from None
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise STTError("پاسخ معتبر تشخیص گفتار از Groq دریافت نشد.")
    if DEBUG:
        _debug_log(debug_id, "raw", {"text": result["text"]})
        segments = result.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if isinstance(segment, dict):
                    _debug_log(debug_id, "segment", {name: segment.get(name) for name in
                               ("id", "start", "end", "avg_logprob", "no_speech_prob",
                                "compression_ratio", "text")})
    return normalize_persian(result["text"]) or None


def _local_transcribe(audio):
    global model
    # مدل محلی فقط در حالت local و در اولین درخواست بارگذاری می‌شود.
    if model is None:
        from faster_whisper import WhisperModel
        print("Loading local Whisper model...", flush=True)
        model = WhisperModel(MODEL_NAME, device=STT_DEVICE, compute_type=COMPUTE_TYPE,
                             cpu_threads=CPU_THREADS, num_workers=1)
    source = io.BytesIO(bytes(audio)) if isinstance(audio, (bytes, bytearray, memoryview)) else audio
    try:
        segments, _ = model.transcribe(source, language="fa", beam_size=BEAM_SIZE,
                                      temperature=0.0, condition_on_previous_text=False,
                                      without_timestamps=True, vad_filter=True,
                                      vad_parameters={"min_silence_duration_ms": 250, "speech_pad_ms": 150},
                                      initial_prompt=PERSIAN_PROMPT)
        return normalize_persian(" ".join(segment.text or "" for segment in segments)) or None
    except Exception:
        raise STTError("تشخیص گفتار محلی ناموفق بود؛ مدل و فایل صدا را بررسی کنید.") from None


def transcribe_audio(audio):
    started = time.perf_counter()
    try:
        if PROVIDER == "groq":
            # No CPU inference lock and no implicit fallback to a slow local model.
            # خطای Groq باعث دانلود یا اجرای خودکار مدل محلی نمی‌شود.
            return _groq_transcribe(audio)
        if PROVIDER == "local":
            with _transcribe_lock:
                return _local_transcribe(audio)
        raise STTError("TIMO_STT_PROVIDER باید groq یا local باشد.")
    finally:
        print(f"[TIMING] stt provider={PROVIDER} model={GROQ_MODEL if PROVIDER == 'groq' else MODEL_NAME} "
              f"total_ms={round((time.perf_counter()-started)*1000)}", flush=True)


print(f"STT ready: provider={PROVIDER}; audio=in-memory; local_model=not-loaded", flush=True)

