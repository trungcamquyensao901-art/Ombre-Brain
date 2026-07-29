import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from handoff_manager import HandoffManager


class HandoffManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = HandoffManager(str(Path(self.temp.name)))

    def tearDown(self):
        self.temp.cleanup()

    def test_create_and_list_handoff(self):
        created = self.manager.create(
            summary="决定先实现会话交接。",
            channel="claude_mobile",
            emotional_state={"user": "期待"},
            unresolved=["部署到 VPS"],
            promises=[{"actor": "claude", "content": "完成测试"}],
            decisions=["handoff 集成进 Ombre"],
            source_refs=["conversation/abc"],
        )
        recent = self.manager.list_recent()
        self.assertEqual(recent[0]["id"], created["id"])
        self.assertEqual(recent[0]["unresolved"][0]["status"], "open")
        self.assertEqual(recent[0]["promises"][0]["status"], "pending")

    def test_resolve_item_and_fulfill_promise(self):
        created = self.manager.create(
            summary="测试交接",
            unresolved=["一件事"],
            promises=[{"actor": "claude", "content": "一个承诺"}],
        )
        self.manager.resolve_item(
            created["id"], created["unresolved"][0]["id"], "unresolved"
        )
        self.manager.resolve_item(
            created["id"], created["promises"][0]["id"], "promise"
        )
        updated = self.manager.get(created["id"])
        self.assertEqual(updated["unresolved"][0]["status"], "resolved")
        self.assertEqual(updated["promises"][0]["status"], "fulfilled")

    def test_expired_handoff_is_hidden(self):
        created = self.manager.create(summary="即将过期")
        path = self.manager._path(created["id"])
        created["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        path.write_text(json.dumps(created), encoding="utf-8")
        self.assertEqual(self.manager.list_recent(), [])
        self.assertEqual(
            self.manager.list_recent(include_expired=True)[0]["status"], "expired"
        )

    def test_promote_state_and_content(self):
        created = self.manager.create(
            summary="关键讨论",
            decisions=["采用 Coread"],
            unresolved=["完成部署"],
            promises=[{"actor": "claude", "content": "继续实现"}],
        )
        content = self.manager.promotion_content(created)
        self.assertIn("采用 Coread", content)
        self.assertIn("完成部署", content)
        self.assertIn("继续实现", content)
        promoted = self.manager.mark_promoted(created["id"], "bucket-123")
        self.assertEqual(promoted["status"], "promoted")
        self.assertEqual(promoted["promoted_bucket_id"], "bucket-123")

    def test_rejects_empty_summary_and_bad_id(self):
        with self.assertRaises(ValueError):
            self.manager.create(summary=" ")
        with self.assertRaises(ValueError):
            self.manager.get("../escape")


if __name__ == "__main__":
    unittest.main()
