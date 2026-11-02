import shutil
import os
import cv2
import subprocess
import numpy as np

ADB_PATH = os.getenv("TIMO_ADB_PATH") or shutil.which("adb") or "adb"

command = [
    ADB_PATH,
    "exec-out",
    "v4l2-ctl",
    "-d",
    "/dev/video20",
    "--set-fmt-video=width=640,height=480,pixelformat=MJPG",
    "--stream-mmap=3",
    "--stream-count=0",
    "--stream-to=-"
]

process = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL
)

buffer = bytearray()

print("Timo live camera started")

while True:

    chunk = process.stdout.read(16384)

    if not chunk:
        print("Camera stream stopped")
        break

    buffer.extend(chunk)

    while True:

        start = buffer.find(b"\xff\xd8")

        if start == -1:
            break

        end = buffer.find(b"\xff\xd9", start + 2)

        if end == -1:
            break

        jpg = bytes(buffer[start:end + 2])

        del buffer[:end + 2]

        image_array = np.frombuffer(
            jpg,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            continue

        cv2.imshow(
            "Timo Live Camera",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            process.terminate()
            cv2.destroyAllWindows()
            raise SystemExit


process.terminate()
cv2.destroyAllWindows()
