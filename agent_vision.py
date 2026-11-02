"""Bridge existing YuNet/SFace recognition to the shared robot dialogue."""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib import request, error
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def publish(server, key, event):
    # فقط رویداد و شناسه و امتیاز ارسال می‌شوند؛ تصویر مرجع وارد درخواست سلام نمی‌شود.
    payload = {field: event[field] for field in ('type', 'name', 'confidence')}
    req = request.Request(server + '/api/agent/host/recognition',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json', 'X-Agent-Key': key},
                          method='POST')
    with request.urlopen(req, timeout=4) as response:
        return json.load(response)


def main(argv=None):
    parser = argparse.ArgumentParser(description='تشخیص چهره برای ایجنت مشترک تیمو')
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    parser.add_argument('--adb', default=os.getenv('TIMO_ADB_PATH') or shutil.which('adb'))
    parser.add_argument('--device', default=os.getenv('TIMO_ADB_DEVICE'))
    parser.add_argument('--no-window', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    server = args.server.rstrip('/')
    parsed = urlsplit(server)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password or parsed.path:
        parser.error('این برنامه کنار سرور پایتون اجرا می‌شود؛ آدرس HTTP محلی وارد کنید.')
    key_path = ROOT / 'data' / 'agent-admin.key'
    if not key_path.exists():
        parser.error('ابتدا Agent_Setup.bat را اجرا کنید؛ کلید مدیر پیدا نشد.')
    key = key_path.read_text(encoding='utf-8').strip()
    sys.path.insert(0, str(ROOT / 'vision'))
    try:
        import vision_engine as vision
        from agent_host import load_people
        import cv2
    except ImportError as exc:
        print(f'وابستگی تشخیص چهره موجود نیست: {exc.name}. برنامه را با محیط قبلی Vision اجرا کنید.')
        return 1
    try:
        people = load_people()
    except (ValueError, OSError):
        parser.error('فایل data/agent-people.json معتبر نیست؛ نام و متن سلام افراد را بررسی کنید.')
    if not people:
        print('هیچ فردی در data/agent-people.json ثبت نشده است.')
        return 1
    # Retry visible recognition frequently; the broker owns the greeting cooldown.
    vision.EVENT_COOLDOWN = 2
    if args.adb:
        vision.ADB_PATH = str(Path(args.adb).resolve())
    vision.KNOWN_FACE_DIR = str(ROOT / 'vision' / 'known_faces')

    class AgentVision(vision.VisionEngine):
        def _load_known_faces(self):
            result = {}
            for identity in people:
                folder = ROOT / 'vision' / 'known_faces' / identity
                features = []
                for image_path in sorted(folder.glob('*')):
                    if image_path.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                        continue
                    image = cv2.imread(str(image_path))
                    if image is not None:
                        feature = self._get_face_feature(image)
                        if feature is not None:
                            features.append(feature)
                if features:
                    result[identity] = features
                    print(f'{identity}: {len(features)} reference faces loaded')
            if not result:
                raise RuntimeError('تصویر مرجع قابل استفاده برای افراد ثبت‌شده پیدا نشد.')
            return result

        def _recognize(self, frame):
            height, width = frame.shape[:2]
            self.detector.setInputSize((width, height))
            _, faces = self.detector.detect(frame)
            if faces is None:
                return []
            results = []
            for face in faces:
                aligned = self.recognizer.alignCrop(frame, face)
                feature = self.recognizer.feature(aligned)
                scores = sorted(((max(float(self.recognizer.match(ref, feature, cv2.FaceRecognizerSF_FR_COSINE))
                                      for ref in refs), identity)
                                 for identity, refs in self.known_features.items()), reverse=True)
                score, identity = scores[0]
                # Do not assign an identity if two enrolled people match similarly.
                # علاوه بر حداقل شباهت، فاصله با نفر دوم بررسی می‌شود تا تطبیق مبهم کنار گذاشته شود.
                confident = score >= vision.RECOGNITION_THRESHOLD and (len(scores) == 1 or score - scores[1][0] >= 0.05)
                if confident:
                    self._emit('PERSON_RECOGNIZED', identity, min(1.0, score))
                else:
                    identity = 'Unknown'
                x, y, w, h = map(int, face[:4])
                results.append((x, y, w, h, identity, score))
            return results

        def _start_camera(self):
            import subprocess
            command = [vision.ADB_PATH]
            if args.device:
                command.extend(['-s', args.device])
            command.extend(['exec-out', 'v4l2-ctl', '-d', '/dev/video20',
                            '--set-fmt-video=width=640,height=480,pixelformat=MJPG',
                            '--stream-mmap=3', '--stream-count=0', '--stream-to=-'])
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0)

    last_error = [0.0]
    def on_event(event):
        try:
            result = publish(server, key, event)
            if result.get('status') == 'queued':
                print('Greeting queued for the paired robot.')
        except (OSError, error.URLError, ValueError):
            if time.monotonic() - last_error[0] >= 15:
                print('ارتباط با سرور ایجنت برقرار نشد؛ سرور و کلید مدیر را بررسی کنید.')
                last_error[0] = time.monotonic()
    try:
        engine = AgentVision(on_event=on_event, show_window=not args.no_window)
        if args.check:
            req = request.Request(server + '/api/agent/state', headers={'X-Agent-Key': key})
            with request.urlopen(req, timeout=4) as response:
                response.read()
            print('PASS: models, reference faces, ADB path and authenticated server access.')
            print('This check does not open the camera or verify physical recognition.')
            return 0
        print('صفحهٔ گفتگو روی ربات: فعال‌کردن سلام شخصی را بزنید.')
        print('برنامه‌های قدیمی تشخیص چهره که صدا پخش می‌کنند را هم‌زمان اجرا نکنید.')
        engine.run()
        return 0
    except (OSError, RuntimeError, ValueError, cv2.error):
        print('اجرای Vision ناموفق بود؛ مسیر ADB، مدل‌ها، تصاویر مرجع و اتصال ربات را بررسی کنید.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
