# agent-skills

Claude Code와 Codex CLI에서 공통으로 쓰는 개인용 스킬 모음. 두 CLI 모두 `SKILL.md` + `scripts/` 구조를 그대로 읽기 때문에, 스킬 하나를 만들면 양쪽에 그대로 설치해서 쓸 수 있다.

## 설치

```bash
python setup.py
```

레포 루트 바로 아래의 각 디렉토리(`SKILL.md`가 있는 것만)를 찾아서 다음 위치로 복사한다:

- `~/.claude/skills/<스킬이름>/` (Claude Code)
- `~/.codex/skills/<스킬이름>/` (Codex CLI)

```bash
python setup.py --target claude     # Claude Code에만 설치
python setup.py --target codex      # Codex CLI에만 설치
python setup.py --only 이어서         # 특정 스킬만 설치
```

Python 표준 라이브러리만 사용하므로 별도 설치 없이 Windows/macOS/Linux 어디서나 동일하게 동작한다. 이미 설치되어 있던 스킬은 덮어쓴다(기존 내용 삭제 후 재복사).

## 스킬을 수정했을 때

이 레포의 `<스킬이름>/` 안의 파일을 고치고 나서 `python setup.py`를 다시 실행해야 `~/.claude/skills/`, `~/.codex/skills/`에 반영된다. 반대로 설치된 쪽을 직접 고치면 이 레포에는 반영되지 않으니, **항상 이 레포를 기준(source of truth)으로 수정하고 setup.py로 배포한다.**

## 새 기기에서 쓰기

```bash
git clone <this-repo-url>
cd agent-skills
python setup.py
```

## 현재 스킬 목록

### `이어서`

가장 최근 Claude Code 세션 또는 Codex CLI 세션에서 실제로 어떤 작업이 있었는지 파악한다.

- Claude Code: `/이어서`, `/이어서 클로드`, `/이어서 코덱스`
- Codex CLI: `$이어서` (뒤에 "클로드"/"코덱스"가 섞인 자연어를 붙여도 인식함)

세션 파일을 git 상태나 문서로 추론하지 않고, 스크립트로 직접 파싱한다. 탐색 스크립트에는 실행 주체(`--agent claude|codex`)와 찾을 세션 종류(`--source claude|codex|both`)를 전달한다. 현재 실행 중인 에이전트의 세션만 건너뛰고, 다른 에이전트의 세션은 최신 파일을 선택한다. Codex의 `guardian_review` 서브에이전트 검토 스레드도 자동으로 걸러낸다. 1차로 가벼운 요약만 뽑고, 더 자세한 내용이 필요할 때만 해당 구간을 2차로 상세 파싱한다. 자세한 동작은 `이어서/SKILL.md` 참고.

## 스킬 추가하는 법

1. 레포 루트에 새 디렉토리를 만들고 그 안에 `SKILL.md`(필수, YAML frontmatter에 `name`/`description`)와 필요하면 `scripts/`, `references/`, `assets/`를 둔다.
2. `python setup.py --only <새 스킬 이름>`으로 설치해서 확인한다.
3. 이 README의 "현재 스킬 목록"에 한 줄 추가한다.
