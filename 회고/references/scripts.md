# 세션 조사 스크립트 사용법

명령의 `<스킬경로>`는 현재 읽은 `SKILL.md`가 있는 폴더, `<작업폴더>`는 조사할 워크스페이스다. 현재 작업 폴더에서 실행하면 `--workspace` 기본값은 현재 폴더다. 결과 경로 기본값도 현재 폴더의 `session-research/output/`이다.

기존 결과와 충돌하지 않도록 아래 예시는 조사별 출력 폴더를 명시한다. `<결과폴더>`는 `<작업폴더>/session-research/output/<조사명>`처럼 정한다. Python 실행 파일은 환경에 따라 `python` 또는 `python3`를 사용한다.

```text
python "<스킬경로>/scripts/세션목록.py" --workspace "<작업폴더>" --output "<결과폴더>"
python "<스킬경로>/scripts/사용자프롬프트.py" --workspace "<작업폴더>" --output "<결과폴더>"
python "<스킬경로>/scripts/검색.py" "키워드1" "키워드2" --input "<결과폴더>/prompts.jsonl" --output "<결과폴더>/search.json"
python "<스킬경로>/scripts/자세히.py" "실제프롬프트ID" --input "<결과폴더>" --output "<결과폴더>/details" --before 2 --after 2
```

## 스크립트와 옵션

| 스크립트 | 역할과 주요 옵션 |
| --- | --- |
| `세션목록.py` | 세션 메타데이터와 원본 경로를 `sessions.json`, `sessions.md`로 저장 |
| `사용자프롬프트.py` | 사용자 원문·ID를 `prompts.jsonl`, `prompts.md`로 저장하고 시간순 정렬. `--session` 반복 지정, `--since YYYY-MM-DD`, `--until YYYY-MM-DD` 지원 |
| `검색.py` | 키워드 중 하나라도 포함하는 발언 검색. `--all`은 모든 키워드, `--regex`는 정규식. 콘솔은 미리보기, JSON은 전체 원문 |
| `자세히.py` | 여러 ID를 한 번에 받아 앞뒤 대화 저장. `--before`, `--after`는 사용자 발언 수. `--before 0 --after 0`은 대상 발언과 그 응답. `--tools`는 도구 입출력도 포함 |

세션 목록·사용자 추출의 공통 옵션:

| 옵션 | 의미 |
| --- | --- |
| `--workspace` | 조사할 작업 경로와 하위 경로 |
| `--source both\|claude\|codex` | 조사할 도구. 기본 both |
| `--claude-root` | 기본 `~/.claude/projects` |
| `--codex-root` | 기본 `~/.codex/sessions` |
| `--include-subagents` | 기본 제외되는 서브에이전트 세션 포함 |
| `--output` | 출력 폴더 |

검색의 `--input`은 `prompts.jsonl` 파일이고 상세 조회의 `--input`은 `sessions.json`과 `prompts.jsonl`이 있는 폴더다. 출력 폴더를 바꾸면 모든 명령의 경로를 맞춘다. 같은 출력 파일은 재실행 시 덮어쓰며 이전 상세 결과는 자동 삭제하지 않는다.

## 결과와 근거의 한계

- `sessions.json`에 세션 메타데이터·제외 이유·파싱 경고가 있다. 사용자 추출은 이 파일도 갱신한다. `sessions.md`는 세션 목록 명령만 작성한다.
- `excluded-users.json`에는 자동 주입으로 판단한 항목과 사용자 내용이 없는 항목이 있다.
- `details/*.md`, `details/*.json`에는 해당 ID의 상세 구간과 원본 위치가 있다.
- ID는 소스 종류, 원본 파일 경로 해시, JSONL 줄 번호로 구성한다. 새 줄이 추가되어도 기존 ID는 유지되지만 파일 이동·재작성 후에는 다시 추출해야 한다. 상세 조회는 대상 원문이 달라지면 중단한다.
- Codex는 `response_item` 메시지만 채택하고 중복된 `event_msg`는 제외한다. Claude 도구 결과와 비공개 추론은 사용자 발언에 포함하지 않는다. 비공개 추론은 상세 조회에도 추출하지 않는다.
- 첨부는 종류만 표시하며 이미지·문서 바이너리는 추출하지 않는다. 필요한 시각적 맥락은 로그 텍스트만으로 확정할 수 없다.
- 재개·분기 중복 후보는 `duplicate_of`로 표시하고 삭제하지 않는다. 상세 결과는 원본 파일 순서이며 Claude 분기 관계는 `message_uuid`, `parent_uuid`로 확인한다. 다른 세션 맥락을 자동 합치지 않는다.
- 날짜 필터는 로그 타임스탬프의 날짜 부분을 사용한다. UTC 기록은 UTC 날짜 기준이다. 기본적으로 진행 중인 세션도 포함한다.
- 브랜치는 세션 작업 경로의 저장소 정보다. 워크스페이스의 main이 하위 저장소 브랜치와 같다고 가정하지 않는다.
- 소스 디렉터리 누락·파싱 실패는 경고에 남긴다. 경고가 해결되지 않았다면 전체 기록을 빠짐없이 읽었다고 결론 내리지 않는다.
