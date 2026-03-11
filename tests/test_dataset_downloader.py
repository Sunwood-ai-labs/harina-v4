from pathlib import Path

from app.dataset_downloader import (
    ChannelReference,
    DownloadRecord,
    build_attachment_path,
    build_named_segment,
    parse_channel_url,
    write_metadata,
)


def test_parse_channel_url_with_channel_link() -> None:
    reference = parse_channel_url("https://discord.com/channels/1208743618345435226/1432620533928951930")
    assert reference == ChannelReference(guild_id=1208743618345435226, channel_id=1432620533928951930, message_id=None)


def test_parse_channel_url_with_message_link() -> None:
    reference = parse_channel_url("https://discord.com/channels/1/2/3")
    assert reference == ChannelReference(guild_id=1, channel_id=2, message_id=3)


def test_build_attachment_path_preserves_original_filename(tmp_path: Path) -> None:
    target = build_attachment_path(
        output_dir=tmp_path,
        reference=ChannelReference(guild_id=100, channel_id=200),
        guild_name="Example Guild",
        channel_name="receipt uploads",
        message_id=300,
        attachment_id=400,
        filename="sample image.png",
    )

    assert (
        target
        == tmp_path
        / "guild-Example-Guild-100"
        / "channel-receipt-uploads-200"
        / "message-300"
        / "attachment-400"
        / "sample image.png"
    )


def test_write_metadata_outputs_jsonl(tmp_path: Path) -> None:
    metadata_path = write_metadata(
        output_dir=tmp_path,
        records=[
            DownloadRecord(
                guild_id=1,
                guild_name="Guild",
                channel_id=2,
                channel_name="images",
                message_id=3,
                message_url="https://discord.com/channels/1/2/3",
                author_id=4,
                author_name="User#0001",
                created_at="2026-03-11T00:00:00+00:00",
                attachment_id=5,
                filename="photo.jpg",
                content_type="image/jpeg",
                size=123,
                relative_path="guild-1/channel-2/message-3/attachment-5/photo.jpg",
                source_url="https://cdn.discordapp.com/attachments/file.jpg",
            )
        ],
    )

    assert metadata_path == tmp_path / "metadata.jsonl"
    assert metadata_path.read_text(encoding="utf-8").strip().startswith('{"guild_id": 1')


def test_build_named_segment_skips_japanese_name() -> None:
    assert build_named_segment("guild", 123, "はりな") == "guild-123"
    assert build_named_segment("channel", 456, "v3_maki") == "channel-v3_maki-456"
