"""
Timo Runtime
============
Unified runtime that connects:

    Camera -> VisionEngine -> TimoBrain -> Robot Actions

For this milestone, robot actions are printed by a temporary bridge.
Next, this same runtime will receive Realtime Voice + Barge-in and
the Android Robot SDK bridge.
"""

import sys
import time
import threading
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
VISION_DIR = PROJECT_DIR / "vision"

# vision_engine.py currently lives inside /vision and is not yet a package.
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

from timo_brain import TimoBrain
from realtime_voice import RealtimeVoiceEngine
from vision_engine import VisionEngine
from prime_engine import answer_query
from voice import VoicePlayer


class TimoRuntime:
    def __init__(self):
        self.running = False

        self.brain = TimoBrain(
            action_callback=self._handle_robot_action
        )

        self.vision = VisionEngine(
            on_event=self._handle_vision_event,
            show_window=True,
        )

        self.voice = RealtimeVoiceEngine(
            on_event=self._handle_voice_event,
            device=1,
        )

        self.voice_player = VoicePlayer(
            on_finished=self._handle_speech_finished,
        )

    def _handle_vision_event(self, event):
        """
        Vision knows what it sees.
        Brain decides what Timo should do.
        """
        print(f"[RUNTIME] Vision -> Brain: {event}")
        self.brain.submit_event(event)

    def _handle_voice_event(self, event):
        """
        Voice emits speech-start/end and transcript events.
        Speech-start goes to Brain immediately so it can trigger barge-in.
        """
        event_type = event.get("type")

        if event_type == "USER_SPEECH_STARTED":
            if self.voice_player.is_speaking:
                print("[RUNTIME] Barge-in -> stopping Timo speech immediately")
                self.voice_player.stop()

            print(f"[RUNTIME] Voice -> Brain (barge-in): {event}")
            self.brain.submit_event(event)

        elif event_type == "USER_TRANSCRIPT":
            text = (event.get("text") or "").strip()
            print(f"[RUNTIME] Voice transcript: {text}")

            if not text:
                return

            normalized = (
                text.replace("ي", "ی")
                    .replace("ك", "ک")
                    .replace("ۀ", "ه")
                    .replace("‌", " ")
            )

            stop_words = ("وایسا", "بایست", "توقف", "متوقف شو", "صبر کن")
            khodivzad_names = ("خدیوزاد", "خديوزاد", "خدی و زاد")

            if any(word in normalized for word in stop_words):
                command = {
                    "type": "USER_COMMAND",
                    "intent": "STOP",
                    "text": text,
                }
                print(f"[RUNTIME] Intent -> Brain: {command}")
                self.brain.submit_event(command)
                return

            wants_navigation = any(
                word in normalized
                for word in ("برو", "حرکت کن", "ببر", "بریم", "بیا بریم")
            )

            if wants_navigation and any(name in normalized for name in khodivzad_names):
                command = {
                    "type": "USER_COMMAND",
                    "intent": "NAVIGATE",
                    "target": "KHODIVZAD_ROOM",
                    "text": text,
                }
                print(f"[RUNTIME] Intent -> Brain: {command}")
                self.brain.submit_event(command)
                return

            print("[RUNTIME] General conversation -> AI")
            try:
                reply = answer_query(text)
            except Exception as exc:
                print(f"[RUNTIME] AI conversation error: {exc}")
                reply = "فعلاً در پاسخ‌گویی هوشمند مشکلی پیش آمده."

            if reply and reply != "__EXIT__":
                print(f"[RUNTIME] AI reply: {reply}")
                self._handle_robot_action({
                    "type": "SPEAK",
                    "payload": {
                        "text": reply,
                        "source": "AI_CONVERSATION",
                    },
                })

        elif event_type == "USER_SPEECH_ENDED":
            print(f"[RUNTIME] Voice speech ended: {event}")

    def _handle_speech_finished(self):
        """
        Playback callback. Kept lightweight so audio thread never blocks.
        """
        print("[RUNTIME] Timo speech finished")

    def _handle_robot_action(self, action):
        """
        Temporary action bridge.

        This is intentionally NOT controlling the real robot yet.
        Realtime speech and Android Robot SDK actions will be connected here.
        """
        action_type = action.get("type")
        payload = action.get("payload", {})

        print(
            f"[RUNTIME ACTION] {action_type} -> {payload}"
        )

        if action_type == "SPEAK":
            text = (payload.get("text") or "").strip()
            if text:
                print(f"[RUNTIME] Timo speaking: {text}")
                self.voice_player.speak(text)

        elif action_type == "WAVE":
            print(
                "[RUNTIME] Wave adapter pending "
                "(Android Robot SDK will replace this placeholder)"
            )

        elif action_type == "LISTEN":
            print(
                "[RUNTIME] Realtime microphone adapter pending"
            )

        elif action_type == "NAVIGATE":
            print(
                "[RUNTIME] Navigation adapter pending "
                "(Android Robot SDK will replace this placeholder)"
            )

        elif action_type == "STOP_SPEAKING":
            print("[RUNTIME] STOP_SPEAKING -> stopping audio")
            self.voice_player.stop()

        elif action_type == "STOP":
            print(
                "[RUNTIME] Robot stop adapter pending"
            )

    def start(self):
        if self.running:
            return

        self.running = True

        print("=" * 58)
        print("TIMO AI ROBOT ASSISTANT - UNIFIED RUNTIME")
        print("=" * 58)

        self.brain.start()

        print("[RUNTIME] Brain connected")

        self.voice.start()
        print("[RUNTIME] Realtime Voice connected")

        print("[RUNTIME] Vision connected")
        print("[RUNTIME] Starting camera...")
        print("")

        try:
            # Vision owns the main loop/window for this milestone.
            self.vision.run()

        except KeyboardInterrupt:
            print("\n[RUNTIME] Ctrl+C received")

        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return

        self.running = False

        print("")
        print("[RUNTIME] Shutting down Timo...")

        try:
            self.vision.stop()
        except Exception as exc:
            print(f"[RUNTIME] Vision stop warning: {exc}")

        try:
            self.voice.stop()
        except Exception as exc:
            print(f"[RUNTIME] Voice stop warning: {exc}")

        try:
            self.voice_player.stop()
        except Exception as exc:
            print(f"[RUNTIME] Voice player stop warning: {exc}")

        try:
            self.brain.stop()
        except Exception as exc:
            print(f"[RUNTIME] Brain stop warning: {exc}")

        print("[RUNTIME] Timo stopped safely")


if __name__ == "__main__":
    runtime = TimoRuntime()
    runtime.start()
