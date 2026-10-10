"""추출된 사용자 프롬프트에서 키워드/정규식으로 근거 ID를 찾는다."""
import argparse
import json
import re
from pathlib import Path
from common import OUTPUT, console, write_json


def main():
    console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keywords", nargs="+")
    parser.add_argument("--all", action="store_true", help="모든 키워드가 있는 발언만 검색")
    parser.add_argument("--regex", action="store_true")
    parser.add_argument("--source", choices=("claude", "codex"))
    parser.add_argument("--input", type=Path, default=OUTPUT / "prompts.jsonl")
    parser.add_argument("--output", type=Path, default=OUTPUT / "search.json")
    args = parser.parse_args()
    try:
        patterns = [re.compile(word if args.regex else re.escape(word), re.IGNORECASE) for word in args.keywords]
    except re.error as error:
        parser.error(str(error))
    result = []
    with args.input.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if args.source and row["source"] != args.source:
                continue
            matches = [bool(pattern.search(row["text"])) for pattern in patterns]
            if (all(matches) if args.all else any(matches)):
                result.append(row)
                preview = " ".join(row["text"].split())[:180]
                print(f"{row['id']}\t{row['timestamp']}\t{preview}")
    write_json(args.output, result)
    print(f"MATCHES={len(result)} OUTPUT={args.output}")


if __name__ == "__main__":
    main()
