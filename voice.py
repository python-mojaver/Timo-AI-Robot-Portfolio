import asyncio
import hashlib
import os
import threading
from pathlib import Path

import edge_tts


VOICE = "fa-IR-FaridNeural"

AUDIO_DIR = str(Path(__file__).resolve().parent / "generated_audio")

os.makedirs(
    AUDIO_DIR,
    exist_ok=True
)


async def _generate_voice(
    text: str,
    output_path: str
):

    communicate = edge_tts.Communicate(

        text=text,

        voice=VOICE,

        # کمی سریع‌تر و مناسب مکالمه
        rate="+8%",

        volume="+0%"
    )

    await communicate.save(
        output_path
    )


def generate_voice(text: str):

    text = (
        text or ""
    ).strip()

    if not text:
        return None


    # برای یک متن ثابت،
    # همیشه همان فایل استفاده شود
    text_hash = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()


    filename = (
        f"voice_{text_hash}.mp3"
    )

    output_path = os.path.join(
        AUDIO_DIR,
        filename
    )


    # اگر قبلاً تولید شده
    if (
        os.path.exists(output_path)
        and
        os.path.getsize(output_path) > 0
    ):

        print(
            "Voice cache:",
            output_path
        )

        return output_path


    try:

        print(
            "Generating voice..."
        )


        asyncio.run(

            _generate_voice(
                text,
                output_path
            )
        )


        if (
            not os.path.exists(
                output_path
            )
            or
            os.path.getsize(
                output_path
            ) == 0
        ):

            return None


        print(
            "Voice generated:",
            output_path
        )


        return output_path


    except Exception as error:

        print(
            "Voice generation error:",
            error
        )

        try:

            if os.path.exists(
                output_path
            ):
                os.remove(
                    output_path
                )

        except Exception:
            pass


        return None


class VoicePlayer:
    """
    Cancellable speech player for Timo.

    - Reuses generate_voice() and its MP3 cache.
    - Playback runs in a background thread, so Vision/Mic keep running.
    - stop() immediately stops current playback for barge-in.
    """

    def __init__(self, on_finished=None):
        self.on_finished = on_finished
        self._lock = threading.RLock()
        self._thread = None
        self._stop_requested = threading.Event()
        self._pygame = None

    def _ensure_audio(self):
        if self._pygame is not None:
            return True

        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
            return True
        except Exception as error:
            print("Voice playback init error:", error)
            return False

    def speak(self, text: str):
        text = (text or "").strip()
        if not text:
            return False

        # A new response replaces anything currently being spoken.
        self.stop()
        self._stop_requested.clear()

        self._thread = threading.Thread(
            target=self._speak_worker,
            args=(text,),
            daemon=True,
            name="TimoVoicePlayer",
        )
        self._thread.start()
        return True

    def _speak_worker(self, text: str):
        path = generate_voice(text)
        if not path or self._stop_requested.is_set():
            return

        if not self._ensure_audio():
            return

        try:
            with self._lock:
                self._pygame.mixer.music.load(path)
                self._pygame.mixer.music.play()

            print("[VOICE OUT] Speaking:", text)

            while not self._stop_requested.wait(0.03):
                with self._lock:
                    if not self._pygame.mixer.music.get_busy():
                        break

            interrupted = self._stop_requested.is_set()

            if interrupted:
                print("[VOICE OUT] Speech interrupted")
            else:
                print("[VOICE OUT] Speech finished")
                if self.on_finished:
                    try:
                        self.on_finished()
                    except Exception as error:
                        print("Voice finished callback error:", error)

        except Exception as error:
            print("Voice playback error:", error)

    def stop(self):
        self._stop_requested.set()

        if self._pygame is not None:
            try:
                with self._lock:
                    self._pygame.mixer.music.stop()
            except Exception:
                pass

    @property
    def is_speaking(self):
        if self._pygame is None:
            return False
        try:
            with self._lock:
                return bool(self._pygame.mixer.music.get_busy())
        except Exception:
            return False


if __name__ == "__main__":

    path = generate_voice(
        "سلام، من دستیار فروش هوشمند هستم."
    )

    print(
        "Generated:",
        path
    )