from pathlib import Path

import yaml


def test_compose_defines_durable_database_and_attachment_volumes() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((repository_root / "docker-compose.yml").read_text())

    assert {"api", "db"} <= manifest["services"].keys()
    assert manifest["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert "postgres-data" in manifest["volumes"]
    assert "attachment-data" in manifest["volumes"]
