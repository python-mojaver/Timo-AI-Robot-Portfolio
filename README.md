# Timo AI Robot Assistant

Python backend and browser interface for a Persian-first robot assistant. Built by **Babak Mojaver** with **FastAPI, LangGraph, SQLite, Groq, n8n and OpenCV**.

This repository contains the Python/web side of the integration. The Android SDK bridge is a separate project: [HTNRobotAssistant](https://github.com/python-mojaver/HTNRobotAssistant). That public Android checkout may lag the deployed device; this backend does not include an APK or the vendor SDK.

[راهنمای فارسی](START_HERE_FA.md) · [Architecture](docs/ARCHITECTURE.md) · [Validation and limitations](docs/VALIDATION.md)

## Features implemented in the source

- FastAPI text-chat, audio-transcription and speech-playback endpoints; browser UI and Android WebView hooks.
- A real LangGraph state graph with SQLite checkpoints, separate conversation threads and a bounded model/tool loop. Up to four model calls per turn; six recent user turns retained.
- Two chat providers: an n8n webhook or direct Groq tool calling. The Groq path can search the catalog, retrieve approved knowledge, list destinations and prepare registered navigation commands.
- Operator-managed facts, Q&A, reply skills, rooms and shared-map settings, protected by an operator key. Spoken teaching creates a draft; an authenticated operator confirms it.
- Groq Whisper transcription from in-memory audio, with optional local faster-whisper. Edge TTS supports cached/progressive playback. Stop/typing/new-turn events interrupt playback and stale replies are rejected; the current PCM microphone pauses ingestion during playback and briefly afterwards to suppress speaker echo.
- Separate YuNet/SFace face recognition and a greeting broker for an operator-paired robot session. Face recognition does not grant navigation authority.
- Persian, English, Turkish and Azerbaijani response preferences. Recognition quality and voice availability vary by service and device.

## Quick start (Windows / PowerShell)

Use Python 3.12 or newer. From this repository folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe setup_demo.py
.\.venv\Scripts\python.exe setup_agent.py
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

If Python 3.12 is not installed, use `py -3 -m venv .venv` with your installed Python. Validation for this release used Python 3.12.

Open `http://127.0.0.1:8000/` for chat, `/agent` for the operator UI and `/docs` for the API. `setup_agent.py` displays the local operator key; keep it private. `setup_demo.py` creates three synthetic products and leaves an existing catalog untouched. Run it before the first server start if you want demo products.

For text chat, choose one provider in `.env`:

| Provider | Configuration |
| --- | --- |
| n8n | Import `HTN_Prime_Workflow.json`, attach your own model credentials, select an available model and activate the webhook. The supplied workflow uses a Gemini node; it is an example, not the deployed Groq workflow. |
| Direct Groq | Set `TIMO_CHAT_PROVIDER=groq`, `GROQ_API_KEY` and an available tool-capable `TIMO_GROQ_MODEL`. No n8n instance is needed. |

Speech recognition uses `TIMO_STT_PROVIDER=groq` and a private `GROQ_API_KEY`. Text-only chat and the operator UI can start without speech credentials. For local STT, install `requirements-local-stt.txt` and explicitly select `local`. Audio uploads may leave the device when a cloud service is selected. This is turn-based **speech → text → model → speech**, not a native speech-to-speech model.

## Optional face recognition

Install `requirements-vision-agent.txt`. Obtain the YuNet and SFace models separately from the [OpenCV model zoo](https://github.com/opencv/opencv_zoo), place them in `vision/models`, and enroll only consented local images in `vision/known_faces/<identity>/`. Copy `examples/agent-people.example.json` to `data/agent-people.json` and configure identities/greetings. Set `TIMO_ADB_PATH` or put `adb` on PATH, then run `agent_vision.py --check` before starting the camera loop.

The device-specific camera path `/dev/video20`, map/pose validation and Android bridge require the actual robot. No reference face images or trained model weights are distributed here.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_tests.py
npm ci
npm test
.\.venv\Scripts\python.exe scripts/check_public_files.py
```

Tests use temporary synthetic catalogs, temporary agent/checkpoint databases and mocked network/model responses. They do not validate live service quality or physical movement. See `docs/VALIDATION.md` for the results and scope of this release.

## Deployment boundaries

Run **one Uvicorn worker**: the greeting broker and streaming jobs are process-local. This is a local robot integration prototype, not a public multi-user SaaS. Keep it on loopback or a trusted controlled network. Conversation IDs separate state but are not account authentication. Navigation preparation/dispatch does not prove that a robot moved, arrived or stopped. Current WebView code uses the `direct-v2` Android bridge for explicit registered commands; an older README's per-command confirmation flow is not the current UI.

Existing deployments should keep their `.env`, databases, map settings and face enrollment. This sanitized public package is for a **separate checkout**, not an overwrite of the working robot folder.

`listen.py`, `realtime_voice.py`, `timo_runtime*.py` and standalone scripts under `vision/` include earlier desktop experiments. They are not the main web entry point; optional dependencies are listed in `requirements-legacy-cli.txt`. The broad `requirements-ai-libraries.txt` inventory records experiments and is not required for the app.
