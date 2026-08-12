from pathlib import Path

import yaml


def test_compose_defines_durable_database_and_attachment_volumes() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((repository_root / "docker-compose.yml").read_text())

    assert {"api", "db"} <= manifest["services"].keys()
    assert manifest["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert "postgres-data" in manifest["volumes"]
    assert "attachment-data" in manifest["volumes"]


def test_postgres_acceptance_compose_isolated_to_a_test_database() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((repository_root / "docker-compose.test.yml").read_text())

    database = manifest["services"]["postgres-test"]
    runner = manifest["services"]["pytest-postgres"]
    assert database["environment"]["POSTGRES_DB"] == "agentpost_test"
    assert database["tmpfs"] == ["/var/lib/postgresql/data"]
    assert runner["depends_on"]["postgres-test"]["condition"] == "service_healthy"
    assert "/agentpost_test" in runner["environment"]["AGENTPOST_TEST_POSTGRES_URL"]
