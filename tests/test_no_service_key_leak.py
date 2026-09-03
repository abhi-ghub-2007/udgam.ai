"""A-12 guard: the service-role key stays confined to two files, and no
Supabase key of any kind is ever hardcoded into a frontend file.

This is the automated form of the execution prompt's "ZERO secret exposure
on frontend" rule. It runs in CI and fails the build, rather than relying on
anyone remembering.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Declaring the setting is not the same as reading it. config.py must name
# the field for pydantic-settings to load it at all; what A-12 constrains is
# who may *use* the value.
DECLARATION_SITE = Path("backend/app/config.py")

# The only modules permitted to read the service-role key.
ALLOWED = {
    DECLARATION_SITE,
    Path("backend/app/db/admin_client.py"),
    Path("backend/scripts/seed_demo.py"),
    Path("scripts/seed_demo.py"),
}

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "Udgam-tools",
             ".claude", "design_reference", "tests"}

SERVICE_KEY = re.compile(r"SUPABASE_SERVICE_ROLE_KEY")
# A real Supabase key is a JWT: three dot-separated base64url segments.
JWT_SHAPE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")


def _files(*exts: str):
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in exts:
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        yield p


def test_service_role_key_confined_to_allowed_modules():
    offenders = []
    for p in _files(".py", ".js", ".html", ".css", ".json", ".md", ".sql"):
        rel = p.relative_to(ROOT)
        if rel in ALLOWED or rel.name in {".env.example", "ASSUMPTIONS.md"}:
            continue
        if SERVICE_KEY.search(p.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(rel))
    assert not offenders, (
        "SUPABASE_SERVICE_ROLE_KEY referenced outside the two allowed modules "
        f"(A-12): {offenders}"
    )


def test_no_hardcoded_keys_in_frontend():
    frontend = ROOT / "frontend"
    if not frontend.exists():
        return
    offenders = []
    for p in frontend.rglob("*"):
        if not p.is_file() or p.suffix not in {".js", ".html", ".css", ".json"}:
            continue
        if "vendor" in p.parts:          # third-party bundle, not our code
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if JWT_SHAPE.search(text) or SERVICE_KEY.search(text):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"Hardcoded key material found in frontend: {offenders}"


def test_env_is_gitignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [line.strip() for line in ignored], ".env must be gitignored"
