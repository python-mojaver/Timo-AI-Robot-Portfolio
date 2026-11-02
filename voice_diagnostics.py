"""Inspect the last received WAV without calling a model or the robot."""
import array
import math
import sys
import wave
from pathlib import Path


def main():
    path = Path(__file__).resolve().parent / 'data' / 'debug_audio' / 'debug_last.wav'
    if not path.exists():
        print('No recorded audio yet. Record one sentence in the chat first.')
        return 1
    try:
        with wave.open(str(path), 'rb') as audio:
            rate, channels, width, frames = audio.getframerate(), audio.getnchannels(), audio.getsampwidth(), audio.getnframes()
            raw = audio.readframes(frames)
        print(f'Audio: {path}')
        print(f'Duration: {frames/rate:.2f} s | Sample rate: {rate} Hz | Channels: {channels} | Bits: {width*8}')
        if width == 2 and raw:
            values = array.array('h', raw)
            if sys.byteorder != 'little':
                values.byteswap()
            rms = math.sqrt(sum(float(x)*x for x in values)/len(values))/32768
            peak = max(abs(x) for x in values)/32768
            clipped = sum(abs(x) >= 32760 for x in values)/len(values)*100
            print(f'RMS: {rms:.5f} | Peak: {peak:.5f} | Near-clipping samples: {clipped:.2f}%')
        print('Listen to this exact file and compare its words with the displayed transcript.')
        return 0
    except (wave.Error, EOFError) as exc:
        print('Last upload is not a PCM WAV (an older/browser/native recording may use another format).')
        print(f'Audio file: {path} | {type(exc).__name__}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
