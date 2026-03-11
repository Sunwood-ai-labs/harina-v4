from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.config import Settings
from app.discord_upload_test import run_discord_upload_test
from app.gemini_smoke_test import is_supported_image_file
from app.local_receipt_runner import run_local_receipt_process


DEFAULT_TEST_ASSET_DIR = Path("docs/public/test")
TestAssetMode = Literal["both", "cli", "discord"]


def discover_test_images(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise RuntimeError(f"Test asset directory does not exist: {source_dir}")

    return sorted(path for path in source_dir.rglob("*") if is_supported_image_file(path))


async def run_test_asset_suite(
    *,
    settings: Settings,
    source_dir: Path,
    mode: TestAssetMode,
    channel_id: int | None = None,
    discord_timeout_seconds: float = 60.0,
    cli_google_write: bool = False,
) -> dict[str, object]:
    images = discover_test_images(source_dir)
    if not images:
        raise RuntimeError(f"No supported test images found under: {source_dir}")

    cli_results: list[dict[str, object]] = []
    cli_failure_count = 0
    if mode in {"both", "cli"}:
        for image_path in images:
            try:
                cli_results.append(
                    {
                        "status": "ok",
                        **await run_local_receipt_process(
                            settings=settings,
                            image_path=image_path,
                            skip_google_write=not cli_google_write,
                            source_name="docs-public-test-cli",
                            author_tag="harina-v4-test",
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                cli_failure_count += 1
                cli_results.append(
                    {
                        "status": "error",
                        "image_path": str(image_path.resolve()),
                        "error": str(exc) or exc.__class__.__name__,
                    }
                )

    discord_results: list[dict[str, object]] = []
    discord_failure_count = 0
    if mode in {"both", "discord"}:
        target_channel_id = channel_id or settings.discord_test_channel_id
        if target_channel_id is None:
            raise RuntimeError("Set --channel-id or DISCORD_TEST_CHANNEL_ID before running Discord test assets.")

        for image_path in images:
            try:
                discord_results.append(
                    {
                        "status": "ok",
                        **await run_discord_upload_test(
                            settings=settings,
                            channel_id=target_channel_id,
                            image_path=image_path,
                            caption=f"docs/public/test {image_path.name}",
                            timeout_seconds=discord_timeout_seconds,
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                discord_failure_count += 1
                discord_results.append(
                    {
                        "status": "error",
                        "channel_id": target_channel_id,
                        "image_path": str(image_path.resolve()),
                        "error": str(exc) or exc.__class__.__name__,
                    }
                )

    return {
        "success": cli_failure_count == 0 and discord_failure_count == 0,
        "mode": mode,
        "source_dir": str(source_dir.resolve()),
        "image_count": len(images),
        "images": [str(path.resolve()) for path in images],
        "cli_google_write": cli_google_write,
        "cli_result_count": len(cli_results),
        "cli_failure_count": cli_failure_count,
        "discord_result_count": len(discord_results),
        "discord_failure_count": discord_failure_count,
        "cli_results": cli_results,
        "discord_results": discord_results,
    }
