"""실제 사용자 텍스트를 원문 그대로 추출하고 ID와 원본 위치를 저장한다."""
import argparse
import hashlib
import json
from common import add_discovery_arguments, console, events, inventory, prompt_id, write_json


def main():
    console()
    parser = argparse.ArgumentParser(description=__doc__)
    add_discovery_arguments(parser)
    parser.add_argument("--session", action="append", default=[], help="세션 key 또는 session_id. 여러 번 지정 가능")
    parser.add_argument("--since", help="포함 시작 날짜 ISO 형식, 예: 2026-10-01")
    parser.add_argument("--until", help="포함 마지막 날짜 YYYY-MM-DD")
    args = parser.parse_args()
    manifest = inventory(args)
    rows, excluded, seen = [], [], {}
    for session in manifest["sessions"]:
        if args.session and session["key"] not in args.session and session["session_id"] not in args.session:
            continue
        for event in events(session, manifest["warnings"]):
            if event["role"] != "user":
                continue
            row = dict(event, id=prompt_id(session, event), session_key=session["key"],
                       session_id=session["session_id"], source=session["source"],
                       file=session["file"], cwd=session["cwd"], branches=session["branches"])
            date = (row["timestamp"] or "")[:10]
            if (args.since or args.until) and not date:
                row["excluded_reason"] = row["excluded_reason"] or "missing_timestamp_for_date_filter"
            elif (args.since and date < args.since) or (args.until and date > args.until):
                continue
            if row["excluded_reason"] or (not row["text"].strip() and not row["attachments"]):
                row["excluded_reason"] = row["excluded_reason"] or "no_user_content"
                excluded.append(row)
                continue
            # 같은 짧은 지시는 별도 발언이다. UUID 또는 날짜와 원문이 같을 때만 중복 후보로 표시한다.
            fingerprint = row["message_uuid"] or (row["source"] + "|" + row["timestamp"] + "|" + row["text"] if row["timestamp"] else row["id"])
            digest = hashlib.sha256(fingerprint.encode()).hexdigest()
            row["duplicate_of"] = seen.get(digest)
            seen.setdefault(digest, row["id"])
            rows.append(row)
    rows.sort(key=lambda row: (row["timestamp"] or "", row["session_key"], row["line"]))
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "sessions.json", manifest)
    write_json(args.output / "excluded-users.json", excluded)
    with (args.output / "prompts.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (args.output / "prompts.md").open("w", encoding="utf-8") as stream:
        stream.write("# 사용자 프롬프트\n\n원문은 요약하거나 자르지 않습니다. 중복 후보도 삭제하지 않습니다.\n\n")
        for row in rows:
            stream.write(f"## {row['id']}\n\n{row['timestamp']} | {row['source']} | 브랜치: {', '.join(row['branches']) or '미기록'}\n\n")
            if row["duplicate_of"]:
                stream.write(f"중복 후보: {row['duplicate_of']}\n\n")
            if row["attachments"]:
                stream.write(f"첨부 종류: {', '.join(row['attachments'])} (첨부 바이너리는 추출하지 않음)\n\n")
            stream.write(row["text"] + "\n\n---\n\n")
    print(f"PROMPTS={len(rows)} EXCLUDED_USERS={len(excluded)} WARNINGS={len(manifest['warnings'])}")
    print(f"OUTPUT={args.output.resolve()}")


if __name__ == "__main__":
    main()
