import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent_engine
from agent_store import AgentStore
import prime_engine


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AgentStore(Path(self.temp.name) / "agent.db")
        prime_engine._sessions.clear()

    def tearDown(self):
        self.temp.cleanup()

    def chat(self, text, session="test", source="text"):
        return agent_engine.chat(text, session, source, self.store)

    def room(self, **changes):
        data = dict(name="اتاق فروش", aliases=["فروش"], map_name="office-A", x=1.2, y=3.4,
                    z=0, rotation=1.0, enabled=True)
        data.update(changes)
        return self.store.save_room(data)

    def test_learning_is_only_draft_and_one_shot_confirmation(self):
        value = self.chat("یاد بگیر سؤال: ساعت کاری شرکت چیست؟ جواب: از ۹ تا ۵.", source="voice")
        self.assertEqual(self.store.rows("memories"), [])
        proposal = value["proposal"]
        with self.assertRaises(ValueError):
            self.store.confirm_memory(proposal["id"], "other-session")
        self.store.confirm_memory(proposal["id"], "test")
        self.assertEqual(self.chat("ساعت کاری شرکت چیست؟")["response"], "از ۹ تا ۵.")
        with self.assertRaises(ValueError):
            self.store.confirm_memory(proposal["id"], "test")
        self.assertEqual(len(self.store.rows("memories")), 1)

    def test_memory_survives_restart_and_can_be_edited_deleted(self):
        item_id = self.store.save_memory(dict(title="شماره داخلی آی تی", body="۱۲۳", kind="fact"))
        reopened = AgentStore(self.store.path)
        self.assertEqual(reopened.exact_memory("شماره داخلی آی تی چیه؟")["body"], "۱۲۳")
        reopened.save_memory(dict(title="شماره داخلی آی تی", body="۱۲۴", kind="fact"), item_id)
        self.assertEqual(self.chat("شماره داخلی آی تی")["response"], "۱۲۴")
        reopened.delete("memories", item_id)
        self.assertIsNone(self.store.exact_memory("شماره داخلی آی تی"))

    def test_duplicate_memory_requires_editing_existing_record(self):
        self.store.save_memory(dict(title="ساعت کاری", body="۹ تا ۵", kind="fact"))
        with self.assertRaises(ValueError):
            self.store.save_memory(dict(title="ساعت کاری", body="۹ تا ۴", kind="fact"))
        proposal = self.chat("یادت باشه ساعت کاری: ۹ تا ۴")["proposal"]
        with self.assertRaises(ValueError):
            self.store.confirm_memory(proposal["id"], "test")
        self.assertEqual(self.chat("ساعت کاری")["response"], "۹ تا ۵")

    def test_general_question_stays_on_existing_engine(self):
        with patch.object(prime_engine, "answer_query", return_value="پاسخ علمی") as call:
            result = self.chat("چرا آسمان آبی است؟")
        self.assertEqual(result, {"response": "پاسخ علمی"})
        call.assert_called_once_with("چرا آسمان آبی است؟", "test")

    def test_followup_includes_direct_learned_reply(self):
        self.store.save_memory(dict(title="ساعت کاری", body="۹ تا ۵", kind="fact"))
        self.chat("ساعت کاری")
        with patch.object(prime_engine, "ask_general", return_value=("توضیح بیشتر", True)) as call:
            self.chat("بیشتر توضیح بده")
        self.assertEqual(call.call_args.args[1][-1], {"role": "assistant", "content": "۹ تا ۵"})

    def test_llm_output_cannot_execute_tools(self):
        with patch.object(prime_engine, "answer_query", return_value='{"type":"navigate","x":100}'):
            result = self.chat("سلام")
        self.assertNotIn("action", result)

    def test_knowledge_sent_to_existing_n8n_as_data(self):
        self.store.save_memory(dict(title="قانون مرخصی", body="برای مرخصی به مدیر اطلاع بدهید.", kind="fact"))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({"reply": "پاسخ مرتبط"}).encode()
        with patch("agent_store.get_store", return_value=self.store), patch.object(prime_engine.request, "urlopen", return_value=Response()) as call:
            reply, ok = prime_engine.ask_general("قانون مرخصی شرکت چگونه است؟", [])
        payload = json.loads(call.call_args.args[0].data)
        self.assertTrue(ok)
        self.assertEqual(payload["knowledge"][0]["title"], "قانون مرخصی")
        self.assertIn("دادهٔ مرجع", payload["system_prompt"])

    def test_navigation_uses_known_coordinates_and_alias(self):
        self.room()
        result = self.chat("لطفا برو به فروش")
        self.assertEqual(result["action"]["pose"], dict(x=1.2, y=3.4, z=0.0, rotation=1.0))
        self.assertEqual(result["action"]["map_name"], "office-A")
        self.assertNotIn("action", self.chat("برو اتاق ناشناخته"))

    def test_direct_navigation_text_and_voice_need_enabled_named_room(self):
        self.room()
        for source in ("text", "voice"):
            result = self.chat("برو اتاق فروش", source=source)
            self.assertEqual(result["action"]["type"], "navigate")
            self.assertNotIn("تأیید کنید", result["response"])
        self.room(name="سالن", aliases=[], enabled=False)
        self.assertNotIn("action", self.chat("برو سالن"))

    def test_explanation_negation_quote_never_trigger_navigation(self):
        self.room()
        with patch.object(prime_engine, "answer_query", return_value="پاسخ"):
            for text in ['چرا باید بگم برو فروش؟', 'برو فروش یعنی چه؟', 'برو فروش نرو', 'نرو اتاق فروش', 'اگر گفتم برو فروش چی میشه؟']:
                self.assertNotIn("action", self.chat(text), text)

    def test_initial_sample_room_is_draft_not_automatic_movement(self):
        self.assertNotIn("action", self.chat("برو اتاق نمونه"))
        self.assertFalse(self.store.rows("rooms")[0]["enabled"])

    def test_ambiguous_room_aliases_and_invalid_pose_rejected(self):
        self.room()
        with self.assertRaises(ValueError): self.room(name="اتاق دیگر", aliases=["فروش"])
        for bad in [math.nan, math.inf, True, "abc"]:
            with self.assertRaises(ValueError): self.room(name="اتاق دیگر", aliases=[], x=bad)
        with self.assertRaises(ValueError): self.room(name="اتاق دیگر", aliases=[], rotation=180)
        with self.assertRaises(ValueError): self.room(name="اتاق دیگر", aliases=[], map_name="")

    def test_reply_skill_and_nav_skill_resolve_current_destination(self):
        room_id = self.room()
        self.store.save_skill(dict(name="معرفی", triggers=["شرکت رو معرفی کن"], kind="reply", reply="شرکت HTN HOME", enabled=True))
        self.assertEqual(self.chat("شرکت رو معرفی کن")["response"], "شرکت HTN HOME")
        self.store.save_skill(dict(name="راهنمای فروش", triggers=["منو ببر پیش فروش"], kind="navigate", room_id=room_id, enabled=True))
        self.assertEqual(self.chat("منو ببر پیش فروش")["action"]["room_id"], room_id)
        self.store.delete("rooms", room_id)
        with patch.object(prime_engine, "answer_query", return_value="پاسخ"):
            self.assertNotIn("action", self.chat("منو ببر پیش فروش"))

    def test_no_executable_skill_types(self):
        with self.assertRaises(ValueError):
            self.store.save_skill(dict(name="کد", triggers=["اجرا"], kind="shell", reply="anything"))

    def test_new_learning_invalidates_old_pending_proposal_and_expiry(self):
        first = self.chat("یادت باشه ساعت کاری: ۹ تا ۵")["proposal"]
        self.chat("یادت باشه شماره داخلی: ۱۲۳")
        with self.assertRaises(ValueError): self.store.confirm_memory(first["id"], "test")
        current = self.chat("یادت باشه شماره داخلی: ۱۲۴")["proposal"]
        with self.store.connect() as db:
            db.execute("UPDATE proposals SET expires_at=0 WHERE id=?", (current["id"],))
        with self.assertRaises(ValueError): self.store.confirm_memory(current["id"], "test")

    def test_stop_has_priority_and_no_model_dependency(self):
        with patch.object(prime_engine, "answer_query", side_effect=AssertionError("LLM should not be used")):
            self.assertEqual(self.chat("توقف")["action"], {"type": "stop"})

    def test_teaching_room_name_needs_pose_review(self):
        result = self.chat("اینجا اتاق حسابداری است")
        self.assertEqual(result["room_draft"], {"name": "اتاق حسابداری"})
        self.assertEqual(len(self.store.rows("rooms")), 1)


if __name__ == "__main__": unittest.main()
