#!/usr/bin/env python3
"""First-pass overview parser for a Claude Code session .jsonl file.

For every top-level turn, emits ONE line:

    <raw_line_no>\t<role>\t<short text summary>\t<tool names, comma separated or "->">

Deliberately excludes full tool input/output and full assistant text -- only
enough to let a human (or Claude itself) see "what happened" and decide
whether a deeper, range-scoped detail pass is needed.

Writes the result to a UTF-8 temp file and prints ONLY the file path to
stdout (plain ASCII), so the caller never has to deal with console-encoding
issues (cp949 etc).

Usage:
    parse_claude_overview.py <session.jsonl>
"""
import json
import re
import sys
import tempfile
from pathlib import Path

TASK_NOTIFICATION_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)


def clean(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


def summarize_text_block(text: str) -> str:
    if "<task-notification>" in text:
        m = TASK_NOTIFICATION_SUMMARY_RE.search(text)
        if m:
            return clean("[task-notification] " + m.group(1))
        return clean("[task-notification] (no summary tag found)")
    return clean(text)


def parse_user_turn(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return summarize_text_block(content)

    parts = []
    if isinstance(content, list):
        for c in content:
            ctype = c.get("type")
            if ctype == "text":
                parts.append(summarize_text_block(c.get("text", "")))
            elif ctype == "tool_result":
                inner = c.get("content")
                if isinstance(inner, list):
                    for r in inner:
                        if r.get("type") == "text":
                            parts.append(summarize_text_block(r.get("text", "")))
                elif isinstance(inner, str):
                    parts.append(summarize_text_block(inner))
    return clean(" | ".join(p for p in parts if p))


def parse_assistant_turn(message: dict):
    content = message.get("content")
    texts = []
    tools = []
    if isinstance(content, list):
        for c in content:
            ctype = c.get("type")
            if ctype == "text":
                texts.append(c.get("text", ""))
            elif ctype == "tool_use":
                tools.append(c.get("name", "?"))
    summary = clean(" ".join(texts)) if texts else ""
    return summary, tools


def main():
    # Paths can contain non-ASCII characters on some machines (e.g. a
    # Korean username). Reconfigure stdout to UTF-8 with a safe fallback
    # so printing never crashes regardless of the terminal's codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print("ERROR=usage: parse_claude_overview.py <session.jsonl>")
        sys.exit(1)

    session_path = Path(sys.argv[1])
    if not session_path.is_file():
        print(f"ERROR=file not found: {session_path}")
        sys.exit(1)

    out_fd, out_path = tempfile.mkstemp(prefix="claude_overview_", suffix=".txt")
    rows = []
    malformed = 0

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

            t = d.get("type")
            if t == "user":
                message = d.get("message", {})
                summary = parse_user_turn(message)
                rows.append((line_no, "user", summary, "-"))
            elif t == "assistant":
                message = d.get("message", {})
                summary, tools = parse_assistant_turn(message)
                tool_str = ",".join(tools) if tools else "-"
                rows.append((line_no, "assistant", summary, tool_str))
            # everything else (queue-operation, etc.) is intentionally skipped

    with open(out_fd, "w", encoding="utf-8") as out:
        out.write(
            f"# TOTAL={len(rows)} SOURCE=claude FILE={session_path} "
            f"MALFORMED_LINES_SKIPPED={malformed}\n"
        )
        for line_no, role, summary, tool_str in rows:
            out.write(f"{line_no}\t{role}\t{summary}\t{tool_str}\n")

    if malformed > len(rows) and malformed > 20:
        # More unparseable lines than parsed rows: likely a format or
        # encoding problem worth flagging rather than silently continuing.
        print(f"WARNING=high malformed line count ({malformed}); session format may have changed")

    print(f"OVERVIEW_FILE={out_path}")
    print(f"TOTAL={len(rows)}")


if __name__ == "__main__":
    main()
