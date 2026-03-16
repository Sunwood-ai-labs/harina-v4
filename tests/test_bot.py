import asyncio

from app.bot import ReceiptBot, build_receipt_thread_name, should_process_message
from app.processor import ProcessedReceipt


class _FakeDebugSession:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def write_event(self, event: str, **payload: object) -> None:
        self.events.append((event, payload))


class _FakeBot:
    def __init__(self, *, processed: ProcessedReceipt) -> None:
        self.debug_session = _FakeDebugSession()
        self._processed = processed

    async def _process_attachment(self, *, message, attachment) -> ProcessedReceipt:
        del message, attachment
        return self._processed


class _FakeMessage:
    id = 123


class _FakeAttachment:
    id = 456
    filename = "img_8923.jpg"


def test_should_process_regular_user_message() -> None:
    assert should_process_message(
        author_is_bot=False,
        author_id=1,
        self_user_id=99,
        content="receipt",
        channel_id=10,
        allowed_channel_ids=set(),
        test_message_prefix="[HARINA-TEST]",
    )


def test_should_reject_other_bot_message() -> None:
    assert not should_process_message(
        author_is_bot=True,
        author_id=2,
        self_user_id=99,
        content="[HARINA-TEST] receipt",
        channel_id=10,
        allowed_channel_ids=set(),
        test_message_prefix="[HARINA-TEST]",
    )


def test_should_allow_self_test_message_with_prefix() -> None:
    assert should_process_message(
        author_is_bot=True,
        author_id=99,
        self_user_id=99,
        content="[HARINA-TEST] receipt",
        channel_id=10,
        allowed_channel_ids={10},
        test_message_prefix="[HARINA-TEST]",
    )


def test_should_reject_message_outside_allowed_channel_ids() -> None:
    assert not should_process_message(
        author_is_bot=False,
        author_id=1,
        self_user_id=99,
        content="receipt",
        channel_id=11,
        allowed_channel_ids={10},
        test_message_prefix="[HARINA-TEST]",
    )


def test_build_receipt_thread_name_includes_attachment_count() -> None:
    assert build_receipt_thread_name(message_id=123, attachment_count=1) == "receipt-123-receipt"
    assert build_receipt_thread_name(message_id=123, attachment_count=2) == "receipt-123-2-receipts"


def test_process_attachment_outcome_returns_skip_embed_with_sheet_link_only() -> None:
    fake_bot = _FakeBot(
        processed=ProcessedReceipt(
            extraction=None,
            summary="Skipped because img_8923.jpg is already recorded in Google Sheets.",
            drive_file_id=None,
            drive_file_url=None,
            spreadsheet_url="https://docs.google.com/spreadsheets/d/test-sheet/edit",
            rows=[],
            google_write_performed=False,
            skipped_existing=True,
            skipped_attachment_name="img_8923.jpg",
        )
    )

    outcome = asyncio.run(
        ReceiptBot._process_attachment_outcome(
            fake_bot,
            message=_FakeMessage(),
            attachment=_FakeAttachment(),
            index=1,
            total_attachments=1,
        )
    )

    assert outcome.ok is True
    assert outcome.embed.title == "Receipt Skipped"
    assert outcome.view is not None
    assert [child.label for child in outcome.view.children] == ["Open Sheet"]
    assert fake_bot.debug_session.events == [
        (
            "attachment_skipped_existing",
            {
                "message_id": 123,
                "attachment_id": 456,
                "filename": "img_8923.jpg",
                "index": 1,
                "total_attachments": 1,
            },
        )
    ]
