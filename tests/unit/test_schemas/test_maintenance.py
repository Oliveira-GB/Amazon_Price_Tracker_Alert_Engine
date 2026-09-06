import uuid

import pytest
from pydantic import ValidationError

from schemas.maintenance import HardDeleteCommand, UserBlockedEvent


class TestUserBlockedEvent:
    def test_user_blocked_event_valid(self):
        event = UserBlockedEvent(
            event_id="blocked-123",
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            reason="bot_blocked_by_user",
        )
        assert event.event_id == "blocked-123"
        assert event.reason == "bot_blocked_by_user"

    def test_user_blocked_event_empty_reason(self):
        event = UserBlockedEvent(
            event_id="blocked-123",
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            reason="",
        )
        assert event.reason == ""

    def test_user_blocked_event_invalid_uuid(self):
        with pytest.raises(ValidationError) as exc_info:
            UserBlockedEvent(
                event_id="blocked-123",
                user_id="not-a-uuid",
                telegram_chat_id="123456",
                reason="bot_blocked",
            )
        assert "user_id" in str(exc_info.value)

    def test_user_blocked_event_serialization(self):
        user_id = uuid.uuid4()
        event = UserBlockedEvent(
            event_id="blocked-123",
            user_id=user_id,
            telegram_chat_id="123456",
            reason="bot_blocked",
        )
        json_data = event.model_dump_json()
        restored = UserBlockedEvent.model_validate_json(json_data)
        assert restored.user_id == user_id
        assert restored.reason == "bot_blocked"


class TestHardDeleteCommand:
    def test_hard_delete_command_valid(self):
        cmd = HardDeleteCommand(
            event_id="delete-123",
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
        )
        assert cmd.initiated_by == "system"

    def test_hard_delete_command_with_initiated_by(self):
        cmd = HardDeleteCommand(
            event_id="delete-123",
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
            initiated_by="telegram_403",
        )
        assert cmd.initiated_by == "telegram_403"

    def test_hard_delete_command_default_initiated_by(self):
        cmd = HardDeleteCommand(
            event_id="delete-123",
            user_id=uuid.uuid4(),
            telegram_chat_id="123456",
        )
        assert cmd.initiated_by == "system"

    def test_hard_delete_command_invalid_uuid(self):
        with pytest.raises(ValidationError) as exc_info:
            HardDeleteCommand(
                event_id="delete-123",
                user_id="not-a-uuid",
                telegram_chat_id="123456",
            )
        assert "user_id" in str(exc_info.value)

    def test_hard_delete_command_serialization(self):
        user_id = uuid.uuid4()
        cmd = HardDeleteCommand(
            event_id="delete-123",
            user_id=user_id,
            telegram_chat_id="123456",
            initiated_by="admin_manual",
        )
        json_data = cmd.model_dump_json()
        restored = HardDeleteCommand.model_validate_json(json_data)
        assert restored.user_id == user_id
        assert restored.initiated_by == "admin_manual"
