import re
import shutil
import subprocess

import pytest

from app.config import ROOT, STATIC_DIR

SPEC_ICONS = {"bank", "wallet", "document", "camera", "plug", "upload", "warning", "check", "cross", "chevron",
              "signout", "clock"}


def icon_names() -> set[str]:
    src = (STATIC_DIR / "js" / "icons.js").read_text(encoding="utf-8")
    body = src.split("const PATHS = {", 1)[1].split("};", 1)[0]
    return set(re.findall(r"^\s+(\w+):", body, re.M))


def test_icon_set_matches_spec():
    assert SPEC_ICONS <= icon_names()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_icon_unknown_name_falls_back():
    js = ("import { icon, ICON_NAMES } from './app/static/js/icons.js';"
          "const s = icon('<img onerror=x>');"
          "if (s.includes('onerror') || !s.startsWith('<svg') || s !== icon('document')) process.exit(1);"
          "if (!icon('bank', 24).includes('width=\"24\"') || ICON_NAMES.length < 12) process.exit(2);")
    r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_logo_and_favicon_served(client):
    r = client.get("/static/img/logo.svg")
    assert r.status_code == 200 and "<svg" in r.text and "#4A7FC1" in r.text and "#3FA37A" in r.text
    f = client.get("/favicon.ico")
    assert f.status_code == 200 and f.headers["content-type"].startswith("image/svg+xml")


def test_console_and_signin_use_the_design_system(client):
    c = client.get("/console").text
    assert 'class="topbar"' in c and 'src="/static/img/logo.svg"' in c and "x-html=\"icon(" in c
    assert 'rel="icon" href="/static/img/logo.svg"' in c
    i = client.get("/").text
    assert 'class="topbar"' in i and "Sign in with Google" in i and 'rel="icon" href="/static/img/logo.svg"' in i
    js = client.get("/static/js/console.js").text
    assert 'from "/static/js/icons.js"' in js and "label-pos" in js
    assert 'rel="icon" href="/static/img/logo.svg"' in client.get("/demo-login").text
