#!/usr/bin/env python3
"""Validate every bike setup package under setups/ and write index.json.

Usage:
    python3 tools/build_index.py           # validate + write index.json
    python3 tools/build_index.py --check   # validate only, exit 1 on any problem

Only the structure is checked here: ZIP entries, size, manifest fields and the JSON types of
the setup sections. The app validates every value against its own allow-list when a rider
imports a package, so this script does not know the enum values.
"""
import hashlib
import io
import json
import re
import sys
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUPS = ROOT / "setups"
INDEX = ROOT / "index.json"
# Maintainer-owned list of verified setup ids. Packages cannot set this themselves.
VERIFIED = ROOT / "verified.json"

MAX_BYTES = 2 * 1024 * 1024
# shortcut: caps ZIP expansion (zip bomb) at 16 MB, not in the contract, raise if a real package needs more
MAX_UNPACKED = 16 * 1024 * 1024
FORMAT = "moto-hub/bike-setup"
SCHEMA = 1
REQUIRED_ENTRIES = {"manifest.json", "setup.json"}
ALLOWED_ENTRIES = REQUIRED_ENTRIES | {"dashboard.mhd"}
SECTIONS = ("connection", "video", "androidAuto", "screen", "link", "handlebar", "dashboard")
ID = re.compile(r"^[a-z0-9-]{3,64}$")
# Keys that would carry a rider's network name or password: refused anywhere in the manifest or setup.
PERSONAL_KEY_PARTS = ("ssid", "password")


