from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from scanner import scan_tasks


HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "task-history.json")


def load_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as history_file:
            payload = json.load(history_file)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as history_file:
        json.dump(history, history_file, ensure_ascii=False, indent=2)


def merge_with_history(live_tasks, history, include_stopped=False):
    live_by_id = {task["id"]: task for task in live_tasks}
    merged = list(live_tasks)
    if include_stopped:
        for task_id, task in history.items():
            if task_id in live_by_id:
                continue
            stopped = dict(task)
            stopped["bucket"] = "stopped"
            stopped["status"] = "stopped"
            merged.append(stopped)
    return merged


class MonitorHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            query = parse_qs(parsed.query)
            include_stopped = query.get("stopped", ["0"])[0] == "1"
            live_tasks = scan_tasks(include_preview=True)
            history = load_history()
            for task in live_tasks:
                history[task["id"]] = task
            save_history(history)
            self.send_json({"tasks": merge_with_history(live_tasks, history, include_stopped)})
            return
        return super().do_GET()

    def send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadingHTTPServer((args.host, args.port), MonitorHandler)
    print(f"http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
