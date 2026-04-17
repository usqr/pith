#!/usr/bin/env python3
"""
/pith update — check for and apply a new Pith release.

Modes
-----
    --check   Print what would change without touching anything.
    --apply   Fetch + checkout the resolved ref and re-run install.sh.
              Prints hook-file hash deltas before proceeding.
    --list    Show available tags (newest first).

Supply-chain safety
-------------------
Honours the same env vars as `install.sh`:

    PITH_REF              tag/branch/commit to install (else: latest tag, else: main)
    PITH_PIN_SHA          abort unless the resolved HEAD matches this SHA
    PITH_VERIFY_GPG=1     require a signed tag

The installed ref + SHA is persisted to ~/.config/pith/config.json by
install.sh and shown by this tool so /pith status can display version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


CONFIG_PATH = Path.home() / ".config" / "pith" / "config.json"
HOOK_FILES = [
    "hooks/session-start.js",
    "hooks/post-tool-use.js",
    "hooks/prompt-submit.js",
    "hooks/stop.js",
    "hooks/config.js",
    "hooks/statusline.sh",
]
INSTALLED_HOOKS_DIR = Path.home() / ".claude" / "hooks" / "pith"


class UpdateError(RuntimeError):
    pass


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def _plugin_root() -> Path:
    cfg = _load_config()
    root = cfg.get("plugin_root") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        raise UpdateError(
            "Could not resolve plugin root. Re-run install.sh to refresh "
            "~/.config/pith/config.json, or set CLAUDE_PLUGIN_ROOT."
        )
    p = Path(root)
    if not (p / ".git").exists():
        raise UpdateError(
            f"Plugin root {p} is not a git checkout — /pith update only "
            "works when Pith was installed from a clone of the repo."
        )
    return p


def _git(root: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=60,
    )
    if check and r.returncode != 0:
        raise UpdateError(
            f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}"
        )
    return r.stdout.strip()


def _latest_tag(root: Path) -> str | None:
    _git(root, "fetch", "--quiet", "--tags", "origin", check=False)
    out = _git(root, "tag", "--sort=-v:refname", check=False)
    for line in out.splitlines():
        t = line.strip()
        if t:
            return t
    return None


def _resolve_ref(root: Path, env_ref: str | None) -> tuple[str, str]:
    """Return (ref, sha) for the update target."""
    target_ref = env_ref or _latest_tag(root) or "main"
    _git(root, "fetch", "--quiet", "origin", check=False)
    sha = _git(root, "rev-parse", target_ref)
    return target_ref, sha


def _hash_file(p: Path) -> tuple[str, int] | None:
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        return None
    return hashlib.sha256(data).hexdigest(), len(data)


def _hook_hashes(base: Path, file_list: list[str]) -> dict[str, tuple[str, int] | None]:
    return {f: _hash_file(base / f) for f in file_list}


def _render_hash_diff(before: dict, after: dict) -> str:
    lines = []
    for key in before:
        b = before[key]
        a = after[key]
        if b == a:
            lines.append(f"  = {key}  unchanged")
        elif b is None:
            lines.append(f"  + {key}  (new, {a[1]} bytes, {a[0][:12]}…)")
        elif a is None:
            lines.append(f"  - {key}  removed")
        else:
            lines.append(
                f"  ~ {key}  {b[0][:12]}… → {a[0][:12]}…  "
                f"({b[1]} → {a[1]} bytes)"
            )
    return "\n".join(lines)


def _verify_gpg(root: Path, ref: str) -> None:
    # Only meaningful for tags.
    tags = _git(root, "tag", "-l", ref)
    if not tags.strip():
        raise UpdateError(
            f"PITH_VERIFY_GPG=1 set but {ref!r} is not a tag."
        )
    r = subprocess.run(
        ["git", "-C", str(root), "verify-tag", ref],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise UpdateError(
            f"Tag {ref} failed GPG verification: {r.stderr.strip()}"
        )


def _verify_pin(sha: str) -> None:
    pin = os.environ.get("PITH_PIN_SHA")
    if pin and sha != pin:
        raise UpdateError(
            f"Resolved SHA {sha} does not match PITH_PIN_SHA {pin} — aborting."
        )


def check() -> int:
    root = _plugin_root()
    cur_sha = _git(root, "rev-parse", "HEAD")
    env_ref = os.environ.get("PITH_REF")
    target_ref, target_sha = _resolve_ref(root, env_ref)

    print(f"PITH UPDATE — check")
    print(f"  plugin root:  {root}")
    print(f"  current:      {cur_sha}")
    print(f"  target ref:   {target_ref}")
    print(f"  target sha:   {target_sha}")

    if cur_sha == target_sha:
        print("  status:       up to date ✓")
        return 0

    # Show commit list.
    log = _git(root, "log", "--oneline", f"{cur_sha}..{target_sha}", check=False)
    print()
    print(f"  commits ahead: {len(log.splitlines()) if log else 0}")
    if log:
        print("  new commits:")
        for line in log.splitlines()[:20]:
            print(f"    · {line}")
        extra = len(log.splitlines()) - 20
        if extra > 0:
            print(f"    · …{extra} more")
    print()

    # Hook hash diff: compare the currently-installed hooks against what
    # the target tree would produce.
    current_hashes = _hook_hashes(root, HOOK_FILES)

    # For target hashes, we don't want to actually check out — use
    # `git show <sha>:path` to pull file contents without touching the worktree.
    target_hashes = {}
    for rel in HOOK_FILES:
        r = subprocess.run(
            ["git", "-C", str(root), "show", f"{target_sha}:{rel}"],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0:
            data = r.stdout
            target_hashes[rel] = (hashlib.sha256(data).hexdigest(), len(data))
        else:
            target_hashes[rel] = None

    print("  hook file changes (current checkout → target):")
    print(_render_hash_diff(current_hashes, target_hashes))

    print()
    print("  installed hashes (~/.claude/hooks/pith/):")
    installed_hashes = _hook_hashes(INSTALLED_HOOKS_DIR, [
        Path(f).name for f in HOOK_FILES
    ])
    for name, val in installed_hashes.items():
        if val is None:
            print(f"    ? {name}  (not installed?)")
        else:
            print(f"    · {name}  {val[0][:12]}…  ({val[1]} bytes)")

    print()
    print("Run `/pith update --apply` to install target ref.")
    if os.environ.get("PITH_VERIFY_GPG") == "1":
        print("    (PITH_VERIFY_GPG=1 set — target must be a signed tag)")
    return 0


def apply() -> int:
    root = _plugin_root()
    env_ref = os.environ.get("PITH_REF")
    target_ref, target_sha = _resolve_ref(root, env_ref)
    _verify_pin(target_sha)
    if os.environ.get("PITH_VERIFY_GPG") == "1":
        _verify_gpg(root, target_ref)

    print(f"PITH UPDATE — applying {target_ref} ({target_sha[:12]}…)")

    # Refuse to wreck a dirty tree.
    status = _git(root, "status", "--porcelain")
    if status:
        raise UpdateError(
            "Plugin-root checkout has uncommitted changes — resolve them first:\n"
            + status
        )

    _git(root, "checkout", target_ref)

    # Re-run install.sh to copy the fresh hooks into ~/.claude/hooks/pith/.
    install_sh = root / "install.sh"
    if not install_sh.exists():
        raise UpdateError(f"No install.sh at {install_sh}")

    env = {**os.environ, "PITH_REF": target_ref}
    r = subprocess.run(["bash", str(install_sh)], env=env, timeout=120)
    if r.returncode != 0:
        raise UpdateError(f"install.sh exited {r.returncode}")

    print(f"\n✓ Pith updated to {target_ref}.")
    return 0


def list_tags() -> int:
    root = _plugin_root()
    _git(root, "fetch", "--quiet", "--tags", "origin", check=False)
    tags = _git(root, "tag", "--sort=-v:refname", check=False)
    if not tags:
        print("No tags found in plugin root.")
        return 0
    print("Available tags (newest first):")
    for line in tags.splitlines()[:20]:
        print(f"  · {line}")
    if len(tags.splitlines()) > 20:
        print(f"  · …{len(tags.splitlines()) - 20} more")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--list", action="store_true")
    args = p.parse_args()

    try:
        if args.apply:
            return apply()
        if args.list:
            return list_tags()
        # Default: check. --check is explicit for scripts that want to be sure.
        return check()
    except UpdateError as exc:
        print(f"[PITH UPDATE ERROR] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[aborted]", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
