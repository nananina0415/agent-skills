---
name: 이어서
description: 가장 최근 Claude Code 세션 또는 Codex CLI 세션에서 실제로 어떤 작업이 있었는지 파악합니다. 사용자가 "이어서", "직전 세션", "아까 그 작업", "최근 코덱스/클로드 세션에서 뭐 했는지" 등을 물을 때, 또는 지난 대화를 이어가려 할 때 사용하세요. 추론이나 git log로 대충 때려맞추지 말고 반드시 이 스킬의 스크립트로 세션 파일을 직접 파싱하세요.
---

# 이어서 — 직전 세션 작업 파악

## 왜 이 스킬이 필요한가

세션 로그를 직접 찾지 않고 git 상태나 문서로 "추론"하면 방향이 틀리기 쉽고 토큰을 많이 쓴다. 또한 Codex 세션 폴더에는 `guardian_review` 같은 서브에이전트 검토 스레드 파일이 메인 작업 세션과 섞여 있어 혼동하기 쉽고, 터미널 콘솔 인코딩(cp949 등) 때문에 한글 출력이 깨지는 문제도 반복된다. 이 스킬은 이 세 가지 문제를 스크립트로 고정해서 매번 겪지 않도록 한다.

**항상 아래 스크립트들로 세션 파일을 직접 파싱한다. 절대 git log/문서 내용으로 추론해서 대체하지 않는다.**

## 호출 방식

- **Claude Code**: `/이어서`, `/이어서 클로드`, `/이어서 코덱스`
- **Codex CLI**: `$이어서` (뒤에 "클로드"/"코덱스"가 섞인 자연어를 붙여도 됨, 예: `$이어서 코덱스 세션 기준으로`)

Codex 스킬은 Claude Code의 슬래시 커맨드 인자(`$ARGUMENTS`)처럼 깔끔하게 분리되지 않는다. 그러므로 인자를 "formal하게" 파싱하지 말고, **사용자가 보낸 프롬프트 텍스트 안에 "클로드"라는 단어가 있으면 claude, "코덱스"라는 단어가 있으면 codex, 둘 다 없으면 both**로 판단한다. 이 로직은 두 플랫폼에서 동일하게 적용된다.

## 스크립트 위치

이 스킬이 설치된 경로를 기준으로 상대 경로:
- `scripts/find_latest_session.py`
- `scripts/parse_claude_overview.py`
- `scripts/parse_codex_overview.py`
- `scripts/parse_claude_detail.py`
- `scripts/parse_codex_detail.py`

설치 위치는 두 군데이며 내용은 동일하다:
- Claude Code용: `~/.claude/skills/이어서/`
- Codex CLI용: `~/.codex/skills/이어서/`

## 세션 파일이 어디 있는지

- **Claude Code**: `~/.claude/projects/<encoded-cwd>/*.jsonl`
  - `<encoded-cwd>` = 현재 작업 디렉토리 절대경로에서 `:`, `\`, `/` 를 전부 `-`로 치환한 문자열 (`find_latest_session.py`가 자동 계산함, 직접 계산할 필요 없음)
- **Codex CLI**: `~/.codex/sessions/<연>/<월>/<일>/rollout-*.jsonl`

파이썬 실행은 `python3`를 먼저 시도하고 실패하면 `python`으로 1회만 재시도한다. 두 번 다 실패하면 사용자에게 Python 설치 여부를 확인해달라고 요청한다.

## 실행 흐름

### 1. 대상 세션 파일 찾기

```
python3 scripts/find_latest_session.py --agent claude|codex --source claude|codex|both
```

출력은 `KEY=VALUE` 형태 평문이다 (JSON도 한글도 아님 — 콘솔 인코딩 문제를 피하기 위함). 예:

```
FILE=C:\Users\x\.codex\sessions\2026\10\05\rollout-....jsonl
SOURCE=codex
CODEX_EXCLUDED_GUARDIAN_REVIEW=3
CODEX_TOTAL_CANDIDATES=1
```

`--agent`에는 **지금 이 스크립트를 실행하는 에이전트**를 넣는다. Claude Code에서 실행 중이면 `claude`, Codex에서 실행 중이면 `codex`다. `--source`는 사용자가 찾으려는 세션 종류다. 두 인자를 혼동하지 않는다.

`ERROR=...`로 시작하면 중단하고 사용자에게 그대로 보고한다 (예: 현재 에이전트의 세션 파일이 1개뿐이라 현재 세션 제외가 불가능한 경우).

현재 에이전트와 같은 종류의 세션에서는 mtime 기준 **2번째로 최신 파일**을 고르고, 다른 종류의 세션에서는 **가장 최신 파일**을 고른다. Codex 쪽은 `thread_source == "guardian_review"`인 서브스레드 파일을 먼저 후보에서 제외한다 — 몇 개가 빠졌는지만 카운트로 보고되고 내용은 보지 않는다.

### 2. 1차 파싱 (overview)

`FILE=`로 나온 경로와 `SOURCE=`에 맞춰:

```
python3 scripts/parse_claude_overview.py <FILE>
# 또는
python3 scripts/parse_codex_overview.py <FILE>
```

출력:
```
OVERVIEW_FILE=<임시파일경로>
TOTAL=<턴/아이템 개수>
```

`WARNING=high malformed line count...`가 나오면, 이건 **환경 문제인지 세션 파일 포맷이 바뀐 것인지 알 수 없다는 뜻**이다 — 바로 더 깊이 파고들지 말고 1번 섹션 "비정상 결과 대응"을 따른다.

### 3. 끝에서부터 거슬러 읽으며 "실제 작업 3개" 찾기

`OVERVIEW_FILE`의 1번째 줄에 `# TOTAL=<n> ...`가 있다. Read 도구로 **끝에서부터** 읽는다 — 전체를 다 읽지 말고, `offset = TOTAL - 60` 정도로 마지막 구간부터 읽어 올라가며 필요한 만큼만 확장한다 (세션 파일이 크면 전체를 다 읽는 건 토큰 낭비).

