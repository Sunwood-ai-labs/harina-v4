import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.test_asset_runner import discover_test_images, run_test_asset_suite


def test_discover_test_images_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    (tmp_path / "b.png").write_bytes(b"png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    result = discover_test_images(tmp_path)

    assert result == [tmp_path / "a.jpg", tmp_path / "b.png"]


def test_run_test_asset_suite_runs_cli_and_discord(monkeypatch, tmp_path: Path) -> None:
    image_a = tmp_path / "IMG_1.jpg"
    image_b = tmp_path / "IMG_2.png"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")

    cli_calls: list[Path] = []
    discord_calls: list[tuple[int, Path, str, float]] = []

    async def fake_run_local_receipt_process(**kwargs):
        cli_calls.append(kwargs["image_path"])
        return {
            "image_path": str(kwargs["image_path"]),
            "mime_type": "image/jpeg",
            "google_write_performed": False,
        }

    async def fake_run_discord_upload_test(*, settings, channel_id, image_path, caption, timeout_seconds):
        del settings
        discord_calls.append((channel_id, image_path, caption, timeout_seconds))
        return {
            "channel_id": channel_id,
            "image_path": str(image_path),
            "reply_message_url": f"https://discord.test/{image_path.name}",
        }

    monkeypatch.setattr("app.test_asset_runner.run_local_receipt_process", fake_run_local_receipt_process)
    monkeypatch.setattr("app.test_asset_runner.run_discord_upload_test", fake_run_discord_upload_test)

    summary = asyncio.run(
        run_test_asset_suite(
            settings=SimpleNamespace(discord_test_channel_id=123456),
            source_dir=tmp_path,
            mode="both",
            discord_timeout_seconds=12.5,
        )
    )

    assert cli_calls == [image_a, image_b]
    assert discord_calls == [
        (123456, image_a, "docs/public/test IMG_1.jpg", 12.5),
        (123456, image_b, "docs/public/test IMG_2.png", 12.5),
    ]
    assert summary["image_count"] == 2
    assert summary["success"] is True
    assert summary["cli_result_count"] == 2
    assert summary["cli_failure_count"] == 0
    assert summary["discord_result_count"] == 2
    assert summary["discord_failure_count"] == 0
    assert summary["cli_results"][0]["status"] == "ok"
    assert summary["discord_results"][0]["status"] == "ok"


def test_run_test_asset_suite_collects_errors_and_continues(monkeypatch, tmp_path: Path) -> None:
    image_a = tmp_path / "IMG_1.jpg"
    image_b = tmp_path / "IMG_2.png"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")

    async def fake_run_local_receipt_process(**kwargs):
        if kwargs["image_path"] == image_a:
            raise RuntimeError("gemini busy")
        return {
            "image_path": str(kwargs["image_path"]),
            "mime_type": "image/png",
            "google_write_performed": False,
        }

    async def fake_run_discord_upload_test(*, settings, channel_id, image_path, caption, timeout_seconds):
        del settings, channel_id, caption, timeout_seconds
        if image_path == image_b:
            raise RuntimeError("timeout")
        return {
            "image_path": str(image_path),
            "reply_message_url": "https://discord.test/ok",
        }

    monkeypatch.setattr("app.test_asset_runner.run_local_receipt_process", fake_run_local_receipt_process)
    monkeypatch.setattr("app.test_asset_runner.run_discord_upload_test", fake_run_discord_upload_test)

    summary = asyncio.run(
        run_test_asset_suite(
            settings=SimpleNamespace(discord_test_channel_id=123456),
            source_dir=tmp_path,
            mode="both",
        )
    )

    assert summary["success"] is False
    assert summary["cli_failure_count"] == 1
    assert summary["discord_failure_count"] == 1
    assert summary["cli_results"][0]["status"] == "error"
    assert summary["discord_results"][1]["status"] == "error"
