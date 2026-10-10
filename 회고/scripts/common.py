"""Claude/Codex 로컬 JSONL 기록을 읽는 공통 함수. 외부 패키지 불필요."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
OUTPUT = ROOT / "session-research" / "output"


def console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path, warnings):
    try:
        with path.open(encoding="utf-8-sig") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        yield number, item
                    else:
                        warnings.append({"file": str(path), "line": number, "reason": "not_object"})
                except json.JSONDecodeError as error:
                    warnings.append({"file": str(path), "line": number, "reason": str(error)})
    except (OSError, UnicodeError) as error:
        warnings.append({"file": str(path), "reason": str(error)})


def normalized(path):
    return str(path).replace("\\", "/").rstrip("/").casefold()


def belongs(cwd, workspace):
    root = normalized(workspace)
    candidate = normalized(cwd)
    return candidate == root or candidate.startswith(root + "/")


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "") for block in content
        if isinstance(block, dict) and block.get("type") in ("text", "input_text", "output_text")
        and isinstance(block.get("text"), str)
    )


def injected_reason(text, item):
    if item.get("isMeta"):
        return "isMeta"
    stripped = text.strip()
    prefixes = {
        "# AGENTS.md instructions for ": "workspace_instructions",
        "<environment_context>": "environment_context",
        "<recommended_plugins>": "plugin_notice",
        "<task-notification>": "task_notification",
        "<system-reminder>": "system_reminder",
        "<local-command-stdout>": "local_command_output",
        "<local-command-stderr>": "local_command_output",
        "<local-command-caveat>": "local_command_notice",
        "This session is being continued from a previous conversation": "continuation_summary",
        "[Request interrupted by user": "interruption_marker",
    }
    for prefix, reason in prefixes.items():
        if stripped.startswith(prefix):
            return reason
    return None


def metadata(path, source, warnings):
    result = {"source": source, "file": str(path.resolve()), "session_id": path.stem,
              "cwd": "", "branches": [], "first_timestamp": None, "last_timestamp": None,
              "subagent": False, "bytes": path.stat().st_size}
    # 세션 찾기 단계에서도 본문은 출력하지 않고 메타데이터만 수집한다.
    for _, item in read_jsonl(path, warnings):
        timestamp = item.get("timestamp")
        if timestamp:
            result["first_timestamp"] = result["first_timestamp"] or timestamp
            result["last_timestamp"] = timestamp
        if source == "codex" and item.get("type") == "session_meta":
            payload = item.get("payload", {})
            result["session_id"] = payload.get("id") or payload.get("session_id") or path.stem
            result["cwd"] = payload.get("cwd", "")
            result["thread_source"] = payload.get("thread_source")
            result["parent_thread_id"] = payload.get("parent_thread_id")
            origin = payload.get("source")
            result["subagent"] = bool(payload.get("parent_thread_id")) or payload.get("thread_source") == "guardian_review" or (isinstance(origin, dict) and "subagent" in origin)
            branch = (payload.get("git") or {}).get("branch")
        elif source == "claude":
            result["cwd"] = item.get("cwd") or result["cwd"]
            result["session_id"] = item.get("sessionId") or result["session_id"]
            result["subagent"] = result["subagent"] or bool(item.get("isSidechain"))
            branch = item.get("gitBranch")
        else:
            branch = None
        if branch and branch not in result["branches"]:
            result["branches"].append(branch)
        if source == "codex" and result["subagent"]:
            # 메인 세션 조사에 불필요한 검토 스레드의 본문은 읽지 않는다.
            break
    result["key"] = source + "-" + hashlib.sha256(result["file"].encode()).hexdigest()[:16]
    return result


def discover(workspace, claude_root, codex_root, source="both", include_subagents=False):
    warnings, sessions, excluded = [], [], []
    candidates = []
    if source in ("both", "claude"):
        # 하위 저장소에서 시작된 세션도 포함한다. 실제 cwd로 최종 확인한다.
        encoded = re.sub(r"[:\\/]", "-", str(workspace.resolve())).casefold()
        if claude_root.is_dir():
            for project in claude_root.iterdir():
                if project.is_dir() and (project.name.casefold() == encoded or project.name.casefold().startswith(encoded + "-")):
                    candidates.extend((path, "claude") for path in project.glob("*.jsonl"))
                    if include_subagents:
                        candidates.extend((path, "claude") for path in project.glob("*/subagents/*.jsonl"))
        else:
            warnings.append({"file": str(claude_root), "reason": "source_directory_missing"})
    if source in ("both", "codex"):
        if codex_root.is_dir():
            candidates.extend((path, "codex") for path in codex_root.rglob("rollout-*.jsonl"))
        else:
            warnings.append({"file": str(codex_root), "reason": "source_directory_missing"})
    for path, kind in sorted(candidates):
        session = metadata(path, kind, warnings)
        if not belongs(session["cwd"], workspace):
            excluded.append({"file": str(path), "reason": "outside_workspace_or_missing_cwd"})
        elif session["subagent"] and not include_subagents:
            excluded.append({"file": str(path), "reason": "subagent"})
        else:
            sessions.append(session)
    sessions.sort(key=lambda row: (row["first_timestamp"] or "", row["key"]))
    return {"workspace": str(workspace.resolve()), "sessions": sessions, "excluded": excluded, "warnings": warnings}


def events(session, warnings):
    for line, item in read_jsonl(Path(session["file"]), warnings):
        role, text, tools, attachments = None, "", [], []
        if session["source"] == "codex":
            if item.get("type") == "response_item":
                payload = item.get("payload", {})
                kind = payload.get("type")
                if kind == "message" and payload.get("role") in ("user", "assistant"):
                    role = payload["role"]
                    text = text_content(payload.get("content"))
                    attachments = [b.get("type") for b in (payload.get("content") or []) if isinstance(b, dict) and b.get("type") not in ("input_text", "output_text", "text")]
                elif kind in ("function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"):
                    role = "tool"
                    text = json.dumps(payload, ensure_ascii=False)
                    tools = [payload.get("name") or kind]
            # event_msg.user_message는 response_item과 중복되므로 채택하지 않는다.
        elif item.get("type") in ("user", "assistant"):
            message = item.get("message") or {}
            role = item["type"]
            content = message.get("content")
            text = text_content(content)
            if isinstance(content, list):
                tools = [b.get("name") or b.get("type") for b in content if isinstance(b, dict) and b.get("type") in ("tool_use", "tool_result")]
                attachments = [b.get("type") for b in content if isinstance(b, dict) and b.get("type") in ("image", "document")]
                if tools and not text:
                    role, text = "tool", json.dumps(content, ensure_ascii=False)
        if role:
            yield {"line": line, "role": role, "text": text, "tools": tools,
                   "attachments": attachments, "timestamp": item.get("timestamp"),
                   "message_uuid": item.get("uuid"), "parent_uuid": item.get("parentUuid"),
                   "excluded_reason": injected_reason(text, item) if role == "user" else None}


def prompt_id(session, event):
    # 원본 JSONL을 덧붙여도 기존 ID가 변하지 않는다.
    return f"{session['key']}:L{event['line']}"


def add_discovery_arguments(parser):
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude/projects")
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--source", choices=("claude", "codex", "both"), default="both")
    parser.add_argument("--include-subagents", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)


def inventory(args):
    return discover(args.workspace, args.claude_root, args.codex_root, args.source, args.include_subagents)
