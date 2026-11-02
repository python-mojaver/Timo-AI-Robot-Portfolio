import shutil
import os
import cv2
import subprocess
import numpy as np
import os
import glob
import time
from dataclasses import dataclass, asdict
from typing import Callable, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.getenv("TIMO_ADB_PATH") or shutil.which("adb") or "adb"

DETECTION_MODEL = os.path.join(BASE_DIR, "models", "face_detection_yunet_2023mar.onnx")
RECOGNITION_MODEL = os.path.join(BASE_DIR, "models", "face_recognition_sface_2021dec.onnx")
KNOWN_FACE_DIR = os.path.join(BASE_DIR, "known_faces", "Mojaver")

PROCESS_EVERY_N_FRAMES = 5
RECOGNITION_THRESHOLD = 0.40

# The Vision Engine does not decide when Timo should greet.
# It only reports recognition events to the Brain.
EVENT_COOLDOWN = 10 * 60


@dataclass
class VisionEvent:
    type: str
    name: str
    confidence: float
    timestamp: float

    def to_dict(self):
        return asdict(self)


class VisionEngine:
    def __init__(
        self,
        on_event: Optional[Callable[[dict], None]] = None,
        show_window: bool = True,
    ):
        self.on_event = on_event
        self.show_window = show_window
        self.running = False
        self.process = None
        self.buffer = bytearray()
        self.frame_counter = 0
        self.last_faces = []
        self.last_event_time = {}

        self._validate_paths()

        self.detector = cv2.FaceDetectorYN.create(
            DETECTION_MODEL,
            "",
            (640, 480),
            score_threshold=0.7,
            nms_threshold=0.3,
            top_k=5000,
        )

        self.recognizer = cv2.FaceRecognizerSF.create(
            RECOGNITION_MODEL,
            "",
        )

        print("Vision AI models loaded successfully")

        self.known_features = self._load_known_faces()

    def _validate_paths(self):
        required = [
            ("ADB", ADB_PATH),
            ("YuNet model", DETECTION_MODEL),
            ("SFace model", RECOGNITION_MODEL),
            ("Known faces", KNOWN_FACE_DIR),
        ]

        missing = [
            f"{label}: {path}"
            for label, path in required
            if not os.path.exists(path)
        ]

        if missing:
            raise FileNotFoundError(
                "Missing required Vision files:\n" + "\n".join(missing)
            )

    def _get_face_feature(self, image):
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(image)

        if faces is None:
            return None

        face = faces[0]
        aligned_face = self.recognizer.alignCrop(image, face)
        return self.recognizer.feature(aligned_face)

    def _load_known_faces(self):
        known_features = []
        image_files = glob.glob(os.path.join(KNOWN_FACE_DIR, "*.jpg"))

        print(f"Found {len(image_files)} reference images")

        for image_path in image_files:
            image = cv2.imread(image_path)

            if image is None:
                continue

            feature = self._get_face_feature(image)

            if feature is not None:
                known_features.append(feature)
                print("Loaded:", os.path.basename(image_path))

        if not known_features:
            raise RuntimeError("No Mojaver reference faces were loaded")

        print(f"{len(known_features)} Mojaver faces loaded")
        return known_features

    def _emit(self, event_type, name, confidence):
        now = time.time()
        key = (event_type, name)
        last_time = self.last_event_time.get(key, 0.0)

        # Do not flood the Brain with the same recognition every frame.
        if now - last_time < EVENT_COOLDOWN:
            return

        self.last_event_time[key] = now

        event = VisionEvent(
            type=event_type,
            name=name,
            confidence=float(confidence),
            timestamp=now,
        ).to_dict()

        print(
            f"[VISION EVENT] {event['type']} | "
            f"name={event['name']} | "
            f"confidence={event['confidence']:.3f}"
        )

        if self.on_event:
            self.on_event(event)

    def _recognize(self, frame):
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)

        results = []

        if faces is None:
            return results

        for face in faces:
            aligned_face = self.recognizer.alignCrop(frame, face)
            feature = self.recognizer.feature(aligned_face)

            best_score = 0.0

            for known_feature in self.known_features:
                score = self.recognizer.match(
                    known_feature,
                    feature,
                    cv2.FaceRecognizerSF_FR_COSINE,
                )
                best_score = max(best_score, score)

            if best_score >= RECOGNITION_THRESHOLD:
                name = "Mojaver"
                self._emit("PERSON_RECOGNIZED", name, best_score)
            else:
                name = "Unknown"

            x, y, w, h = map(int, face[:4])
            results.append((x, y, w, h, name, best_score))

        return results

    def _start_camera(self):
        command = [
            ADB_PATH,
            "exec-out",
            "v4l2-ctl",
            "-d",
            "/dev/video20",
            "--set-fmt-video=width=640,height=480,pixelformat=MJPG",
            "--stream-mmap=3",
            "--stream-count=0",
            "--stream-to=-",
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

    def stop(self):
        self.running = False

        if self.process and self.process.poll() is None:
            self.process.terminate()

        cv2.destroyAllWindows()

    def run(self):
        self._start_camera()
        self.running = True

        print("")
        print("Timo Vision Engine started")
        print("Vision now emits events; it does not speak by itself.")
        print("Press Q to quit")
        print("")

        try:
            while self.running:
                chunk = self.process.stdout.read(65536)

                if not chunk:
                    print("Camera stream stopped")
                    break

                self.buffer.extend(chunk)

                if len(self.buffer) > 2_000_000:
                    last_start = self.buffer.rfind(b"\xff\xd8")
                    if last_start != -1:
                        self.buffer = self.buffer[last_start:]

                while True:
                    start = self.buffer.find(b"\xff\xd8")
                    if start == -1:
                        break

                    end = self.buffer.find(b"\xff\xd9", start + 2)
                    if end == -1:
                        break

                    jpg = bytes(self.buffer[start:end + 2])
                    del self.buffer[:end + 2]

                    image_array = np.frombuffer(jpg, dtype=np.uint8)
                    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

                    if frame is None:
                        continue

                    self.frame_counter += 1

                    if self.frame_counter % PROCESS_EVERY_N_FRAMES == 0:
                        self.last_faces = self._recognize(frame)

                    if self.show_window:
                        for x, y, w, h, name, score in self.last_faces:
                            cv2.rectangle(
                                frame,
                                (x, y),
                                (x + w, y + h),
                                (0, 255, 0),
                                2,
                            )
                            cv2.putText(
                                frame,
                                f"{name} {score:.2f}",
                                (x, max(25, y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )

                        cv2.imshow("Timo Vision Engine", frame)

                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            self.stop()
                            return

        except KeyboardInterrupt:
            print("\nVision Engine interrupted")
        finally:
            self.stop()


def print_event(event):
    print("BRAIN RECEIVED:", event)


if __name__ == "__main__":
    engine = VisionEngine(on_event=print_event, show_window=True)
    engine.run()
