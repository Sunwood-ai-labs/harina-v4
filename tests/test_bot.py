from app.bot import should_process_message


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
