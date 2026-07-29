"""Persistent short-term conversation handoffs for Ombre Brain."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class HandoffManager:
    """Store handoffs separately from decaying and mergeable memory buckets."""

    def __init__(self, buckets_dir: str):
        self.directory = Path(buckets_dir) / "handoffs"
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, handoff_id: str) -> Path:
        if not handoff_id or any(c not in "0123456789abcdef-" for c in handoff_id.lower()):
            raise ValueError("invalid handoff_id")
        return self.directory / f"{handoff_id}.json"

    def _write(self, handoff: dict[str, Any]) -> None:
        target = self._path(handoff["id"])
        fd, temporary = tempfile.mkstemp(
            dir=str(self.directory), prefix=".handoff-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(handoff, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def create(
        self,
        summary: str,
        channel: str = "claude",
        emotional_state: Optional[dict[str, Any]] = None,
        unresolved: Optional[list[str]] = None,
        promises: Optional[list[dict[str, Any]]] = None,
        decisions: Optional[list[str]] = None,
        source_refs: Optional[list[str]] = None,
        ttl_days: int = 14,
    ) -> dict[str, Any]:
        if not summary or not summary.strip():
            raise ValueError("summary is required")
        ttl_days = max(1, min(365, int(ttl_days)))
        now = _now()
        handoff = {
            "schema_version": 1,
            "id": str(uuid.uuid4()),
            "event": "conversation_handoff",
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "expires_at": _iso(now + timedelta(days=ttl_days)),
            "channel": channel.strip() or "claude",
            "summary": summary.strip(),
            "emotional_state": emotional_state or {},
            "unresolved": [
                {"id": str(uuid.uuid4()), "item": item.strip(), "status": "open"}
                for item in (unresolved or [])
                if item and item.strip()
            ],
            "promises": [
                {
                    "id": str(uuid.uuid4()),
                    "actor": str(item.get("actor", "claude")).strip() or "claude",
                    "content": str(item.get("content", "")).strip(),
                    "due_at": item.get("due_at"),
                    "status": "pending",
                }
                for item in (promises or [])
                if item.get("content")
            ],
            "decisions": [item.strip() for item in (decisions or []) if item and item.strip()],
            "source_refs": [item.strip() for item in (source_refs or []) if item and item.strip()],
            "status": "active",
            "promoted_bucket_id": None,
        }
        self._write(handoff)
        return handoff

    def get(self, handoff_id: str) -> Optional[dict[str, Any]]:
        path = self._path(handoff_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)

    def list_recent(
        self, limit: int = 5, include_expired: bool = False
    ) -> list[dict[str, Any]]:
        now = _now()
        results = []
        for path in self.directory.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as stream:
                    handoff = json.load(stream)
                expired = _parse_iso(handoff["expires_at"]) <= now
                if expired and handoff.get("status") == "active":
                    handoff["status"] = "expired"
                    handoff["updated_at"] = _iso(now)
                    self._write(handoff)
                if include_expired or not expired:
                    results.append(handoff)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        results.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return results[: max(1, min(50, int(limit)))]

    def resolve_item(
        self, handoff_id: str, item_id: str, kind: str = "unresolved"
    ) -> Optional[dict[str, Any]]:
        handoff = self.get(handoff_id)
        if not handoff:
            return None
        collection = "promises" if kind == "promise" else "unresolved"
        target_status = "fulfilled" if collection == "promises" else "resolved"
        for item in handoff.get(collection, []):
            if item.get("id") == item_id:
                item["status"] = target_status
                item["resolved_at"] = _iso(_now())
                handoff["updated_at"] = _iso(_now())
                self._write(handoff)
                return handoff
        raise ValueError(f"{collection} item not found")

    def mark_promoted(self, handoff_id: str, bucket_id: str) -> dict[str, Any]:
        handoff = self.get(handoff_id)
        if not handoff:
            raise ValueError("handoff not found")
        handoff["status"] = "promoted"
        handoff["promoted_bucket_id"] = bucket_id
        handoff["updated_at"] = _iso(_now())
        self._write(handoff)
        return handoff

    @staticmethod
    def promotion_content(handoff: dict[str, Any]) -> str:
        lines = [handoff["summary"]]
        if handoff.get("decisions"):
            lines.append("决定：\n- " + "\n- ".join(handoff["decisions"]))
        open_items = [
            item["item"]
            for item in handoff.get("unresolved", [])
            if item.get("status") == "open"
        ]
        if open_items:
            lines.append("未完成：\n- " + "\n- ".join(open_items))
        promises = [
            f'{item.get("actor", "claude")}: {item["content"]}'
            for item in handoff.get("promises", [])
            if item.get("status") == "pending"
        ]
        if promises:
            lines.append("承诺：\n- " + "\n- ".join(promises))
        return "\n\n".join(lines)
