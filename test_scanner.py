import unittest

from scanner import build_tasks


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
                "command": "node /opt/homebrew/bin/codex",
            },
            {
                "pid": "19684",
                "ppid": "19683",
                "etime": "01-09:28:50",
                "command": "/opt/homebrew/lib/node_modules/@openai/codex/vendor/codex",
            },
        ]

        tasks = build_tasks(tmux_rows, ps_rows, cwd_by_pid={})

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["agent"], "codex")
        self.assertEqual(tasks[0]["source"], "tmux pane")
        self.assertEqual(tasks[0]["tmux"], "tarot:0.0")
        self.assertEqual(tasks[0]["path"], "/Users/kybee/workspace/toy/tarot")
        self.assertIn("tmux pane에서 실행 중", tasks[0]["summary"])
        self.assertTrue(tasks[0]["hasPreview"])

    def test_detects_non_tmux_gemini_process_with_cwd(self):
        tmux_rows = []
        ps_rows = [
            {
                "pid": "200",
                "ppid": "1",
                "etime": "00:03:00",
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
                "command": "node /opt/homebrew/bin/codex",
            },
        ]

        tasks = build_tasks(tmux_rows, ps_rows, cwd_by_pid={"71890": "/tmp"})

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["source"], "tmux pane")
        self.assertEqual(tasks[0]["pid"], "71890")


if __name__ == "__main__":
    unittest.main()
