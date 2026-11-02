import shutil
import os
import cv2
import subprocess
import numpy as np
import os
import glob
import time


ADB_PATH = os.getenv("TIMO_ADB_PATH") or shutil.which("adb") or "adb"

DETECTION_MODEL = "face_detection_yunet_2023mar.onnx"
RECOGNITION_MODEL = "face_recognition_sface_2021dec.onnx"

KNOWN_FACE_DIR = r"known_faces\Mojaver"

# فایل‌های صوتی موجود روی خود Timo
TIMO_GREETING_FILE = "/sdcard/timo_greeting.mp3"
TIMO_HOW_ARE_YOU_FILE = "/sdcard/timo_how_are_you.mp3"

# هر چند فریم یکبار AI اجرا شود
PROCESS_EVERY_N_FRAMES = 5

# آستانه تشخیص هویت
RECOGNITION_THRESHOLD = 0.40

# اگر این مدت آقای مجاور دیده نشود،
# سیستم فرض می‌کند از جلوی دوربین خارج شده
FACE_LOST_TIMEOUT = 3.0


# =========================
# AI Models
# =========================

detector = cv2.FaceDetectorYN.create(
    DETECTION_MODEL,
    "",
    (640, 480),
    score_threshold=0.7,
    nms_threshold=0.3,
    top_k=5000
)

recognizer = cv2.FaceRecognizerSF.create(
    RECOGNITION_MODEL,
    ""
)

print("AI models loaded successfully")


# ======================================
# Timo Greeting State
# ======================================

# آیا آقای مجاور در حال حاضر جلوی دوربین است؟
mojaver_present = False

# آخرین زمانی که آقای مجاور دیده شده
last_mojaver_seen_time = 0.0


# ======================================
# Audio Functions
# ======================================