def rel(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def fail(problems, path, message):
    problems.append(f"{rel(path)}: {message}")


def load_verified(problems):
    """Returns the set of verified setup ids from verified.json; reports a broken file."""
    try:
        value = json.loads(VERIFIED.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        problems.append(f"{rel(VERIFIED)}: cannot read: {e}")
        return set()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        problems.append(f"{rel(VERIFIED)}: must be a JSON array of setup ids")
        return set()
    return set(value)


def text_field(obj, key):
    value = obj.get(key)
    return value.strip() if isinstance(value, str) else ""


def personal_keys(node, found):
    if isinstance(node, dict):
        for key, value in node.items():
            if any(part in str(key).lower() for part in PERSONAL_KEY_PARTS):
                found.append(str(key))
            personal_keys(value, found)
    elif isinstance(node, list):
        for item in node:
            personal_keys(item, found)
    return found


def json_object(contents, name, path, problems):
    """Parses one required JSON entry; returns None (and reports) when it is not an object."""
    if name not in contents:
        return None
    try:
        value = json.loads(contents[name].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        fail(problems, path, f"{name} is not valid JSON: {e}")
        return None
    if not isinstance(value, dict):
        fail(problems, path, f"{name} top level must be an object")
        return None
    return value


def validate_package(path, problems, verified=frozenset()):
    """Returns the index entry when the package is acceptable, else None."""
    before = len(problems)
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        fail(problems, path, f"file is {len(raw)} bytes, limit is {MAX_BYTES}")
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            infos = zf.infolist()
            if sum(info.file_size for info in infos) > MAX_UNPACKED:
                fail(problems, path, f"unpacked size is over {MAX_UNPACKED} bytes")
                return None
            names = [info.filename for info in infos]
            contents = {n: zf.read(n) for n in names if n in ALLOWED_ENTRIES}
    except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as e:
        fail(problems, path, f"not a readable ZIP: {e}")
        return None

    if len(set(names)) != len(names):
        fail(problems, path, "ZIP has a repeated entry name")
    for name in names:
        if name not in ALLOWED_ENTRIES:
            fail(problems, path, f"unexpected ZIP entry {name!r}; only manifest.json, setup.json and dashboard.mhd are allowed")
    for name in sorted(REQUIRED_ENTRIES - set(names)):
        fail(problems, path, f"missing {name}")

    manifest = json_object(contents, "manifest.json", path, problems)
    setup = json_object(contents, "setup.json", path, problems)
    if manifest is None or setup is None:
        return None

    if manifest.get("format") != FORMAT:
        fail(problems, path, f"manifest format must be {FORMAT!r}")
    schema = manifest.get("schema")
    if type(schema) is not int or schema != SCHEMA:
        fail(problems, path, "manifest schema must be 1")
    pid = manifest.get("id")
    if not isinstance(pid, str) or not ID.match(pid):
        fail(problems, path, "manifest id must match [a-z0-9-]{3,64}")
    elif path.name != f"{pid}.mhp":
        fail(problems, path, f"file name must be {pid}.mhp")
    for key in ("name", "brand", "model"):
        if not text_field(manifest, key):
            fail(problems, path, f"manifest {key} is required")

    leaked = sorted(set(personal_keys(manifest, []) + personal_keys(setup, [])))
    if leaked:
        fail(problems, path, f"keys {leaked} are not allowed: packages never carry Wi-Fi names or passwords")

    for key in SECTIONS:
        if key in setup and not isinstance(setup[key], dict):
            fail(problems, path, f"setup.{key} must be an object")
    dashboard = setup.get("dashboard") if isinstance(setup.get("dashboard"), dict) else {}
    ref = dashboard.get("catalogueRef")
    if ref is not None and not isinstance(ref, str):
        fail(problems, path, "setup.dashboard.catalogueRef must be a string or null")
    dashboard_ref = ref.strip() if isinstance(ref, str) and ref.strip() else None
    has_mhd = "dashboard.mhd" in contents
    if dashboard_ref and has_mhd:
        fail(problems, path, "dashboard.mhd must be absent when setup.dashboard.catalogueRef is set")

    if len(problems) != before:
        return None
    model_id = manifest.get("modelId")
    return {
        "id": pid,
        "name": text_field(manifest, "name"),
        "brand": text_field(manifest, "brand"),
        "model": text_field(manifest, "model"),
        "years": text_field(manifest, "years"),
        "tft": text_field(manifest, "tft"),
        "modelId": model_id if isinstance(model_id, str) else None,
        "path": rel(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "sections": [key for key in SECTIONS if key in setup],
        "hasDashboard": has_mhd or dashboard_ref is not None,
        "dashboardRef": dashboard_ref,
        "author": text_field(manifest, "author"),
        "notes": text_field(manifest, "notes"),
        "app": text_field(manifest, "app"),
        "phone": text_field(manifest, "phone"),
        "verified": pid in verified,
    }


def build():
    problems, entries, seen_ids = [], [], {}
    verified = load_verified(problems)
    if SETUPS.is_dir():
        for path in sorted(SETUPS.rglob("*.mhp")):
            entry = validate_package(path, problems, verified)
            if entry is None:
                continue
            if entry["id"] in seen_ids:
                fail(problems, path, f"id {entry['id']!r} already used by {seen_ids[entry['id']]}")
                continue
            seen_ids[entry["id"]] = entry["path"]
            entries.append(entry)
    entries.sort(key=lambda e: (e["brand"].lower(), e["name"].lower(), e["id"]))
    return problems, entries


def main(argv):
    check_only = "--check" in argv
    problems, entries = build()
    for problem in problems:
        print(f"ERROR {problem}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s), {len(entries)} setup(s) valid", file=sys.stderr)
        return 1
    print(f"{len(entries)} setup(s) valid")
    if check_only:
        return 0
    previous = None
    if INDEX.exists():
        try:
            previous = json.loads(INDEX.read_text("utf-8"))
        except json.JSONDecodeError:
            previous = None
    # Keep generatedAt stable when nothing else changed, so the Action does not commit every run.
    if previous and previous.get("setups") == entries and previous.get("schema") == 1:
        print("index.json unchanged")
        return 0
    index = {
        "schema": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "setups": entries,
    }
    INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
