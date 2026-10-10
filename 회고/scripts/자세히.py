"""프롬프트 ID로 같은 세션의 앞뒤 대화를 추출한다."""
import argparse
import json
from pathlib import Path
from common import OUTPUT, console, events, write_json


def main():
    console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="+", help="사용자프롬프트 결과의 ID. 여러 개 지정 가능")
    parser.add_argument("--input", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT / "details")
    parser.add_argument("--before", type=int, default=1, help="앞쪽 사용자 발언 수")
    parser.add_argument("--after", type=int, default=1, help="뒤쪽 사용자 발언 수. 마지막 발언에 대한 응답도 포함")
    parser.add_argument("--tools", action="store_true", help="도구 입출력 원문도 포함")
    args = parser.parse_args()
    if args.before < 0 or args.after < 0:
        parser.error("before/after must be non-negative")
    sessions = {row["key"]: row for row in json.loads((args.input / "sessions.json").read_text(encoding="utf-8"))["sessions"]}
    index = {}
    for line in (args.input / "prompts.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        index[row["id"]] = row
    unknown = [key for key in args.ids if key not in index]
    if unknown:
        parser.error("unknown prompt IDs: " + ", ".join(unknown))
    warnings, cache = [], {}
    for key in args.ids:
        prompt = index[key]
        session = sessions[prompt["session_key"]]
        if session["key"] not in cache:
            cache[session["key"]] = list(events(session, warnings))
        all_events = cache[session["key"]]
        users = [i for i, row in enumerate(all_events) if row["role"] == "user" and not row["excluded_reason"] and (row["text"].strip() or row["attachments"])]
        target = next((n for n, position in enumerate(users) if all_events[position]["line"] == prompt["line"]), None)
        if target is None or all_events[users[target]]["text"] != prompt["text"]:
            parser.error("source changed; re-extract prompts: " + key)
        start = users[max(0, target - args.before)]
        last = min(len(users) - 1, target + args.after)
        end = users[last + 1] if last + 1 < len(users) else len(all_events)
        selected = [row for row in all_events[start:end] if args.tools or row["role"] != "tool"]
        basename = key.replace(":", "_")
        write_json(args.output / (basename + ".json"), {"prompt": prompt, "session": session, "events": selected, "warnings": warnings})
        lines = [f"# {key}", "", f"원본: {session['file']}", "", "원본 파일 순서입니다. Claude의 parent_uuid는 JSON 결과에서 확인할 수 있습니다.", ""]
        for row in selected:
            lines.extend([f"## L{row['line']} {row['role']} {'[대상]' if row['line'] == prompt['line'] else ''}",
                          f"{row['timestamp']} | 자동 주입 구분: {row['excluded_reason'] or '-'}", "", row["text"], ""])
            if row["tools"] and not args.tools:
                lines.extend(["도구: " + ", ".join(row["tools"]), ""])
        (args.output / (basename + ".md")).write_text("\n".join(lines), encoding="utf-8")
        print(f"DETAIL={args.output / (basename + '.md')}")
    print(f"WARNINGS={len(warnings)}")


if __name__ == "__main__":
    main()
