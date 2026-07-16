"""OPS-8: static checks on aspirational deploy artefacts.

These files are demonstrative — they aren't applied. The tests here just make
sure they parse, and that every file has the "not applied" disclaimer so a
future reader can't mistake them for production config.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "deploy" / "k8s"
TF_DIR = REPO_ROOT / "deploy" / "terraform"


def _read(path: Path) -> str:
    return path.read_text()


def test_k8s_readme_and_manifests_exist():
    assert (K8S_DIR / "README.md").exists()
    for name in (
        "deployment.yaml",
        "service.yaml",
        "configmap.yaml",
        "secret.yaml.example",
        "pvc.yaml",
    ):
        assert (K8S_DIR / name).exists(), f"missing k8s/{name}"


def test_terraform_files_exist():
    assert (TF_DIR / "README.md").exists()
    for name in ("main.tf", "variables.tf", "outputs.tf"):
        assert (TF_DIR / name).exists(), f"missing terraform/{name}"


def test_deploy_top_readme_points_to_both():
    text = _read(REPO_ROOT / "deploy" / "README.md")
    assert "k8s/" in text
    assert "terraform/" in text
    assert "systemd/" in text


@pytest.mark.parametrize(
    "path",
    [
        K8S_DIR / "README.md",
        K8S_DIR / "deployment.yaml",
        K8S_DIR / "service.yaml",
        K8S_DIR / "configmap.yaml",
        K8S_DIR / "secret.yaml.example",
        K8S_DIR / "pvc.yaml",
        TF_DIR / "README.md",
        TF_DIR / "main.tf",
        TF_DIR / "variables.tf",
        TF_DIR / "outputs.tf",
    ],
)
def test_every_aspirational_file_carries_the_disclaimer(path):
    """Case-insensitive check for 'aspirational' anywhere in the file."""
    assert "aspirational" in _read(path).lower(), (
        f"{path.relative_to(REPO_ROOT)} is missing the 'aspirational' disclaimer"
    )


def test_k8s_yaml_files_parse():
    yaml = pytest.importorskip("yaml")
    for path in K8S_DIR.glob("*.yaml"):
        for doc in yaml.safe_load_all(path.read_text()):
            # Some manifests contain multiple docs (e.g. pvc.yaml has two).
            # Every non-empty doc must at least be a dict with a `kind`.
            if doc is None:
                continue
            assert isinstance(doc, dict), f"{path.name} contains a non-dict document"
            assert "kind" in doc, f"{path.name} document is missing `kind`"


def test_k8s_deployment_probes_healthz():
    text = _read(K8S_DIR / "deployment.yaml")
    assert "/api/healthz" in text
    assert "readinessProbe" in text
    assert "livenessProbe" in text
    assert "runAsNonRoot" in text


def test_k8s_deployment_is_recreate_strategy():
    """SQLite is single-writer; rolling update would double-write."""
    text = _read(K8S_DIR / "deployment.yaml")
    assert "Recreate" in text


def test_terraform_main_names_expected_resources():
    text = _read(TF_DIR / "main.tf")
    for expected in (
        "aws_s3_bucket",
        "aws_s3_bucket_versioning",
        "aws_ebs_volume",
        "aws_instance",
        "aws_iam_role",
        "aws_security_group",
    ):
        assert expected in text, f"terraform/main.tf missing resource `{expected}`"


def test_terraform_backup_bucket_blocks_public_access():
    text = _read(TF_DIR / "main.tf")
    assert "aws_s3_bucket_public_access_block" in text
    assert "block_public_acls       = true" in text or "block_public_acls = true" in text


def test_k8s_secret_example_does_not_hold_a_real_key():
    """The .example file must not accidentally contain a real 64-char hex."""
    import re

    text = _read(K8S_DIR / "secret.yaml.example")
    # A committed real key would be a base64 encoding of 64 hex chars — ~88
    # base64 chars ending in `=`. Assert the stub isn't that shape by
    # requiring the placeholder marker instead.
    assert "replace this" in text.lower() or "base64-encoded" in text.lower()
    # Belt-and-braces: reject anything that looks like a real 64-hex key
    # directly in the yaml body (i.e. not inside a comment).
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        assert not re.search(r"[0-9a-f]{64}", line), (
            f"secret.yaml.example appears to contain a real hex key: {line}"
        )
