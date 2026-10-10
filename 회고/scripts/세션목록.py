"""워크스페이스 관련 세션과 검색에서 제외된 세션의 목록을 저장한다."""
import argparse
from common import add_discovery_arguments, console, inventory, write_json


def main():
    console()
    parser = argparse.ArgumentParser(description=__doc__)
    add_discovery_arguments(parser)
    args = parser.parse_args()
    result = inventory(args)
    write_json(args.output / "sessions.json", result)
    lines = ["# 세션 목록", "", "브랜치는 로그에 기록된 값이며 현재 하위 저장소 브랜치와 다를 수 있습니다.", ""]
    for session in result["sessions"]:
        lines.extend([f"## {session['key']}", f"- 종류: {session['source']}",
                      f"- 기간: {session['first_timestamp']} ~ {session['last_timestamp']}",
                      f"- cwd: {session['cwd']}", f"- 브랜치: {', '.join(session['branches']) or '미기록'}",
                      f"- 원본: {session['file']}", ""])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "sessions.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"SESSIONS={len(result['sessions'])} WARNINGS={len(result['warnings'])}")
    print(f"OUTPUT={args.output.resolve()}")


if __name__ == "__main__":
    main()
