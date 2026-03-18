from pathlib import Path


def _service_block(compose_text: str, service_name: str) -> str:
    lines = compose_text.splitlines()
    marker = f"  {service_name}:"
    start_index = next(index for index, line in enumerate(lines) if line == marker)

    block_lines: list[str] = []
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index > start_index and line.startswith("  ") and not line.startswith("    "):
            break
        block_lines.append(line)

    return "\n".join(block_lines)


def test_docker_compose_keeps_google_oauth_file_mounts_for_runtime_services() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    for service_name in ("receipt-bot", "drive-watcher"):
        block = _service_block(compose_text, service_name)
        assert "env_file:" in block
        assert "- .env" in block
        assert "GOOGLE_OAUTH_CLIENT_SECRET_FILE: /app/secrets/harina-oauth-client.json" in block
        assert "- ./secrets:/app/secrets:ro" in block


def test_docker_compose_keeps_uv_entrypoints_for_bot_and_drive_watcher() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    receipt_bot_block = _service_block(compose_text, "receipt-bot")
    drive_watcher_block = _service_block(compose_text, "drive-watcher")

    assert 'command: ["uv", "run", "--no-dev", "harina-v4", "bot", "run"]' in receipt_bot_block
    assert 'command: ["uv", "run", "--no-dev", "harina-v4", "drive", "watch"]' in drive_watcher_block
