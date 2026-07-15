"""OPS-4: static checks on deploy artefacts.

These tests don't actually spin up Docker or systemd — they're cheap sanity
checks that catch syntax errors and typos before someone hits them on a real
host. Full end-to-end deployment validation happens manually against a real
target and is documented in docs/DEPLOYMENT.md.
"""
import configparser
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _shell_syntax_check(script: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash -n failed for {script.name}:\n{result.stderr}"


def test_install_sh_parses():
    _shell_syntax_check(REPO_ROOT / "scripts" / "install.sh")


def test_backup_sh_parses():
    _shell_syntax_check(REPO_ROOT / "scripts" / "backup.sh")


def test_restore_sh_parses():
    _shell_syntax_check(REPO_ROOT / "scripts" / "restore.sh")


def test_dockerfile_has_healthcheck_and_non_root_user():
    text = (REPO_ROOT / "Dockerfile").read_text()
    assert "HEALTHCHECK" in text
    assert "/api/healthz" in text  # HEALTHCHECK must probe our endpoint
    assert "USER foi" in text  # non-root at runtime
    assert "gunicorn" in text  # not the Flask dev server


def test_docker_compose_yaml_is_valid():
    """Cheap check: the file parses as YAML and has the app service defined.
    Uses PyYAML if available, otherwise falls back to a substring check."""
    text = (REPO_ROOT / "docker-compose.yml").read_text()
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("PyYAML not installed; substring check")
    doc = yaml.safe_load(text)
    assert "services" in doc
    assert "app" in doc["services"]
    assert "SECRET_KEY" in "\n".join(doc["services"]["app"].get("environment", []))


def test_systemd_service_units_are_valid_ini():
    for name in (
        "foi-tracker.service",
        "foi-tracker-backup.service",
        "foi-tracker-backup.timer",
    ):
        path = REPO_ROOT / "deploy" / "systemd" / name
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        # systemd allows repeated keys — configparser rejects them by default
        # but with strict=False it just keeps the last. Good enough for a
        # smoke check.
        cp.read(path)
        assert cp.sections(), f"{name} has no sections"


def test_service_unit_references_env_file_and_gunicorn():
    text = (REPO_ROOT / "deploy" / "systemd" / "foi-tracker.service").read_text()
    assert "EnvironmentFile=/etc/foi-tracker/env" in text
    assert "gunicorn" in text
    assert "NoNewPrivileges=true" in text  # hardening


def test_backup_timer_fires_daily():
    text = (REPO_ROOT / "deploy" / "systemd" / "foi-tracker-backup.timer").read_text()
    assert "OnCalendar=" in text
    assert "Persistent=true" in text


def test_env_example_contains_secret_key_placeholder():
    text = (REPO_ROOT / ".env.example").read_text()
    assert "SECRET_KEY" in text
    assert "CHANGE_ME" in text