각 줄은 `<원본 jsonl 줄번호>\t<role>\t<요약>\t<tool들>` (Codex는 tool 열이 없고 kind가 user/assistant/tool).

**"3개"는 user 프롬프트 개수가 아니라 실제로 완료된 작업 단위다.** 사용자가 피드백/재지시를 여러 번 보낸 끝에 완료된 하나의 작업은 1개로 친다. 예를 들어 "A 고쳐줘" → "아니 그거 아니고" → "이제 맞다"로 끝난 흐름은 작업 1개다. 이런 클러스터링을 하려면 2~3개보다 훨씬 많은 줄을 읽어야 할 수 있다 — 아깝다고 일찍 멈추지 말 것.

### 4. 사용자에게 3개 작업 요약 보고

각 작업이 어느 원본 줄번호 구간(`start-end`)에 해당하는지 내부적으로 기억해둔다 (사용자에게 줄번호 자체를 보여줄 필요는 없다).

### 5. 더 구체적인 내용이 필요할 때만 2차 파싱

사용자가 "그 중에 n번째 작업 자세히 알려줘" 등으로 요구하면:

```
python3 scripts/parse_claude_detail.py <FILE> --range <start>-<end> [--range <start2>-<end2> ...]
# 또는
python3 scripts/parse_codex_detail.py <FILE> --range <start>-<end> [...]
```

여러 작업을 한꺼번에 물으면 `--range`를 여러 번 넘겨서 **한 번의 호출로 처리**한다 (프로세스를 여러 번 띄우지 않음). 출력의 `DETAIL_FILE=` 경로를 Read 도구로 읽는다.

## 비정상 결과 대응

스크립트가 `ERROR=`나 `WARNING=`을 내거나, overview 파일 내용이 터무니없어 보이면(예: 줄 수가 0인데 세션은 분명히 길었다거나, role이 전부 이상하게 나온다거나):

1. 먼저 멈추고 사용자에게 **무슨 일이 있었는지** 그대로 보고한다. 섣불리 원인을 단정하지 않는다.
2. 원인이 환경 문제(Python 버전, 파일 권한 등)인지 세션 파일 포맷이 바뀐 것인지 확인이 필요하면, 공식 문서/체인지로그(Claude Code, Codex CLI)를 검색해서 확인한다.
3. 다만 이 조사가 오래 걸리거나 토큰을 많이 쓸 것 같으면, 조사를 계속할지 먼저 사용자에게 확인받는다. "최근 작업 3개 파악"이라는 가벼운 질문에 조사 비용이 압도적으로 커지는 상황을 반복하지 않기 위함이다.

## 참고: 실제 확인된 스키마

- **Claude jsonl**: 줄마다 `type`(`user`/`assistant`/`queue-operation` 등). `message.content`는 `text`/`tool_use`/`tool_result` 타입이 섞인 배열이거나 순수 문자열. 서브에이전트 결과는 `user` 메시지 안에 `<task-notification>...<summary>...</summary>...</result>` 형태로 들어온다.
- **Codex rollout jsonl**: 첫 줄이 `type:"session_meta"` (`payload.thread_source`, `payload.cwd` 포함). 이후 이벤트 스트림에서 실제 대화는 `type:"response_item"`이고 `payload.type`이 `"message"`(role: user/assistant/developer — developer는 시스템 주입 메시지라 무시), `"custom_tool_call"`/`"custom_tool_call_output"`(Codex의 범용 exec 등 툴 호출), `"function_call"`/`"function_call_output"`(그 외 함수 호출)로 나뉜다.
