"""Durable, operator-curated knowledge and destinations. No executable user code."""
from contextlib import contextmanager
import json
import math
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def normalize(value):
    value = str(value).lower().replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def clean(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{label}: مقدار خالی یا بیش از {limit} نویسه است.")
    return value.strip()


class AgentStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("TIMO_AGENT_DB") or BASE_DIR / "data" / "agent.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories(
                  id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                  kind TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS rooms(
                  id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
                  aliases TEXT NOT NULL, map_name TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL,
                  z REAL NOT NULL, rotation REAL NOT NULL, enabled INTEGER NOT NULL,
                  updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS skills(
                  id INTEGER PRIMARY KEY, name TEXT NOT NULL, triggers TEXT NOT NULL,
                  kind TEXT NOT NULL, reply TEXT NOT NULL, room_id INTEGER,
                  enabled INTEGER NOT NULL, updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals(
                  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, kind TEXT NOT NULL,
                  payload TEXT NOT NULL, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            if not db.execute("SELECT 1 FROM meta WHERE key='initial-room'").fetchone():
                # Inert public example: an operator must supply and verify the map and pose.
                db.execute("""INSERT INTO rooms(name,name_key,aliases,map_name,x,y,z,rotation,enabled,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?)""", ("اتاق نمونه", normalize("اتاق نمونه"),
                    json.dumps(["نمونه"], ensure_ascii=False),
                    "", 0.0, 0.0, 0.0, 0.0, 0, time.time()))
                db.execute("INSERT INTO meta VALUES('initial-room','1')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, table):
        if table not in {"memories", "rooms", "skills"}:
            raise ValueError("Unknown table")
        with self.connect() as db:
            rows = [dict(x) for x in db.execute(f"SELECT * FROM {table} ORDER BY id DESC")]
        for row in rows:
            for name in ("aliases", "triggers"):
                if name in row:
                    row[name] = json.loads(row[name])
            if "enabled" in row:
                row["enabled"] = bool(row["enabled"])
        return rows

    def _write(self, table, values, item_id=None):
        with self.connect() as db:
            if item_id is not None:
                query = f"UPDATE {table} SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?"
                if db.execute(query, [*values.values(), int(item_id)]).rowcount != 1:
                    raise ValueError("این مورد پیدا نشد؛ صفحه را تازه کنید.")
                return int(item_id)
            return db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})",
                              list(values.values())).lastrowid

    def save_memory(self, data, item_id=None):
        kind = data.get("kind", "fact")
        if kind not in {"fact", "qa"}:
            raise ValueError("نوع حافظه نامعتبر است.")
        title = clean(data.get("title"), 200, "عنوان/سؤال")
        if any(normalize(row["title"]) == normalize(title) and row["id"] != item_id for row in self.rows("memories")):
            raise ValueError("این عنوان قبلاً ثبت شده؛ مورد قبلی را ویرایش کنید.")
        values = {"title": title,
                  "body": clean(data.get("body"), 8000, "اطلاعات/پاسخ"), "kind": kind,
                  "updated_at": time.time()}
        if item_id is None:
            values["created_at"] = time.time()
        return self._write("memories", values, item_id)

    @staticmethod
    def _aliases(value):
        if not isinstance(value, list) or len(value) > 20:
            raise ValueError("حداکثر ۲۰ نام جایگزین مجاز است.")
        aliases = [clean(x, 120, "نام جایگزین") for x in value]
        if any(not normalize(x) for x in aliases):
            raise ValueError("نام جایگزین معتبر نیست.")
        return list(dict.fromkeys(aliases))

    def save_room(self, data, item_id=None):
        if not isinstance(data.get("enabled", False), bool):
            raise ValueError("فعال‌بودن مقصد باید درست/نادرست باشد.")
        name = clean(data.get("name"), 120, "نام اتاق")
        if not normalize(name):
            raise ValueError("نام اتاق معتبر نیست.")
        aliases = self._aliases(data.get("aliases", []))
        map_name = str(data.get("map_name", "")).strip()
        if len(map_name) > 120 or (data.get("enabled") and not map_name):
            raise ValueError("برای فعال‌کردن مقصد، نام نقشه لازم است.")
        pose = {}
        for key in ("x", "y", "z", "rotation"):
            raw = data.get(key)
            if isinstance(raw, bool):
                raise ValueError("مختصات باید عدد باشد.")
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"مختصات {key} باید عدد باشد.") from None
            if not math.isfinite(number) or abs(number) > (math.pi * 2 if key == "rotation" else 10000):
                raise ValueError("مختصات نامعتبر یا rotation خارج از بازه رادیان است.")
            pose[key] = number
        proposed_keys = {normalize(name), *(normalize(a) for a in aliases)}
        for room in self.rows("rooms"):
            if room["id"] != item_id and proposed_keys & {normalize(room["name"]), *(normalize(a) for a in room["aliases"])}:
                raise ValueError("این نام یا نام جایگزین متعلق به اتاق دیگری است.")
        return self._write("rooms", {"name": name, "name_key": normalize(name),
            "aliases": json.dumps(aliases, ensure_ascii=False), "map_name": map_name, **pose,
            "enabled": int(bool(data.get("enabled"))), "updated_at": time.time()}, item_id)

    def save_skill(self, data, item_id=None):
        if not isinstance(data.get("enabled", True), bool):
            raise ValueError("فعال‌بودن قابلیت باید درست/نادرست باشد.")
        kind = data.get("kind")
        if kind not in {"reply", "navigate"}:
            raise ValueError("قابلیت فقط پاسخ متنی یا رفتن به مقصد ثبت‌شده است.")
        triggers = self._aliases(data.get("triggers", []))
        if not triggers:
            raise ValueError("حداقل یک عبارت فعال‌کننده لازم است.")
        keys = {normalize(t) for t in triggers}
        for skill in self.rows("skills"):
            if skill["id"] != item_id and keys & {normalize(t) for t in skill["triggers"]}:
                raise ValueError("این عبارت قبلاً برای قابلیت دیگری ثبت شده است.")
        reply, room_id = "", None
        if kind == "reply":
            reply = clean(data.get("reply"), 8000, "پاسخ")
        else:
            try:
                room_id = int(data.get("room_id"))
            except (TypeError, ValueError):
                raise ValueError("اتاق را انتخاب کنید.") from None
            if not any(x["id"] == room_id for x in self.rows("rooms")):
                raise ValueError("اتاق مقصد پیدا نشد.")
        return self._write("skills", {"name": clean(data.get("name"), 120, "نام قابلیت"),
            "triggers": json.dumps(triggers, ensure_ascii=False), "kind": kind, "reply": reply,
            "room_id": room_id, "enabled": int(bool(data.get("enabled", True))), "updated_at": time.time()}, item_id)

    def delete(self, table, item_id):
        if table not in {"memories", "rooms", "skills"}:
            raise ValueError("نوع مورد نامعتبر است.")
        with self.connect() as db:
            if table == "rooms":
                db.execute("UPDATE skills SET enabled=0 WHERE room_id=?", (item_id,))
            if db.execute(f"DELETE FROM {table} WHERE id=?", (int(item_id),)).rowcount != 1:
                raise ValueError("مورد پیدا نشد.")

    def retrieve(self, text, limit=5):
        stopwords = set("چه چیست چیه کی هست است رو را به از با برای لطفا می شود آیا ساعت الان بگو درباره چطور چگونه".split())
        keys = set(normalize(text).split()) - stopwords
        scored = []
        for row in self.rows("memories"):
            title = set(normalize(row["title"]).split()) - stopwords
            body = set(normalize(row["body"]).split()) - stopwords
            overlap = len(keys & title)
            score = overlap * 4 + len(keys & body)
            if keys and (overlap > 0 or len(keys & body) >= 2):
                scored.append((score, row))
        return [row for _, row in sorted(scored, key=lambda x: (x[0], x[1]["updated_at"]), reverse=True)[:limit]]

    def exact_memory(self, text):
        key = normalize(text)
        endings = (" چیست", " چیه", " چه ساعتی است", " را بگو", " رو بگو")
        options = {key}
        for tail in endings:
            if key.endswith(tail):
                options.add(key[:-len(tail)].strip())
        matches = [row for row in self.rows("memories") if normalize(row["title"]) in options]
        return matches[0] if len(matches) == 1 else None

    def propose(self, session, kind, payload):
        proposal_id = secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute("DELETE FROM proposals WHERE expires_at<? OR session_id=?", (time.time(), session))
            count = db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            if count >= 200:
                raise ValueError("تعداد درخواست‌های در انتظار زیاد است؛ کمی بعد تلاش کنید.")
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?)", (proposal_id, session, kind,
                       json.dumps(payload, ensure_ascii=False), time.time() + 300))
        return {"id": proposal_id, "kind": kind, "payload": payload, "expires_in": 300}

    def confirm_memory(self, proposal_id, session):
        # One transaction: consuming a confirmation twice never writes two memories.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM proposals WHERE id=? AND session_id=? AND expires_at>?",
                             (proposal_id, session, time.time())).fetchone()
            if not row or row["kind"] != "memory":
                raise ValueError("درخواست منقضی شده یا متعلق به این گفتگو نیست.")
            data = json.loads(row["payload"])
            if any(normalize(existing["title"]) == normalize(data["title"]) for existing in db.execute("SELECT title FROM memories")):
                raise ValueError("این عنوان قبلاً ثبت شده؛ در بخش آموزش، مورد قبلی را ویرایش کنید.")
            now = time.time()
            item_id = db.execute("INSERT INTO memories(title,body,kind,created_at,updated_at) VALUES(?,?,?,?,?)",
                                (data["title"], data["body"], data["kind"], now, now)).lastrowid
            db.execute("DELETE FROM proposals WHERE id=?", (proposal_id,))
            return item_id


_store = None


def get_store():
    global _store
    if _store is None:
        _store = AgentStore()
    return _store


def admin_key():
    provided = os.getenv("TIMO_AGENT_ADMIN_KEY", "").strip()
    if provided:
        if len(provided) < 24:
            raise ValueError("TIMO_AGENT_ADMIN_KEY باید حداقل ۲۴ نویسه باشد.")
        return provided
    path = BASE_DIR / "data" / "agent-admin.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(secrets.token_urlsafe(32))
        path.chmod(0o600)
    except FileExistsError:
        pass
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 24:
        raise ValueError("فایل کلید مدیر نامعتبر است؛ تنظیمات ایجنت را بررسی کنید.")
    return value
