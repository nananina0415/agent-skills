#!/usr/bin/env python3
"""First-pass overview parser for a Codex CLI rollout .jsonl file.

Codex rollout files are a flat event stream (not grouped into turns like
Claude Code's jsonl). Each line has {"type": ..., "payload": {...}}; the
interesting ones for an overview are type == "response_item" with
payload.type in ("message", "custom_tool_call", "function_call").

Emits ONE line per interesting item:

    <raw_line_no>\t<kind>\t<short text / tool name>

kind is "user", "assistant", or "tool". "developer"-role messages (Codex's
injected system/instructions) are skipped as noise. Tool call outputs are
skipped too -- only the fact that a tool was called is recorded, matching
the Claude overview's "tool names only" behavior.

Writes the result to a UTF-8 temp file and prints ONLY the file path (plain
ASCII) to stdout.

Usage:
    parse_codex_overview.py <rollout.jsonl>
"""
import json
import sys
import tempfile
from pathlib import Path


def clean(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


def extract_text(content) -> str:
    if not isinstance(content, list):
        return ""
    parts = []
    for c in content:
        if isinstance(c, dict) and "text" in c:
            parts.append(c["text"])
    return clean(" ".join(parts))


def main():
    # Paths can contain non-ASCII characters on some machines (e.g. a
    # Korean username). Reconfigure stdout to UTF-8 with a safe fallback
    # so printing never crashes regardless of the terminal's codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print("ERROR=usage: parse_codex_overview.py <rollout.jsonl>")
        sys.exit(1)

    session_path = Path(sys.argv[1])
    if not session_path.is_file():
        print(f"ERROR=file not found: {session_path}")
        sys.exit(1)

    out_fd, out_path = tempfile.mkstemp(prefix="codex_overview_", suffix=".txt")
    rows = []
    malformed = 0
    guardian_subthread_calls = 0

    with open(session_path, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                d = json.loads(raw_line)
            except Exception:
                malformed += 1
                continue

            if d.get("type") != "response_item":
                continue
            payload = d.get("payload", {})
            ptype = payload.get("type")

            if ptype == "message":
                role = payload.get("role")
                if role == "developer":
                    continue
                text = extract_text(payload.get("content"))
                if role in ("user", "assistant"):
                    rows.append((line_no, role, text))
            elif ptype == "custom_tool_call":
                name = payload.get("name", "?")
                rows.append((line_no, "tool", name))
                if name == "guardian" or "guardian" in name:
                    guardian_subthread_calls += 1
            elif ptype == "function_call":
                name = payload.get("name", "?")
                rows.append((line_no, "tool", name))
            # custom_tool_call_output / function_call_output / reasoning /
            # compaction are intentionally skipped at overview level.

    with open(out_fd, "w", encoding="utf-8") as out:
        out.write(
            f"# TOTAL={len(rows)} SOURCE=codex FILE={session_path} "
            f"MALFORMED_LINES_SKIPPED={malformed} "
            f"GUARDIAN_SUBTHREAD_CALLS={guardian_subthread_calls}\n"
        )
        for line_no, kind, text in rows:
            out.write(f"{line_no}\t{kind}\t{text}\n")

    if malformed > len(rows) and malformed > 20:
        print(f"WARNING=high malformed line count ({malformed}); session format may have changed")

    print(f"OVERVIEW_FILE={out_path}")
    print(f"TOTAL={len(rows)}")


if __name__ == "__main__":
    main()