def open_timo_audio(audio_file):
    """
    Open and play an audio file on Timo.
    """

    subprocess.Popen(
        [
            ADB_PATH,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            f"file://{audio_file}",
            "-t",
            "audio/mpeg"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def go_timo_home():
    """
    Return Timo screen to Home.
    """

    subprocess.Popen(
        [
            ADB_PATH,
            "shell",
            "input",
            "keyevent",
            "KEYCODE_HOME"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def play_greeting_sequence():
    """
    Sequence:

    1. سلام آقای مجاور
    2. حالتون خوبه آقای مجاور؟
    3. Return to Home
    """

    print("")
    print("TIMO conversation started")
    print("")

    try:

        # =========================
        # First sentence
        # =========================

        print("TIMO -> سلام آقای مجاور")

        open_timo_audio(
            TIMO_GREETING_FILE
        )

        # فرصت برای کامل شدن جمله اول
        time.sleep(2.0)


        # =========================
        # Second sentence
        # =========================

        print("TIMO -> حالتون خوبه آقای مجاور؟")

        open_timo_audio(
            TIMO_HOW_ARE_YOU_FILE
        )

        # فرصت برای کامل شدن جمله دوم
        time.sleep(2.5)


        # =========================
        # Return Home
        # =========================

        go_timo_home()

        print("")
        print("TIMO is now waiting for Mojaver response...")
        print("")

    except Exception as e:

        print(
            "ERROR playing conversation:",
            e
        )


# ======================================
# Greeting Trigger
# ======================================

def say_hello_to_mojaver():

    print("")
    print("================================")
    print("Mr. Mojaver recognized")
    print("Starting TIMO conversation")
    print("================================")
    print("")

    play_greeting_sequence()

    # مرحله بعدی:
    #
    # listen_to_mojaver()
    #
    # سپس:
    #
    # start_ai_chat()


# ======================================
# Face Feature
# ======================================

def get_face_feature(image):

    height, width = image.shape[:2]

    detector.setInputSize(
        (width, height)
    )

    _, faces = detector.detect(
        image
    )

    if faces is None:
        return None

    face = faces[0]

    aligned_face = recognizer.alignCrop(
        image,
        face
    )

    feature = recognizer.feature(
        aligned_face
    )

    return feature


# =========================
# Load known faces
# =========================

known_features = []

image_files = glob.glob(
    os.path.join(
        KNOWN_FACE_DIR,
        "*.jpg"
    )
)

print(
    f"Found {len(image_files)} reference images"
)

for image_path in image_files:

    image = cv2.imread(
        image_path
    )

    if image is None:
        continue

    feature = get_face_feature(
        image
    )

    if feature is not None:

        known_features.append(
            feature
        )

        print(
            "Loaded:",
            os.path.basename(image_path)
        )


if len(known_features) == 0:

    print(
        "ERROR: No reference faces loaded"
    )

    raise SystemExit


print(
    f"{len(known_features)} Mojaver faces loaded"
)


# =========================
# Start camera
# =========================

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
    stderr=subprocess.DEVNULL,
    bufsize=0
)

buffer = bytearray()

print("")
print(
    "Timo Face Recognition + Conversation started"
)
print(
    "Press Q to quit"
)


frame_counter = 0
last_faces = []


# =========================
# Main camera loop
# =========================

while True:

    chunk = process.stdout.read(
        65536
    )

    if not chunk:

        print(
            "Camera stream stopped"
        )

        break

    buffer.extend(
        chunk
    )

    # جلوگیری از بزرگ شدن بیش از حد buffer
    if len(buffer) > 2_000_000:

        last_start = buffer.rfind(
            b"\xff\xd8"
        )

        if last_start != -1:

            buffer = buffer[
                last_start:
            ]


    while True:

        start = buffer.find(
            b"\xff\xd8"
        )

        if start == -1:
            break

        end = buffer.find(
            b"\xff\xd9",
            start + 2
        )

        if end == -1:
            break

        jpg = bytes(
            buffer[
                start:end + 2
            ]
        )

        del buffer[
            :end + 2
        ]

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

        frame_counter += 1

        height, width = frame.shape[:2]


        # =========================
        # Face Recognition
        # =========================

        if frame_counter % PROCESS_EVERY_N_FRAMES == 0:

            detector.setInputSize(
                (width, height)
            )

            _, faces = detector.detect(
                frame
            )

            last_faces = []


            if faces is not None:

                for face in faces:

                    aligned_face = recognizer.alignCrop(
                        frame,
                        face
                    )

                    feature = recognizer.feature(
                        aligned_face
                    )

                    best_score = 0.0


                    # =========================
                    # Compare with known faces
                    # =========================

                    for known_feature in known_features:

                        score = recognizer.match(
                            known_feature,
                            feature,
                            cv2.FaceRecognizerSF_FR_COSINE
                        )

                        if score > best_score:

                            best_score = score


                    # =============================
                    # Mojaver recognized
                    # =============================

                    if best_score >= RECOGNITION_THRESHOLD:

                        name = "Mojaver"

                        # هر بار که واقعاً دیده می‌شود
                        # زمان آخرین مشاهده تازه شود
                        last_mojaver_seen_time = time.time()


                        # فقط وقتی تازه وارد کادر شده
                        # مکالمه شروع شود
                        if not mojaver_present:

                            mojaver_present = True

                            say_hello_to_mojaver()

                            # چون پخش دو فایل صوتی چند ثانیه
                            # حلقه دوربین را متوقف می‌کند،
                            # زمان را دوباره تازه می‌کنیم
                            last_mojaver_seen_time = time.time()


                    else:

                        name = "Unknown"


                    # =========================
                    # Face Coordinates
                    # =========================

                    x = int(
                        face[0]
                    )

                    y = int(
                        face[1]
                    )

                    w = int(
                        face[2]
                    )

                    h = int(
                        face[3]
                    )


                    # ذخیره نتیجه برای نمایش روی تصویر
                    last_faces.append(
                        (
                            x,
                            y,
                            w,
                            h,
                            name,
                            best_score
                        )
                    )


            # =========================
            # Check if Mojaver left
            # =========================

            if mojaver_present:

                time_since_last_seen = (
                    time.time()
                    - last_mojaver_seen_time
                )

                # اگر حداقل 3 ثانیه دیده نشد،
                # سیستم دوباره آماده سلام شود
                if time_since_last_seen > FACE_LOST_TIMEOUT:

                    mojaver_present = False

                    print("")
                    print(
                        "Mojaver left camera view"
                    )
                    print(
                        "Greeting system re-armed"
                    )
                    print("")


        # =========================
        # Draw Recognition Result
        # =========================

        for (
            x,
            y,
            w,
            h,
            name,
            score
        ) in last_faces:

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"{name} {score:.2f}",
                (
                    x,
                    max(
                        25,
                        y - 10
                    )
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


        # =========================
        # Show Camera
        # =========================

        cv2.imshow(
            "Timo Face Recognition + Conversation",
            frame
        )


        # =========================
        # Quit
        # =========================

        if cv2.waitKey(1) & 0xFF == ord("q"):

            process.terminate()

            cv2.destroyAllWindows()

            raise SystemExit


# =========================
# Cleanup
# =========================

process.terminate()

cv2.destroyAllWindows()
