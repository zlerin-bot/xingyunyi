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


def test_production_compose_keeps_database_and_api_off_public_ports() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((repository_root / "docker-compose.production.yml").read_text())

    assert {"api", "caddy", "db"} == manifest["services"].keys()
    assert "ports" not in manifest["services"]["api"]
    assert "ports" not in manifest["services"]["db"]
    assert manifest["services"]["caddy"]["ports"] == ["80:80", "443:443", "443:443/udp"]
    assert manifest["services"]["api"]["environment"]["AGENTPOST_ENVIRONMENT"] == "production"
    assert manifest["services"]["api"]["read_only"] is True
    assert manifest["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert manifest["services"]["caddy"]["depends_on"]["api"]["condition"] == "service_healthy"


def test_production_compose_uses_durable_state_and_no_literal_secrets() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_text = (repository_root / "docker-compose.production.yml").read_text()
    manifest = yaml.safe_load(manifest_text)

    assert {"postgres-data", "attachment-data", "caddy-data", "caddy-config"} <= set(
        manifest["volumes"]
    )
    assert "development-only" not in manifest_text
    assert "POSTGRES_PASSWORD: agentpost" not in manifest_text
    assert "AGENTPOST_API_KEY_PEPPER: replace" not in manifest_text
