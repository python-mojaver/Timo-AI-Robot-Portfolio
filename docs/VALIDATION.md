# Validation — 2 November 2026

Prepared from the uploaded Python/web source, with working-company data excluded.

| Check | Result | Scope |
| --- | --- | --- |
| Python `run_tests.py` | 54 tests passed | Synthetic catalog; temporary SQLite state; network/model doubles |
| JavaScript `npm test` | 4 suites passed | DOM/VM checks, not real-browser pixels or hardware |
| Python syntax | Passed | All included Python files parse |
| Fresh-checkout smoke | Passed | `/`, `/agent`, `/docs`, OpenAPI and static assets return 200; local catalog question and price follow-up work |
| Operator boundaries | Passed in smoke/tests | Unauthenticated state returns 401; credential-file URL returns 404; cross-origin management writes rejected |
| Voice request smoke | Passed | Empty audio rejected with 400; TTS preparation returns a job without calling the live speech provider |
| Public-file scan | Passed | No tracked runtime databases, face samples, real price workbook, model weights, backup trees, `.env` or recognizable API-key patterns |

The JavaScript suites cover stale response suppression, playback interruption, mono WAV encoding, PCM onset/silence boundaries, playback/echo suppression, manager operations, safe text rendering, map synchronization, duplicate navigation prevention and the recognition greeting lifecycle.

## Fixes and packaging changes

- Updated test doubles to the current response-language, face metadata and progressive-TTS contracts. Updated the microphone harness from the old recorder polling API to continuous PCM ingestion.
- Fixed generic Persian catalog questions: “چه / محصولاتی / کالاهایی” no longer become mandatory product-search keywords. The existing catalog checkpoint/follow-up test now works with synthetic data.
- Made the catalog path configurable; added a non-overwriting synthetic-demo initializer and an isolated test runner.
- Matched the n8n webhook setting to the example workflow, while preserving the legacy `N8N_WEBHOOK_URL` override.
- Made templates/static/audio paths checkout-relative and ADB lookup configurable. The default public launch binds to loopback and uses one worker.
- Separated main web dependencies from optional local STT, vision and older desktop experiments. Local Whisper is no longer the default for a new checkout.
- Removed production catalog/chat databases, their SQLite sidecars, company price workbook, enrolled face images and update-backup directories from the public package. Replaced the office-specific initial destination with an inert example.
- Added current English/Persian guides, environment template, CI configuration and a resume description.

## What was not validated

No live Groq/n8n/Edge TTS request, real microphone recording, camera stream, Android build, vendor SDK callback, head/arm movement, physical navigation or emergency stopping was tested in this environment. Automated tests cannot establish Persian STT accuracy or actual robot motion. Native speech-to-speech and model fine-tuning are not implemented here.

The currently public Android repository is separate and may be older than the deployed device. The Python upload contained Android files only inside historical backup trees; these were excluded rather than treated as the current Android app.

## Publication status

The user has created the public `python-mojaver/Timo-AI-Robot-Portfolio` repository. Code publication has not yet been confirmed. The earlier `Timo-AI-Robot-Assistant` repository is private and will remain separate. `HTNRobotAssistant` is the separate Android Gradle project. Add the new public backend URL to the PDF resume only after the push is confirmed.
