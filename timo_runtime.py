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
from vision_engine import VisionEngine


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

    def _handle_vision_event(self, event):
        """
        Vision knows what it sees.
        Brain decides what Timo should do.
        """
        print(f"[RUNTIME] Vision -> Brain: {event}")
        self.brain.submit_event(event)

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
            print(
                "[RUNTIME] Speech adapter pending "
                "(Realtime Voice will replace this placeholder)"
            )

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
            print(
                "[RUNTIME] Barge-in stop adapter pending"
            )

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
            self.brain.stop()
        except Exception as exc:
            print(f"[RUNTIME] Brain stop warning: {exc}")

        print("[RUNTIME] Timo stopped safely")


if __name__ == "__main__":
    runtime = TimoRuntime()
    runtime.start()
