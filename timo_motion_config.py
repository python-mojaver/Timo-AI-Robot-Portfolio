"""One server-owned active-map setting; room coordinates are never rewritten here."""
import json
import uuid

KEY = "shared-motion-map-v1"


def get_shared_map(store):
    with store.connect() as db:
        row = db.execute("SELECT value FROM meta WHERE key=?", (KEY,)).fetchone()
    if row is None:
        return {"map_name": "", "revision": "", "configured": False}
    value = json.loads(row[0])
    return {"map_name": value["map_name"], "revision": value["revision"], "configured": True}


def set_shared_map(store, data):
    name = data.get("map_name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError("نام نقشه باید بین ۱ تا ۱۲۰ نویسه باشد.")
    expected = data.get("expected_revision")
    if not isinstance(expected, str):
        raise ValueError("صفحه را تازه کنید و دوباره ذخیره کنید.")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM meta WHERE key=?", (KEY,)).fetchone()
        current = json.loads(row[0]) if row else {"revision": "", "map_name": ""}
        if expected != current["revision"]:
            raise ValueError("تنظیم نقشه در دستگاه دیگری تغییر کرده؛ صفحه را تازه کنید.")
        if name.strip() == current["map_name"]:
            return {**current, "configured": True}
        value = {"map_name": name.strip(), "revision": uuid.uuid4().hex}
        db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (KEY, json.dumps(value, ensure_ascii=False)))
    return {**value, "configured": True}
