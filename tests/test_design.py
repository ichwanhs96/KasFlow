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


def test_collect_page_uses_the_design_system(client):
    c = client.get("/c/some-token").text
    assert 'class="tile"' in c and "icon('camera'" in c and 'rel="icon" href="/static/img/logo.svg"' in c
    assert 'from "/static/js/icons.js"' in client.get("/static/js/collect.js").text


FLAGS = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
EMOJI = re.compile("[\U0001F000-\U0001FAFF⌀-⏿■-◿☀-➿⬀-⯿️‍]")
DOCS = [ROOT / "README.md", ROOT / "SUBMISSION.md", ROOT / "docs" / "pitch-outline.md", ROOT / "video" / "record_demo.ts"]


def checked_files():
    static = sorted(p for p in STATIC_DIR.rglob("*") if p.suffix in {".html", ".js", ".css", ".svg"})
    return static + DOCS


@pytest.mark.parametrize("path", checked_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_emoji_except_country_flags(path):
    text = FLAGS.sub("", path.read_text(encoding="utf-8"))
    found = sorted(set(EMOJI.findall(text)))
    assert not found, f"emoji in {path.relative_to(ROOT)}: {found}"


@pytest.mark.parametrize("page", sorted(STATIC_DIR.rglob("*.html")), ids=lambda p: p.name)
def test_every_page_links_the_favicon(page):
    assert 'rel="icon" href="/static/img/logo.svg"' in page.read_text(encoding="utf-8")


def test_every_icon_used_exists():
    names = icon_names()
    used = set()
    for p in STATIC_DIR.rglob("*"):
        if p.suffix in {".html", ".js"}:
            text = p.read_text(encoding="utf-8")
            used |= set(re.findall(r"""icon\(\s*['"](\w+)['"]""", text))
            for pair in re.findall(r"""icon\([^)]*\?\s*['"](\w+)['"]\s*:\s*['"](\w+)['"]""", text):
                used |= set(pair)  # ternaries such as icon(ok ? 'check' : 'cross')
    kinds = (STATIC_DIR / "js" / "console.js").read_text(encoding="utf-8").split("const KIND_ICON = {", 1)[1].split("};", 1)[0]
    used |= set(re.findall(r'"(\w+)"', kinds))  # values of { open_finance: "bank", ... }
    assert {"bank", "wallet", "camera", "upload", "plug"} <= used
    assert used <= names, used - names


def test_no_os_junk_files_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if f.endswith(".DS_Store")]
    assert ".DS_Store" in (ROOT / ".gitignore").read_text().split()


def test_no_background_polling_keeps_cloud_run_awake():
    # Cloud Run scales to zero; a forgotten browser tab must never keep an instance alive.
    for p in STATIC_DIR.rglob("*.js"):
        assert "setInterval" not in p.read_text(encoding="utf-8"), p.name
    deploy = (ROOT / "deploy.sh").read_text(encoding="utf-8")
    assert "--min-instances 0" in deploy and "--cpu-boost" in deploy


def test_console_has_manual_refresh(client):
    assert 'data-testid="refresh"' in client.get("/console").text
