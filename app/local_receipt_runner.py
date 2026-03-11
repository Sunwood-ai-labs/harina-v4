from __future__ import annotations

import mimetypes
from pathlib import Path

from app.config import Settings
from app.formatters import build_local_receipt_context
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient
from app.processor import ReceiptProcessor


async def run_local_receipt_process(
    *,
    settings: Settings,
    image_path: Path,
    mime_type: str | None = None,
    skip_google_write: bool = False,
    source_name: str = "cli",
    author_tag: str = "harina-v4",
) -> dict[str, object]:
    if not image_path.exists():
        raise RuntimeError(f"Image file does not exist: {image_path}")
    if not image_path.is_file():
        raise RuntimeError(f"Image path is not a file: {image_path}")

    settings.require_gemini_api_key()
    google_workspace = None
    if not skip_google_write:
        settings.require_google_workspace()
        google_workspace = GoogleWorkspaceClient(
            credentials=settings.google_credentials,
            drive_folder_id=settings.google_drive_folder_id or "",
            spreadsheet_id=settings.google_sheets_spreadsheet_id or "",
            sheet_name=settings.google_sheets_sheet_name,
        )

    processor = ReceiptProcessor(
        gemini=GeminiReceiptExtractor(
            api_key=settings.gemini_api_key or "",
            model=settings.gemini_model,
        ),
        google_workspace=google_workspace,
    )

    resolved_mime_type = mime_type or mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    result = await processor.process_receipt(
        context=build_local_receipt_context(
            image_path,
            source_name=source_name,
            author_tag=author_tag,
        ),
        filename=image_path.name,
        mime_type=resolved_mime_type,
        image_bytes=image_path.read_bytes(),
        write_to_google=not skip_google_write,
    )

    return {
        "image_path": str(image_path.resolve()),
        "mime_type": resolved_mime_type,
        **result.as_dict(),
    }
