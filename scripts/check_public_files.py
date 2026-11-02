"""Check tracked public content (or an unpacked package) without echoing secrets."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {"data", "known_faces", "generated_audio", "models", ".venv", "venv", "node_modules"}
PRIVATE_SUFFIXES = {".db", ".sqlite3", ".xlsx", ".key", ".pem", ".onnx", ".bin", ".mp3", ".wav"}
TOKEN = re.compile(r"(?:gsk_|AIza|sk-proj-|ghp_|github_pat_)[A-Za-z0-9_-]{15,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")

def main():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode == 0:
        paths = [ROOT / name for name in result.stdout.decode().split("\0") if name]
    else:
        paths = [p for p in ROOT.rglob("*") if p.is_file() and not any(x in {".git", ".venv", "node_modules", "__pycache__"} for x in p.relative_to(ROOT).parts)]
    errors = []
    for path in paths:
        relative = path.relative_to(ROOT)
        if (any(x in PRIVATE_DIRS or x.endswith("-backups") for x in relative.parts)
                or path.suffix in PRIVATE_SUFFIXES or path.name == ".env"
                or path.name.startswith(".env.") and path.name != ".env.example"):
            errors.append(str(relative) + ": private/runtime file")
        elif path.is_file() and path.stat().st_size < 2_000_000:
            if TOKEN.search(path.read_text(encoding="utf-8", errors="ignore")):
                errors.append(str(relative) + ": possible credential")
    for error in errors:
        print(error)
    print("Public-file check:", "FAILED" if errors else "OK")
    return bool(errors)

if __name__ == "__main__":
    raise SystemExit(main())
