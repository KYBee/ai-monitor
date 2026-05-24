from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections import defaultdict
from typing import Dict, Iterable, List, Optional


AGENTS = ("codex", "gemini", "claude")


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


def activity_status(proc: Dict[str, str]) -> str:
    try:
        pcpu = float(proc.get("pcpu", ""))
    except ValueError:
        return "running"
    if pcpu >= 1.0:
        return "running"
    return "waiting"


def activity_status_for(procs: Iterable[Dict[str, str]]) -> str:
    for proc in procs:
        if detect_agent(proc["command"]) and activity_status(proc) == "running":
            return "running"
    return "waiting"


def build_tasks(
    tmux_rows: Iterable[str],
    ps_rows: Iterable[Dict[str, str]],
    cwd_by_pid: Dict[str, str],
    preview_by_pane: Optional[Dict[str, str]] = None,
) -> List[Dict[str, object]]:
    preview_by_pane = preview_by_pane or {}
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
        open_session = pane["session"]
        tasks.append(
            {
                "id": task_id("tmux", tmux_target, agent_proc["pid"]),
                "bucket": "running",
                "status": activity_status_for(candidate_procs),
                "agent": agent,
                "badge": agent[0].upper(),
                "title": make_title(agent, pane["path"], pane["session"]),
                "summary": tmux_summary(pane["path"], pane["pane"]),
                "path": pane["path"],
                "source": "session",
                "tmux": tmux_target,
                "session": pane["session"],
                "pid": agent_proc["pid"],
                "etime": agent_proc.get("etime", ""),
                "command": agent_proc["command"],
                "hasPreview": False,
                "openCommand": f"ps -p {agent_proc['pid']} -o pid,ppid,etime,pcpu,command",
                "preview": "",
            }
        )

    for proc in ps_rows:
        if proc["pid"] in represented_pids:
            continue
        agent = detect_agent(proc["command"])
        if not agent:
            continue
        path = cwd_by_pid.get(proc["pid"], "")
        tasks.append(
            {
                "id": task_id("process", proc["pid"], proc["pid"]),
                "bucket": "running",
                "status": activity_status(proc),
                "agent": agent,
                "badge": agent[0].upper(),
                "title": make_title(agent, path),
                "summary": process_summary(path, proc["pid"]),
                "path": path or "cwd unavailable",
                "source": "process",
                "tmux": "",
                "session": "",
                "pid": proc["pid"],
                "etime": proc.get("etime", ""),
                "command": proc["command"],
                "hasPreview": False,
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

    return build_tasks(tmux_rows, ps_rows, cwd_by_pid, {})
