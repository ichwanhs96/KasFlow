import os
import subprocess

import pytest

from app.config import ROOT


@pytest.mark.parametrize("script", ["bootstrap.sh", "deploy.sh", "video/stitch.sh"])
def test_shell_scripts_parse_and_are_executable(script):
    path = ROOT / script
    assert os.access(path, os.X_OK), f"{script} is not executable"
    r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_bootstrap_never_commits_secrets_and_keeps_scale_to_zero():
    text = (ROOT / "bootstrap.sh").read_text(encoding="utf-8")
    assert "chmod 600 .env.deploy" in text and ".env.deploy" in (ROOT / ".gitignore").read_text()
    assert "./deploy.sh" in text and "check_gemini.py" in text
    assert "--min-instances 0" in (ROOT / "deploy.sh").read_text(encoding="utf-8")
