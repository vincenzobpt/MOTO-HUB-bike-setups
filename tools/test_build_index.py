#!/usr/bin/env python3
"""Self-check for build_index.py: one valid package passes, two broken ones fail.

Usage:
    python3 -I tools/test_build_index.py
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index  # noqa: E402

MANIFEST = {
    "format": "moto-hub/bike-setup", "schema": 1, "id": "cfmoto-700mt-2024-tft7",
    "name": "CFMOTO 700MT 2024", "brand": "CFMOTO", "model": "700MT", "years": "2024",
    "tft": "7\" landscape", "modelId": None, "author": "", "notes": "",
    "app": "0.1.58 (123)", "phone": "OnePlus CPH2653", "createdAt": "2026-11-11T10:00:00Z",
}
SETUP = {
    "connection": {"mode": "AUTO"},
    "video": {"quality": "BALANCED"},
    "dashboard": {"id": "stock", "builtin": True, "catalogueRef": None},
}


def make_package(folder, manifest, setup, extra=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{manifest['id']}.mhp"
    entries = {"manifest.json": json.dumps(manifest), "setup.json": json.dumps(setup)}
    entries.update(extra or {})
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def validate(path):
    problems = []
    entry = build_index.validate_package(path, problems)
    return entry, problems


with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp) / "setups" / "cfmoto"

    good = make_package(folder, MANIFEST, SETUP)
    entry, problems = validate(good)
    assert problems == [], problems
    assert entry["id"] == "cfmoto-700mt-2024-tft7"
    assert entry["sections"] == ["connection", "video", "dashboard"]
    assert entry["hasDashboard"] is False and entry["dashboardRef"] is None
    print("ok 1: valid package passes")

    extra_manifest = dict(MANIFEST, id="cfmoto-extra-entry")
    extra = make_package(folder, extra_manifest, SETUP, extra={"photo.jpg": "not allowed"})
    entry, problems = validate(extra)
    assert entry is None
    assert any("unexpected ZIP entry 'photo.jpg'" in p for p in problems), problems
    print("ok 2: extra ZIP entry fails")

    leaky_setup = {"link": {"password": "test-only"}}
    leaky = make_package(folder, dict(MANIFEST, id="cfmoto-leaky-one"), leaky_setup)
    entry, problems = validate(leaky)
    assert entry is None
    assert any("not allowed" in p and "password" in p for p in problems), problems
    print("ok 3: password key fails")

    claimed = make_package(folder, dict(MANIFEST, id="cfmoto-self-verified", verified=True), SETUP)
    entry, problems = validate(claimed)
    assert problems == [] and entry["verified"] is False, (entry, problems)
    print("ok 4: manifest verified:true is indexed as unverified")

print("4 checks passed")
