"""Explicit Persian tool routing; LLM answers never become robot commands."""
import re

import prime_engine
from agent_store import get_store, normalize

STOP_COMMANDS = {"توقف", "بایست", "وایسا", "حرکت نکن", "توقف حرکت", "توقف ربات"}


def navigation_target(text):
    value = normalize(text)
    # Anchored grammar: quoted questions, negation and explanatory prose are not actions.
    match = re.fullmatch(r"(?:لطفا )?(?:(?:برو|حرکت کن)(?: به)?|(?:منو|من را|من رو) ببر(?: به)?|ببرم(?: به)?) (.+)", value)
    if not match:
        return None
    return match.group(1)


def room_matches(room, target):
    keys = {normalize(room["name"]), *(normalize(x) for x in room["aliases"])}
    return target in keys


def room_proposal(room):
    if not room["enabled"] or not room["map_name"]:
        return {"response": "این اتاق ثبت شده، اما نقشه و فعال‌بودن مقصد هنوز تأیید نشده؛ بخش «آموزش ایجنت» را بررسی کنید."}
    return {"response": f"مقصد «{room['name']}» را پیدا کردم؛ درخواست حرکت را به اپ ربات می‌فرستم.",
            "action": {"type": "navigate", "room_id": room["id"], "name": room["name"],
                       "map_name": room["map_name"],
                       "pose": {k: room[k] for k in ("x", "y", "z", "rotation")}}}


def direct_reply(text, session_id, source="text", store=None):
    store = store or get_store()
    text = str(text).strip()[:6000]
    key = normalize(text)
    if not key:
        return {"response": "لطفاً سؤال یا دستور را بگید."}
    if key in STOP_COMMANDS:
        return {"response": "درخواست لغو ناوبری را به ربات می‌فرستم؛ توقف واقعی را بررسی کنید.",
                "action": {"type": "stop"}}
    here = re.fullmatch(r"(?:یادت باشه )?اینجا (?:اتاق )?(.+?) (?:است|هست|هستش)", key)
    if here:
        return {"response": "نام اتاق را آماده کردم. در بخش آموزش، موقعیت فعلی ربات را دریافت و همراه نام نقشه بررسی کنید؛ سپس ذخیره کنید.",
                "room_draft": {"name": "اتاق " + here.group(1)}}
    # Learning is a draft regardless of input source. Only a manager can persist it.
    match = re.match(r"^(?:یاد بگیر|یادت باشه|به خاطر بسپار)(?:\s+که)?\s*[:：]?\s+(.+)$", text, re.S)
    if match:
        body = match.group(1).strip()
        qa = re.fullmatch(r"(?:سؤال|سوال)\s*[:：]\s*(.+?)\s+(?:جواب|پاسخ)\s*[:：]\s*(.+)", body, re.S)
        if qa:
            payload = {"title": qa.group(1).strip()[:200], "body": qa.group(2).strip(), "kind": "qa"}
        else:
            parts = re.split(r"\s*[:：]\s*", body, maxsplit=1)
            payload = {"title": parts[0][:200], "body": parts[1] if len(parts) == 2 else body, "kind": "fact"}
        proposal = store.propose(session_id, "memory", payload)
        return {"response": "این اطلاعات را برای یادگیری آماده کردم. متن شنیده‌شده را بررسی و با کلید مدیر ذخیره کنید؛ هنوز در حافظه ثبت نشده.", "proposal": proposal}
    target = navigation_target(text)
    if target:
        matches = [room for room in store.rows("rooms") if room_matches(room, target)]
        if len(matches) == 1:
            return room_proposal(matches[0])
    for skill in store.rows("skills"):
        if skill["enabled"] and key in {normalize(t) for t in skill["triggers"]}:
            if skill["kind"] == "reply":
                prime_engine.remember_reply(text, skill["reply"], session_id)
                return {"response": skill["reply"], "source": "skill"}
            room = next((r for r in store.rows("rooms") if r["id"] == skill["room_id"]), None)
            return room_proposal(room) if room else {"response": "مقصد این قابلیت حذف شده است."}
    if target:
        return {"response": "اتاقی با این نام پیدا نکردم. نام و موقعیتش را در بخش آموزش ثبت کنید؛ فعلاً فرمان حرکت ارسال نشد."}
    memory = store.exact_memory(text)
    if memory:
        prime_engine.remember_reply(text, memory["body"], session_id)
        return {"response": memory["body"], "source": "memory",
                "references": [{"id": memory["id"], "title": memory["title"]}]}
    return None


def canonical_query(text):
    key = normalize(text)
    intro_commands = {"محصولات رو معرفی کن", "محصولات را معرفی کن", "محصولات را معرفی کنید",
                      "محصولات رو معرفی کنید", "محصولات شرکت رو معرفی کن", "کاتالوگ رو معرفی کن"}
    if key.removeprefix("لطفا ") in intro_commands:
        return "چه محصولاتی دارید؟"
    return text


def chat(text, session_id, source="text", store=None):
    result = direct_reply(text, session_id, source, store)
    if result is not None:
        return result
    response = prime_engine.answer_query(canonical_query(text), session_id)
    if response == "__EXIT__":
        response = "گفتگو به پایان رسید."
    return {"response": response}
