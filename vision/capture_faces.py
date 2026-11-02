import shutil
import os
import cv2
import subprocess
import numpy as np
import os

ADB_PATH = os.getenv("TIMO_ADB_PATH") or shutil.which("adb") or "adb"
MODEL_PATH = "face_detection_yunet_2023mar.onnx"

SAVE_DIR = r"known_faces\Mojaver"

os.makedirs(SAVE_DIR, exist_ok=True)

detector = cv2.FaceDetectorYN.create(
    MODEL_PATH,
    "",
    (640, 480),
    score_threshold=0.7,
    nms_threshold=0.3,
    top_k=5000
)

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

photo_number = 1

print("Timo Face Capture started")
print("Press S to save face")
print("Press Q to quit")

while True:

    chunk = process.stdout.read(16384)

    if not chunk:
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

        height, width = frame.shape[:2]

        detector.setInputSize(
            (width, height)
        )

        _, faces = detector.detect(frame)

        face_crop = None

        if faces is not None:

            face = faces[0]

            x = int(face[0])
            y = int(face[1])
            w = int(face[2])
            h = int(face[3])

            x = max(0, x)
            y = max(0, y)

            x2 = min(width, x + w)
            y2 = min(height, y + h)

            face_crop = frame[y:y2, x:x2]

            cv2.rectangle(
                frame,
                (x, y),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                "Mojaver",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        cv2.imshow(
            "Timo Face Capture",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):

            if face_crop is not None and face_crop.size > 0:

                filename = os.path.join(
                    SAVE_DIR,
                    f"face_{photo_number:02d}.jpg"
                )

                cv2.imwrite(
                    filename,
                    face_crop
                )

                print(
                    f"Saved: {filename}"
                )

                photo_number += 1

            else:

                print(
                    "No face detected"
                )

        elif key == ord("q"):

            process.terminate()

            cv2.destroyAllWindows()

            raise SystemExit

process.terminate()

cv2.destroyAllWindows()
