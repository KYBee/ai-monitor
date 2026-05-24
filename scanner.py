from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional


AGENTS = ("codex", "gemini", "claude")
PLACEHOLDER_PROMPTS = {
    "Find and fix a bug in @filename",
    "Run /review on my current changes",
}


def run_command(args: List[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""


def parse_ps(output: str) -> List[Dict[str, str]]:
    rows = []
    for line in output.splitlines():
        match_with_cpu = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(.+)$", line)
        if match_with_cpu:
            rows.append(
                {
                    "pid": match_with_cpu.group(1),
                    "ppid": match_with_cpu.group(2),
                    "etime": match_with_cpu.group(3),
                    "pcpu": match_with_cpu.group(4),
                    "command": match_with_cpu.group(5),
                }
            )
            continue
        match = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(.+)$", line)
        if match:
            rows.append(
                {
                    "pid": match.group(1),
                    "ppid": match.group(2),
                    "etime": match.group(3),
                    "pcpu": "",
                    "command": match.group(4),
                }
            )
    return rows


def detect_agent(command: str) -> Optional[str]:
    lowered = command.lower()
    if lowered.startswith("tmux "):
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for agent in AGENTS:
        for token in tokens:
            base = os.path.basename(token).lower()
            if base == agent or base == f"{agent}.js":
                return agent
        if agent == "codex" and "/@openai/codex/" in lowered:
            return agent
    return None


def descendants(root_pid: str, children_by_ppid: Dict[str, List[Dict[str, str]]]):
    stack = list(children_by_ppid.get(root_pid, []))
    while stack:
        proc = stack.pop(0)
        yield proc
        stack.extend(children_by_ppid.get(proc["pid"], []))


def has_agent_ancestor(proc: Dict[str, str], ps_by_pid: Dict[str, Dict[str, str]]) -> bool:
    parent_pid = proc.get("ppid", "")
    seen = set()
    while parent_pid and parent_pid not in seen:
        seen.add(parent_pid)
        parent = ps_by_pid.get(parent_pid)
        if not parent:
            return False
        if detect_agent(parent["command"]):
            return True
        parent_pid = parent.get("ppid", "")
    return False


def parse_tmux_row(row: str) -> Optional[Dict[str, str]]:
    parts = row.split("|", 5)
    if len(parts) != 6:
        return None
    session, pane, pane_id, path, command, pid = parts
    return {
        "session": session,
        "pane": pane,
        "pane_id": pane_id,
        "path": path,
        "command": command,
        "pid": pid,
    }


def project_name(path: str) -> str:
    if not path:
        return "unknown"
    return os.path.basename(path.rstrip(os.sep)) or path


def task_id(source: str, identity: str, agent_pid: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", identity).strip("-")
    return f"{source}:{safe}:{agent_pid}"


def make_title(agent: str, path: str, session: str = "") -> str:
    if session:
        return f"{session} · {agent}"
    return f"{project_name(path)} · {agent}"


def tmux_summary(path: str, pane: str) -> str:
    return f"{project_name(path)} 프로젝트 세션에서 감지됨 · {pane}"


def process_summary(path: str, pid: str) -> str:
    return f"{project_name(path)} 프로젝트에서 일반 프로세스로 실행 중 · PID {pid}"


def iter_jsonl(path: str):
    try:
        with open(path, "r", encoding="utf-8") as jsonl_file:
            for line in jsonl_file:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def recent_jsonl_files(root: str, limit: int = 80) -> List[str]:
    files = []
    if not os.path.isdir(root):
        return files
    for current_root, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(current_root, name)
            try:
                files.append((os.path.getmtime(path), path))
            except OSError:
                continue
    files.sort(reverse=True)
    return [path for _, path in files[:limit]]


def parse_timestamp(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def format_message_time(sort_value: float) -> str:
    if not sort_value:
        return ""
    return datetime.fromtimestamp(sort_value).strftime("%H:%M")


def normalize_context_messages(messages: List[Dict[str, object]]) -> List[Dict[str, str]]:
    normalized = []
    seen = set()
    for message in sorted(messages, key=lambda item: float(item.get("_sort", 0.0)), reverse=True):
        text = str(message.get("text", "")).strip()
        speaker = str(message.get("speaker", "")).strip()
        if not speaker or not text:
            continue
        if text.startswith("<turn_aborted>"):
            continue
        if is_placeholder_prompt(text):
            continue
        identity = (speaker, text)
        if identity in seen:
            continue
        seen.add(identity)
        sort_value = float(message.get("_sort", 0.0))
        normalized.append(
            {
                "speaker": speaker,
                "text": text,
                "time": str(message.get("time") or format_message_time(sort_value)),
            }
        )
    return normalized


def context_text_from_messages(messages: List[Dict[str, str]], fallback: str) -> str:
    if not messages:
        return fallback
    chronological = list(reversed(messages))
    return "\n\n".join(f"{message['speaker']}\n{message['text']}" for message in chronological)


def content_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return ""


def project_paths_match(path: str, candidate: str) -> bool:
    if not path or not candidate:
        return False
    try:
        path = os.path.realpath(path)
        candidate = os.path.realpath(candidate)
    except OSError:
        pass
    return path == candidate


def codex_history_messages(home_dir: str) -> Dict[str, List[Dict[str, object]]]:
    history_path = os.path.join(home_dir, ".codex", "history.jsonl")
    messages_by_session: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for item in iter_jsonl(history_path):
        session_id = item.get("session_id")
        text = str(item.get("text", "")).strip()
        if not session_id or not text:
            continue
        messages_by_session[session_id].append(
            {
                "speaker": "사용자",
                "text": text,
                "_sort": parse_timestamp(item.get("ts")),
            }
        )
    return messages_by_session


def codex_context_from_local_history(project_path: str, home_dir: str) -> List[Dict[str, str]]:
    history_by_session = codex_history_messages(home_dir)
    sessions_root = os.path.join(home_dir, ".codex", "sessions")
    for path in recent_jsonl_files(sessions_root):
        session_id = ""
        session_cwd = ""
        messages: List[Dict[str, object]] = []
        for item in iter_jsonl(path):
            item_type = item.get("type")
            payload = item.get("payload") or {}
            if item_type == "session_meta":
                session_id = str(payload.get("id") or "")
                session_cwd = str(payload.get("cwd") or "")
                continue
            if item_type != "response_item" or payload.get("type") != "message":
                continue
            role = payload.get("role")
            text = content_text(payload.get("content"))
            if not text:
                continue
            if role == "user":
                messages.append({"speaker": "사용자", "text": text, "_sort": parse_timestamp(item.get("timestamp"))})
            elif role == "assistant" and payload.get("phase") == "final_answer":
                messages.append({"speaker": "Codex", "text": text, "_sort": parse_timestamp(item.get("timestamp"))})
        if not project_paths_match(project_path, session_cwd):
            continue
        messages.extend(history_by_session.get(session_id, []))
        normalized = normalize_context_messages(messages)
        if normalized:
            return normalized
    return []


def gemini_project_key(project_path: str, home_dir: str) -> str:
    projects_path = os.path.join(home_dir, ".gemini", "projects.json")
    try:
        with open(projects_path, "r", encoding="utf-8") as projects_file:
            payload = json.load(projects_file)
    except (OSError, json.JSONDecodeError):
        return project_name(project_path)
    projects = payload.get("projects") if isinstance(payload, dict) else {}
    if not isinstance(projects, dict):
        return project_name(project_path)
    best_path = ""
    best_key = ""
    real_project = os.path.realpath(project_path)
    for path, key in projects.items():
        real_path = os.path.realpath(str(path))
        if real_project == real_path or real_project.startswith(real_path + os.sep):
            if len(real_path) > len(best_path):
                best_path = real_path
                best_key = str(key)
    return best_key or project_name(project_path)


def gemini_context_from_local_history(project_path: str, home_dir: str) -> List[Dict[str, str]]:
    key = gemini_project_key(project_path, home_dir)
    chats_root = os.path.join(home_dir, ".gemini", "tmp", key, "chats")
    files = recent_jsonl_files(chats_root, limit=20)
    if not files:
        return []
    messages: List[Dict[str, object]] = []
    for item in iter_jsonl(files[0]):
        item_type = item.get("type")
        sort_value = parse_timestamp(item.get("timestamp"))
        if item_type == "user":
            text = content_text(item.get("content"))
            if text:
                messages.append({"speaker": "사용자", "text": text, "_sort": sort_value})
        elif item_type == "gemini":
            text = content_text(item.get("content"))
            if text:
                messages.append({"speaker": "Gemini", "text": text, "_sort": sort_value})
    return normalize_context_messages(messages)


def claude_context_from_local_history(project_path: str, home_dir: str) -> List[Dict[str, str]]:
    encoded_project = project_path.replace(os.sep, "-")
    chats_root = os.path.join(home_dir, ".claude", "projects", encoded_project)
    files = recent_jsonl_files(chats_root, limit=20)
    if not files:
        return []
    messages: List[Dict[str, object]] = []
    for item in iter_jsonl(files[0]):
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        role = message.get("role") or item.get("type")
        text = content_text(message.get("content") or item.get("content"))
        sort_value = parse_timestamp(item.get("timestamp"))
        if role == "user" and text:
            messages.append({"speaker": "사용자", "text": text, "_sort": sort_value})
        elif role == "assistant" and text:
            messages.append({"speaker": "Claude", "text": text, "_sort": sort_value})
    return normalize_context_messages(messages)


def agent_context_from_local_history(agent: str, project_path: str, home_dir: Optional[str] = None) -> List[Dict[str, str]]:
    home_dir = home_dir or os.path.expanduser("~")
    if agent == "codex":
        return codex_context_from_local_history(project_path, home_dir)
    if agent == "gemini":
        return gemini_context_from_local_history(project_path, home_dir)
    if agent == "claude":
        return claude_context_from_local_history(project_path, home_dir)
    return []


def clean_preview_line(line: str) -> str:
    line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line)
    line = line.strip()
    line = re.sub(r"^[>›•\-\s]+", "", line).strip()
    return line


def clean_terminal_text(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    return text.strip()


def is_placeholder_prompt(content: str) -> bool:
    return content.strip() in PLACEHOLDER_PROMPTS


def is_meaningful_preview_line(line: str) -> bool:
    if len(line) < 3:
        return False
    if is_placeholder_prompt(line):
        return False
    lowered = line.lower()
    ignored = (
        "tokens used",
        "context left",
        "ctrl+c",
        "ctrl + t",
        "esc",
        "thinking",
        "running command",
        "would you like to run",
        "press enter to confirm",
        "yes, proceed",
        "yes, and don't ask again",
        "no, and tell codex",
        "approved codex",
        "exit code",
        "wall time",
        "worked for",
        "running ",
        "gpt-",
    )
    if re.match(r"^\d+\.\s+", line):
        return False
    if re.match(r"^[✔•]\s*(ran|running|edited|searched|searching|explored)", line, re.IGNORECASE):
        return False
    return not any(item in lowered for item in ignored)


def conversation_context_from_preview(preview: str, fallback: str = "") -> str:
    lines = [clean_preview_line(line) for line in preview.splitlines()]
    meaningful = [line for line in lines if is_meaningful_preview_line(line)]
    if not meaningful:
        return fallback
    context = "\n".join(meaningful[-24:])
    if len(context) > 2400:
        return context[-2400:].lstrip()
    return context


def terminal_context_from_preview(preview: str, fallback: str = "") -> str:
    context = clean_terminal_text(preview)
    return context or fallback


def qa_context_from_preview(preview: str, fallback: str = "") -> str:
    messages = qa_messages_from_preview(preview)
    if not messages:
        return fallback
    return context_text_from_messages(messages, fallback)


def qa_messages_from_preview(preview: str) -> List[Dict[str, str]]:
    entries = []
    current_speaker = ""
    current_lines: List[str] = []

    def flush():
        nonlocal current_speaker, current_lines
        lines = [line for line in current_lines if line.strip()]
        if current_speaker and lines:
            entries.append((current_speaker, lines))
        current_speaker = ""
        current_lines = []

    def start_entry(speaker: str, text: str):
        flush()
        current_speaker = speaker
        current_lines.append(text)
        return current_speaker

    def strip_marker(line: str, marker: str) -> str:
        return line.strip()[len(marker) :].strip()

    def is_user_prompt(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("› "):
            return False
        content = stripped[2:].strip()
        if is_placeholder_prompt(content):
            return False
        return not re.match(r"^\d+\.\s+", content)

    def is_tool_or_status_line(line: str) -> bool:
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            return False
        if stripped.startswith(("└", "│", "…", "─", "✔", "↳")):
            return True
        if lowered.startswith(
            (
                "ran ",
                "edited ",
                "explored",
                "searching",
                "searched",
                "read ",
                "updated plan",
                "spawned ",
                "running ",
                "working ",
                "waited ",
                "closed ",
                "sent input",
                "queued ",
                "interacted ",
                "context compacted",
                "would you like",
                "reason:",
                "press enter",
                "gpt-",
                "shift +",
                "queued follow-up inputs",
                "find and fix a bug in @filename",
                "run /review on my current changes",
            )
        ):
            return True
        return False

    def is_codex_answer(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("• "):
            return False
        content = stripped[2:].strip()
        return bool(content) and not is_tool_or_status_line(content)

    for raw_line in clean_terminal_text(preview).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if is_user_prompt(line):
            current_speaker = start_entry("사용자", strip_marker(line, "› "))
            continue
        if stripped.startswith("› "):
            flush()
            continue
        if is_codex_answer(line):
            current_speaker = start_entry("Codex", strip_marker(line, "• "))
            continue
        if stripped.startswith("• ") or is_tool_or_status_line(stripped):
            flush()
            continue
        if not stripped:
            continue
        if current_speaker:
            if not is_tool_or_status_line(stripped):
                current_lines.append(stripped)

    flush()
    if not entries:
        return []
    messages = [
        {"speaker": speaker, "text": "\n".join(lines), "time": ""}
        for speaker, lines in entries
    ]
    return list(reversed(messages))


def latest_user_request_summary(messages: List[Dict[str, str]], fallback: str) -> str:
    for message in messages:
        if message.get("speaker") != "사용자":
            continue
        text = " ".join(str(message.get("text", "")).split())
        if not text:
            continue
        return f"{text[:157].rstrip()}..." if len(text) > 160 else text
    return fallback


def context_summary(context: str, fallback: str) -> str:
    def useful_for_summary(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if is_placeholder_prompt(stripped):
            return False
        lowered = stripped.lower()
        prefixes = ("ran ", "explored", "searching", "searched", "read ", "edited ", "thread:", "reason:", "$ ")
        if stripped.startswith(("└", "│", "…", "─")):
            return False
        if lowered.startswith(prefixes):
            return False
        if "http://" in lowered or "https://" in lowered:
            return False
        if "http/1.1" in lowered:
            return False
        return True

    for line in reversed(context.splitlines()):
        if useful_for_summary(line):
            summary = line.strip()
            return f"{summary[:157].rstrip()}..." if len(summary) > 160 else summary
    return fallback


def capture_preview(pane_id: str) -> str:
    if not pane_id:
        return ""
    return run_command(["tmux", "capture-pane", "-p", "-t", pane_id, "-S", "-"])


def build_tasks(
    tmux_rows: Iterable[str],
    ps_rows: Iterable[Dict[str, str]],
    cwd_by_pid: Dict[str, str],
    preview_by_pane: Optional[Dict[str, str]] = None,
    process_context_by_pid: Optional[Dict[str, List[Dict[str, str]]]] = None,
) -> List[Dict[str, object]]:
    preview_by_pane = preview_by_pane or {}
    process_context_by_pid = process_context_by_pid or {}
    children_by_ppid: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    ps_by_pid = {}
    for proc in ps_rows:
        ps_by_pid[proc["pid"]] = proc
        children_by_ppid[proc["ppid"]].append(proc)

    tasks = []
    represented_pids = set()

    for row in tmux_rows:
        pane = parse_tmux_row(row)
        if not pane:
            continue
        candidate_procs = [
            {
                "pid": pane["pid"],
                "ppid": "",
                "etime": "",
                "pcpu": "",
                "command": pane["command"],
            }
        ]
        candidate_procs.extend(descendants(pane["pid"], children_by_ppid))
        agent_proc = None
        agent = None
        for proc in candidate_procs:
            agent = detect_agent(proc["command"])
            if agent:
                agent_proc = proc
                break
        if not agent or not agent_proc:
            continue

        for proc in candidate_procs:
            if detect_agent(proc["command"]):
                represented_pids.add(proc["pid"])
        tmux_target = f"{pane['session']}:{pane['pane']}"
        preview = preview_by_pane.get(pane["pane_id"], "")
        summary = tmux_summary(pane["path"], pane["pane"])
        context_messages = qa_messages_from_preview(preview)
        context_text = qa_context_from_preview(preview, summary)
        summary_context = conversation_context_from_preview(preview, summary)
        fallback_context_summary = context_summary(summary_context, summary)
        tasks.append(
            {
                "id": task_id("tmux", tmux_target, agent_proc["pid"]),
                "bucket": "running",
                "status": "running",
                "agent": agent,
                "badge": agent[0].upper(),
                "title": make_title(agent, pane["path"], pane["session"]),
                "summary": summary,
                "contextSummary": latest_user_request_summary(context_messages, fallback_context_summary),
                "contextText": context_text,
                "contextMessages": context_messages,
                "path": pane["path"],
                "source": "session",
                "tmux": tmux_target,
                "session": pane["session"],
                "pid": agent_proc["pid"],
                "etime": agent_proc.get("etime", ""),
                "command": agent_proc["command"],
                "hasPreview": bool(preview.strip()),
                "openCommand": f"ps -p {agent_proc['pid']} -o pid,ppid,etime,pcpu,command",
                "preview": "",
            }
        )

    for proc in ps_rows:
        if proc["pid"] in represented_pids:
            continue
        if has_agent_ancestor(proc, ps_by_pid):
            continue
        agent = detect_agent(proc["command"])
        if not agent:
            continue
        path = cwd_by_pid.get(proc["pid"], "")
        summary = process_summary(path, proc["pid"])
        context_messages = process_context_by_pid.get(proc["pid"], [])
        context_text = context_text_from_messages(context_messages, summary)
        tasks.append(
            {
                "id": task_id("process", proc["pid"], proc["pid"]),
                "bucket": "running",
                "status": "running",
                "agent": agent,
                "badge": agent[0].upper(),
                "title": make_title(agent, path),
                "summary": summary,
                "contextSummary": latest_user_request_summary(context_messages, summary),
                "contextText": context_text,
                "contextMessages": context_messages,
                "path": path or "cwd unavailable",
                "source": "process",
                "tmux": "",
                "session": "",
                "pid": proc["pid"],
                "etime": proc.get("etime", ""),
                "command": proc["command"],
                "hasPreview": bool(context_messages),
                "openCommand": f"ps -p {proc['pid']} -o pid,ppid,etime,pcpu,command",
                "preview": "",
            }
        )

    return sorted(tasks, key=lambda task: (str(task["path"]), str(task["agent"]), str(task["pid"])))


def get_process_cwd(pid: str) -> str:
    output = run_command(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"])
    for line in output.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def scan_tasks(include_preview: bool = False) -> List[Dict[str, object]]:
    tmux_output = run_command(
        [
            "tmux",
            "list-panes",
            "-a",
            "-F",
            "#{session_name}|#{window_index}.#{pane_index}|#{pane_id}|#{pane_current_path}|#{pane_current_command}|#{pane_pid}",
        ]
    )
    ps_output = run_command(["ps", "ax", "-o", "pid=,ppid=,etime=,pcpu=,command="])
    tmux_rows = tmux_output.splitlines()
    ps_rows = parse_ps(ps_output)

    cwd_by_pid = {}
    for proc in ps_rows:
        if detect_agent(proc["command"]):
            cwd_by_pid[proc["pid"]] = get_process_cwd(proc["pid"])

    process_context_by_pid = {}
    if include_preview:
        for proc in ps_rows:
            agent = detect_agent(proc["command"])
            if not agent:
                continue
            path = cwd_by_pid.get(proc["pid"], "")
            process_context_by_pid[proc["pid"]] = agent_context_from_local_history(agent, path)

    preview_by_pane = {}
    if include_preview:
        for row in tmux_rows:
            pane = parse_tmux_row(row)
            if pane:
                preview_by_pane[pane["pane_id"]] = capture_preview(pane["pane_id"])

    return build_tasks(tmux_rows, ps_rows, cwd_by_pid, preview_by_pane, process_context_by_pid)
