import unittest

from scanner import (
    build_tasks,
    context_summary,
    conversation_context_from_preview,
    parse_ps,
    qa_context_from_preview,
    terminal_context_from_preview,
)


class ScannerTest(unittest.TestCase):
    def test_detects_codex_descendant_inside_tmux_pane(self):
        tmux_rows = [
            "tarot|0.0|%4|/Users/kybee/workspace/toy/tarot|node|19531",
        ]
        ps_rows = [
            {
                "pid": "19531",
                "ppid": "16980",
                "etime": "01-09:29:00",
                "command": "-zsh",
            },
            {
                "pid": "19683",
                "ppid": "19531",
                "etime": "01-09:28:50",
                "pcpu": "0.0",
                "command": "node /opt/homebrew/bin/codex",
            },
            {
                "pid": "19684",
                "ppid": "19683",
                "etime": "01-09:28:50",
                "pcpu": "8.4",
                "command": "/opt/homebrew/lib/node_modules/@openai/codex/vendor/codex",
            },
        ]

        tasks = build_tasks(
            tmux_rows,
            ps_rows,
            cwd_by_pid={},
            preview_by_pane={
                "%4": "› 지금 실행중인 AI 작업 대시보드를 만들고 있어\n오른쪽에 작업 힌트를 크게 보여줘"
            },
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["agent"], "codex")
        self.assertEqual(tasks[0]["source"], "session")
        self.assertEqual(tasks[0]["tmux"], "tarot:0.0")
        self.assertEqual(tasks[0]["status"], "running")
        self.assertEqual(
            tasks[0]["contextText"],
            "사용자\n지금 실행중인 AI 작업 대시보드를 만들고 있어\n오른쪽에 작업 힌트를 크게 보여줘",
        )
        self.assertEqual(tasks[0]["contextSummary"], "오른쪽에 작업 힌트를 크게 보여줘")
        self.assertEqual(tasks[0]["path"], "/Users/kybee/workspace/toy/tarot")
        self.assertIn("세션에서 감지됨", tasks[0]["summary"])
        self.assertTrue(tasks[0]["hasPreview"])
        self.assertEqual(tasks[0]["preview"], "")

    def test_detects_non_tmux_gemini_process_with_cwd(self):
        tmux_rows = []
        ps_rows = [
            {
                "pid": "200",
                "ppid": "1",
                "etime": "00:03:00",
                "pcpu": "0.0",
                "command": "node /opt/homebrew/bin/gemini",
            },
        ]

        tasks = build_tasks(
            tmux_rows,
            ps_rows,
            cwd_by_pid={"200": "/Users/kybee/workspace/toy/GaodeLink"},
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["agent"], "gemini")
        self.assertEqual(tasks[0]["source"], "process")
        self.assertEqual(tasks[0]["status"], "running")
        self.assertEqual(tasks[0]["pid"], "200")
        self.assertEqual(tasks[0]["path"], "/Users/kybee/workspace/toy/GaodeLink")
        self.assertIn("일반 프로세스로 실행 중", tasks[0]["summary"])
        self.assertFalse(tasks[0]["hasPreview"])

    def test_deduplicates_process_already_represented_by_tmux(self):
        tmux_rows = [
            "codex-web|0.0|%6|/Users/kybee/workspace/toy|node|71770",
        ]
        ps_rows = [
            {
                "pid": "71770",
                "ppid": "16980",
                "etime": "01:24:48",
                "command": "-zsh",
            },
            {
                "pid": "71890",
                "ppid": "71770",
                "etime": "01:24:19",
                "pcpu": "0.4",
                "command": "node /opt/homebrew/bin/codex",
            },
        ]

        tasks = build_tasks(tmux_rows, ps_rows, cwd_by_pid={"71890": "/tmp"})

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["source"], "session")
        self.assertEqual(tasks[0]["pid"], "71890")

    def test_deduplicates_child_process_already_represented_by_parent_agent(self):
        tasks = build_tasks(
            tmux_rows=[],
            ps_rows=[
                {
                    "pid": "300",
                    "ppid": "1",
                    "etime": "00:03:00",
                    "pcpu": "0.0",
                    "command": "node /opt/homebrew/bin/codex",
                },
                {
                    "pid": "301",
                    "ppid": "300",
                    "etime": "00:03:00",
                    "pcpu": "0.0",
                    "command": "/opt/homebrew/lib/node_modules/@openai/codex/vendor/codex",
                },
            ],
            cwd_by_pid={"300": "/Users/kybee/workspace/toy"},
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["pid"], "300")

    def test_parse_ps_reads_cpu_for_activity_status(self):
        rows = parse_ps(" 123 1 00:10 2.7 /usr/local/bin/claude\n")

        self.assertEqual(rows[0]["pid"], "123")
        self.assertEqual(rows[0]["pcpu"], "2.7")

    def test_conversation_context_preserves_recent_lines(self):
        context = conversation_context_from_preview(
            """
            tokens used 12,000
            > preview 보다 정보를 위로 올려줘용
            그리고 작업 프로필 색상 조금 다르게 해줘
            """,
            "fallback",
        )

        self.assertEqual(context, "preview 보다 정보를 위로 올려줘용\n그리고 작업 프로필 색상 조금 다르게 해줘")

    def test_terminal_context_keeps_unfiltered_history(self):
        context = terminal_context_from_preview(
            """
            tokens used 12,000
            Would you like to run the following command?
            › 1. Yes, proceed (y)
            실제 대화 기록
            """,
            "fallback",
        )

        self.assertIn("tokens used 12,000", context)
        self.assertIn("Would you like to run the following command?", context)
        self.assertIn("› 1. Yes, proceed (y)", context)
        self.assertIn("실제 대화 기록", context)

    def test_qa_context_keeps_only_user_questions_and_codex_answers(self):
        context = qa_context_from_preview(
            """
            › 처음 질문이에요
              이어지는 질문 줄

            • 네, 첫 답변입니다.
              이어지는 답변입니다.

            • Ran git status --short
              └ M index.html

            • Running tmux capture-pane -p -t %6 -S -80

            • Edited ai-monitor-mockup/index.html (+1 -1)

            ──────────────────────────────────────────────

            › 다음 질문이에요

            • 가능합니다. 이렇게 바꾸겠습니다.
            """
        )

        self.assertEqual(
            context,
            "사용자\n처음 질문이에요\n이어지는 질문 줄\n\nCodex\n네, 첫 답변입니다.\n이어지는 답변입니다.\n\n사용자\n다음 질문이에요\n\nCodex\n가능합니다. 이렇게 바꾸겠습니다.",
        )

    def test_conversation_context_ignores_status_and_approval_choices(self):
        context = conversation_context_from_preview(
            """
            › Run /review on my current changes
              gpt-5.5 high · ~/workspace/toy · Main [default]

            Would you like to run the following command?
            › 1. Yes, proceed (y)
              2. Yes, and don't ask again for commands that start with `curl` (p)
              3. No, and tell Codex what to do differently (esc)
            """,
            "fallback",
        )

        self.assertEqual(context, "Run /review on my current changes")

    def test_context_summary_prefers_human_request_over_tool_lines(self):
        summary = context_summary(
            """
            Explored
            Ran curl -sS https://example.com/config.js
            한 번 확인해줘요
            Reason: Do you want to allow network access?
            $ curl -sS -I https://example.com/
            """,
            "fallback",
        )

        self.assertEqual(summary, "한 번 확인해줘요")


if __name__ == "__main__":
    unittest.main()
