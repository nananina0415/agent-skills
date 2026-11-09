#!/usr/bin/env python3
"""Find the session that was active right before the current session started.

The current session is the caller's session with the latest event. Candidates
are compared by their last event before the current session's first event, so
a session used in parallel cannot outrank the one the user just left. Times
come from the "timestamp" field inside each file because file mtimes do not
track activity in Codex rollout files.

Prints plain ASCII key=value lines to stdout (no Korean, no JSON) so the
caller never has to deal with console-encoding issues. On failure, prints
ERROR=<message> and exits with a non-zero status.

Usage:
    find_latest_session.py --agent claude|codex --source claude|codex|both [--cwd <path>]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def encode_cwd(cwd: str) -> str:
    """Reproduce Claude Code's project-directory encoding rule.

    Claude Code stores session logs under a directory named after the
    working directory, with each of ':', '\\', '/' replaced by '-'.
    Example: C:\\Users\\x\\proj -> C--Users-x-proj
    """
    return "".join("-" if c in (":", "\\", "/") else c for c in cwd)


def read_event_times(path: Path):
    """Return every parsable event time in a session file, as epoch seconds."""
    times = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                raw = json.loads(line).get("timestamp")
                times.append(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
            except (ValueError, AttributeError, TypeError):
                continue
    return times


def find_claude_files(cwd: str):
    projects_dir = Path.home() / ".claude" / "projects" / encode_cwd(cwd)
    if not projects_dir.is_dir():
        return [], {"error": f"claude project dir not found: {projects_dir}"}

    files = [p for p in projects_dir.glob("*.jsonl") if p.is_file()]
    return files, {"dir": str(projects_dir), "total_candidates": len(files)}


def find_codex_files(cwd: str):
    base = Path.home() / ".codex" / "sessions"
    files = sorted(base.glob("*/*/*/rollout-*.jsonl"))
    if not files:
        return [], {"error": f"no codex rollout files under {base}"}

    candidates = []
    excluded_subagent = 0
    excluded_other_cwd = 0
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

        # guardian_review threads and spawned agents both carry source.subagent.
        source = payload.get("source")
        if isinstance(source, dict) and "subagent" in source:
            excluded_subagent += 1
            continue
        if os.path.normcase(payload.get("cwd", "")) != os.path.normcase(cwd):
            excluded_other_cwd += 1
            continue
        candidates.append(f)

    return candidates, {
        "dir": str(base),
        "excluded_subagent": excluded_subagent,
        "excluded_other_cwd": excluded_other_cwd,
        "unreadable": unreadable,
        "total_candidates": len(candidates),
    }


def to_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def print_diagnostics(diagnostics):
    for src, info in diagnostics.items():
        for k, v in info.items():
            print(f"{src.upper()}_{k.upper()}={v}")


def main():
    # Paths can contain non-ASCII characters on some machines (e.g. a
    # Korean username). Reconfigure stdout to UTF-8 with a safe fallback
    # so printing never crashes regardless of the terminal's codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["claude", "codex"], required=True,
                    help="The agent running this script; its latest session is the current one")
    ap.add_argument("--source", choices=["claude", "codex", "both"], default="both")
    ap.add_argument("--cwd", default=None, help="Project cwd to match sessions against (defaults to current dir)")
    args = ap.parse_args()

    cwd = args.cwd or os.getcwd()
    sources = ["claude", "codex"] if args.source == "both" else [args.source]
    finders = {"claude": find_claude_files, "codex": find_codex_files}

    # The caller's side is always loaded because it defines the current session.
    sessions = {}
    diagnostics = {}
    for src in dict.fromkeys(sources + [args.agent]):
        files, diagnostics[src] = finders[src](cwd)
        timed = [(f, read_event_times(f)) for f in files]
        sessions[src] = [(f, times) for f, times in timed if times]

    if not sessions[args.agent]:
        print(f"ERROR=no {args.agent} session found to treat as the current session")
        print_diagnostics(diagnostics)
        sys.exit(1)

    current_file, current_times = max(sessions[args.agent], key=lambda s: max(s[1]))
    current_start = min(current_times)

    chosen_file = None
    chosen_source = None
    chosen_time = None
    for src in sources:
        for f, times in sessions[src]:
            if f == current_file:
                continue
            before_start = [t for t in times if t < current_start]
            if before_start and (chosen_time is None or max(before_start) > chosen_time):
                chosen_file, chosen_source, chosen_time = f, src, max(before_start)

    if chosen_file is None:
        print("ERROR=no session has activity before the current session started")
        print(f"CURRENT_FILE={current_file}")
        print(f"CURRENT_START={to_iso(current_start)}")
        print_diagnostics(diagnostics)
        sys.exit(1)

    print(f"FILE={chosen_file}")
    print(f"SOURCE={chosen_source}")
    print(f"LAST_ACTIVITY={to_iso(chosen_time)}")
    print(f"CURRENT_FILE={current_file}")
    print(f"CURRENT_START={to_iso(current_start)}")
    print_diagnostics(diagnostics)


if __name__ == "__main__":
    main()
