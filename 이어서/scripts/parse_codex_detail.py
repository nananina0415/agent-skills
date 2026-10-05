#!/usr/bin/env python3
"""Second-pass detail parser for a Codex CLI rollout .jsonl file.

Given one or more raw line-number ranges (identified from the overview
file produced by parse_codex_overview.py), extracts the FULL payload for
response_item lines in those ranges: message text, tool call input, and
tool call output.

Writes the result to a UTF-8 temp file and prints ONLY the file path
(plain ASCII) to stdout.

Usage:
    parse_codex_detail.py <rollout.jsonl> --range 10-25 [--range 40-55 ...]
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path


def parse_ranges(range_strs):
    ranges = []
    for rs in range_strs:
        start_s, _, end_s = rs.partition("-")
        start, end = int(start_s), int(end_s)
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def in_any_range(line_no, ranges):
    return any(start <= line_no <= end for start, end in ranges)


def main():
    # Paths can contain non-ASCII characters on some machines (e.g. a
    # Korean username). Reconfigure stdout to UTF-8 with a safe fallback
    # so printing never crashes regardless of the terminal's codepage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("session_file")
    ap.add_argument("--range", action="append", required=True, dest="ranges",
                     help="raw jsonl line range, e.g. 10-25 (repeatable)")
    args = ap.parse_args()

    session_path = Path(args.session_file)
    if not session_path.is_file():
        print(f"ERROR=file not found: {session_path}")
        sys.exit(1)

    try:
        ranges = parse_ranges(args.ranges)
    except ValueError:
        print(f"ERROR=invalid --range value in {args.ranges}, expected <start>-<end>")
        sys.exit(1)

    out_fd, out_path = tempfile.mkstemp(prefix="codex_detail_", suffix=".txt")
    malformed = 0
    matched = 0

    with open(out_fd, "w", encoding="utf-8") as out:
        out.write(f"# RANGES={args.ranges} SOURCE=codex FILE={session_path}\n")
        with open(session_path, encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                if not in_any_range(line_no, ranges):
                    continue
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
                if ptype in ("message", "custom_tool_call", "custom_tool_call_output",
                             "function_call", "function_call_output"):
                    matched += 1
                    out.write(f"\n=== line {line_no} ({ptype}) ===\n")
                    out.write(json.dumps(payload, ensure_ascii=False, indent=2))
                    out.write("\n")

    if matched == 0:
        print(f"WARNING=no matching response_items in ranges {args.ranges}; check line numbers against the overview file")
    if malformed > 0:
        print(f"WARNING=skipped {malformed} malformed lines inside requested ranges")

    print(f"DETAIL_FILE={out_path}")


if __name__ == "__main__":
    main()
