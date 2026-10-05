#!/usr/bin/env python3
"""Find the most recent Claude Code and/or Codex CLI session file.

Prints plain ASCII key=value lines to stdout (no Korean, no JSON) so the
caller never has to deal with console-encoding issues. On failure, prints
ERROR=<message> and exits with a non-zero status.

Usage:
    find_latest_session.py --agent claude|codex --source claude|codex|both [--cwd <path>]
"""
import argparse
import json
import sys
from pathlib import Path


def encode_cwd(cwd: str) -> str:
    """Reproduce Claude Code's project-directory encoding rule.

    Claude Code stores session logs under a directory named after the
    working directory, with each of ':', '\\', '/' replaced by '-'.
    Example: C:\\Users\\x\\proj -> C--Users-x-proj
    """
    return "".join("-" if c in (":", "\\", "/") else c for c in cwd)


def find_claude_candidate(cwd: str, exclude_current: bool):
    projects_dir = Path.home() / ".claude" / "projects" / encode_cwd(cwd)
    if not projects_dir.is_dir():
        return None, {"error": f"claude project dir not found: {projects_dir}"}

    files = [p for p in projects_dir.glob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    required = 2 if exclude_current else 1
    if len(files) < required:
        return None, {
            "error": (
                f"need at least {required} claude session files, "
                f"found {len(files)} in {projects_dir}"
            )
        }

    # Only a Claude caller has a current Claude session to exclude.
    chosen = files[1] if exclude_current else files[0]
    return chosen, {"dir": str(projects_dir), "total_files": len(files)}


def find_codex_candidate(exclude_current: bool):
    base = Path.home() / ".codex" / "sessions"
    files = sorted(base.glob("*/*/*/rollout-*.jsonl"))
    if not files:
        return None, {"error": f"no codex rollout files under {base}"}

    candidates = []
    excluded_guardian = 0
    unreadable = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                first_line = fh.readline()
            meta = json.loads(first_line)
            payload = meta.get("payload", {})
        except Exception:
            unreadable += 1
            continue

        if payload.get("thread_source") == "guardian_review":
            excluded_guardian += 1
            continue
        candidates.append(f)

    required = 2 if exclude_current else 1
    if len(candidates) < required:
        return None, {
            "error": (
                f"need at least {required} non-guardian_review codex session files, "
                f"found {len(candidates)}"
            ),
            "excluded_guardian_review": excluded_guardian,
            "unreadable": unreadable,
        }

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    chosen = candidates[1] if exclude_current else candidates[0]
    return chosen, {
        "dir": str(base),
        "excluded_guardian_review": excluded_guardian,
        "unreadable": unreadable,
        "total_candidates": len(candidates),
    }


def main():
    # Paths can contain non-ASCII characters on some machines (e.g. a
    # Korean username). Reconfigure stdout to UTF-8 with a safe fallback
    # so printing never crashes regardless of the terminal's codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["claude", "codex"], required=True,
                    help="The agent running this script; its current session is excluded")
    ap.add_argument("--source", choices=["claude", "codex", "both"], default="both")
    ap.add_argument("--cwd", default=None, help="Project cwd for Claude session lookup (defaults to current dir)")
    args = ap.parse_args()

    import os

    cwd = args.cwd or os.getcwd()

    chosen_file = None
    chosen_source = None
    chosen_mtime = -1.0
    diagnostics = {}

    if args.source in ("claude", "both"):
        f, info = find_claude_candidate(cwd, exclude_current=args.agent == "claude")
        diagnostics["claude"] = info
        if f is not None:
            mtime = f.stat().st_mtime
            if mtime > chosen_mtime:
                chosen_file, chosen_source, chosen_mtime = f, "claude", mtime

    if args.source in ("codex", "both"):
        f, info = find_codex_candidate(exclude_current=args.agent == "codex")
        diagnostics["codex"] = info
        if f is not None:
            mtime = f.stat().st_mtime
            if mtime > chosen_mtime:
                chosen_file, chosen_source, chosen_mtime = f, "codex", mtime

    if chosen_file is None:
        print("ERROR=no candidate session file found")
        for src, info in diagnostics.items():
            if "error" in info:
                print(f"ERROR_{src.upper()}={info['error']}")
        sys.exit(1)

    print(f"FILE={chosen_file}")
    print(f"SOURCE={chosen_source}")
    for src, info in diagnostics.items():
        for k, v in info.items():
            if k == "error":
                continue
            print(f"{src.upper()}_{k.upper()}={v}")


if __name__ == "__main__":
    main()
