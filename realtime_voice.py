import queue
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from speech_to_text import transcribe_audio


class RealtimeVoiceEngine:
    """Continuous mic -> VAD -> Whisper -> voice events."""

    def __init__(self, on_event=None, device=1, samplerate=16000,
                 block_ms=30, start_rms=0.025, stop_rms=0.012,
                 min_speech_ms=180, end_silence_ms=1100,
                 pre_roll_ms=450, max_utterance_seconds=20,
                 retrigger_guard_ms=350):
        self.on_event = on_event
        self.device = device
        self.samplerate = samplerate
        self.block_ms = block_ms
        self.blocksize = int(samplerate * block_ms / 1000)
        self.start_rms = start_rms
        self.stop_rms = stop_rms
        self.min_speech_blocks = max(1, int(min_speech_ms / block_ms))
        self.end_silence_blocks = max(1, int(end_silence_ms / block_ms))
        self.pre_roll_blocks = max(1, int(pre_roll_ms / block_ms))
        self.max_blocks = max(1, int(max_utterance_seconds * 1000 / block_ms))
        self.retrigger_guard_blocks = max(0, int(retrigger_guard_ms / block_ms))
        self.guard_blocks_left = 0
        self.running = False
        self.audio_queue = queue.Queue(maxsize=200)
        self.worker = None
        self.stream = None
        self.speaking = False
        self.speech_blocks = 0
        self.silence_blocks = 0
        self.utterance = []
        self.pre_roll = []

    def _emit(self, event_type, **payload):
        event = {"type": event_type, **payload, "timestamp": time.time()}
        print(f"[VOICE EVENT] {event}")
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _rms(block):
        return float(np.sqrt(np.mean(np.square(block), dtype=np.float64))) if block.size else 0.0

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[VOICE] Audio status: {status}")
        if not self.running:
            return
        block = indata[:, 0].copy()
        try:
            self.audio_queue.put_nowait(block)
        except queue.Full:
            pass

    def _reset(self):
        self.speaking = False
        self.speech_blocks = 0
        self.silence_blocks = 0
        self.utterance = []
        self.guard_blocks_left = self.retrigger_guard_blocks

    def _process(self, block):
        rms = self._rms(block)
        if not self.speaking:
            self.pre_roll.append(block)
            if len(self.pre_roll) > self.pre_roll_blocks:
                self.pre_roll.pop(0)
            if self.guard_blocks_left > 0:
                self.guard_blocks_left -= 1
                self.speech_blocks = 0
                return
            self.speech_blocks = self.speech_blocks + 1 if rms >= self.start_rms else 0
            if self.speech_blocks >= self.min_speech_blocks:
                self.speaking = True
                self.silence_blocks = 0
                self.utterance = list(self.pre_roll)
                self._emit("USER_SPEECH_STARTED", rms=round(rms, 5))
            return

        self.utterance.append(block)
        self.silence_blocks = self.silence_blocks + 1 if rms <= self.stop_rms else 0
        if self.silence_blocks >= self.end_silence_blocks or len(self.utterance) >= self.max_blocks:
            audio = np.concatenate(self.utterance)
            self._emit("USER_SPEECH_ENDED", duration=round(len(audio) / self.samplerate, 2))
            self._reset()
            threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio):
        path = None
        try:
            pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
            f = tempfile.NamedTemporaryFile(prefix="timo_voice_", suffix=".wav", delete=False)
            path = Path(f.name)
            f.close()
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.samplerate)
                w.writeframes(pcm.tobytes())
            print("[VOICE] Sending utterance to Whisper...")
            text = transcribe_audio(str(path))
            if text:
                self._emit("USER_TRANSCRIPT", text=text)
            else:
                print("[VOICE] Whisper returned no text.")
        except Exception as exc:
            print(f"[VOICE] Transcription error: {exc}")
        finally:
            if path:
                path.unlink(missing_ok=True)

    def _loop(self):
        while self.running:
            try:
                self._process(self.audio_queue.get(timeout=0.2))
            except queue.Empty:
                pass
            except Exception as exc:
                print(f"[VOICE] Processing error: {exc}")

    def start(self):
        if self.running:
            return
        print("=" * 58)
        print("TIMO REALTIME VOICE ENGINE")
        print("=" * 58)
        print(f"[VOICE] Input device: {self.device}")
        print("[VOICE] Listening continuously...")
        self.running = True
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()
        self.stream = sd.InputStream(device=self.device, channels=1,
                                     samplerate=self.samplerate,
                                     blocksize=self.blocksize,
                                     dtype="float32", callback=self._callback)
        self.stream.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=1)
        print("[VOICE] Realtime Voice Engine stopped.")


def demo_event_handler(event):
    if event["type"] == "USER_TRANSCRIPT":
        print("\n" + "=" * 58)
        print("YOU SAID:", event["text"])
        print("=" * 58 + "\n")


if __name__ == "__main__":
    engine = RealtimeVoiceEngine(on_event=demo_event_handler, device=1)
    try:
        engine.start()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[VOICE] Ctrl+C received")
    finally:
        engine.stop()
