"""Checks for the local deploy scripts. They are gitignored (kept out of the public repo), so a clean clone skips these."""
import os
import subprocess

import pytest

from app.config import ROOT


def local_script(name):
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} is a local-only deploy script (gitignored)")
    return path


@pytest.mark.parametrize("script", ["bootstrap.sh", "deploy.sh", "video/stitch.sh"])
def test_shell_scripts_parse_and_are_executable(script):
    path = local_script(script)
    assert os.access(path, os.X_OK), f"{script} is not executable"
    r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_deploy_scales_to_zero():
    deploy = local_script("deploy.sh").read_text(encoding="utf-8")
    assert "--min-instances 0" in deploy and "--cpu-boost" in deploy


def test_bootstrap_never_commits_secrets():
    text = local_script("bootstrap.sh").read_text(encoding="utf-8")
    assert "chmod 600 .env.deploy" in text and ".env.deploy" in (ROOT / ".gitignore").read_text()
    assert "./deploy.sh" in text and "check_gemini.py" in text


def test_local_deploy_files_are_gitignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    for name in ("bootstrap.sh", "deploy.sh", "scripts/seed.py", "scripts/smoke.py", "scripts/check_gemini.py", "ACCESS.md"):
        assert name in ignored, name
