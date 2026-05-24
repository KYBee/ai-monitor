import unittest

from server import merge_with_history


class ServerHistoryTest(unittest.TestCase):
    def test_merge_with_history_keeps_stopped_only_when_requested(self):
        live = [{"id": "live-1", "bucket": "running", "status": "running", "title": "Live"}]
        history = {
            "live-1": {"id": "live-1", "bucket": "running", "status": "running", "title": "Live"},
            "old-1": {"id": "old-1", "bucket": "running", "status": "running", "title": "Old"},
        }

        running_only = merge_with_history(live, history, include_stopped=False)
        with_stopped = merge_with_history(live, history, include_stopped=True)

        self.assertEqual([task["id"] for task in running_only], ["live-1"])
        self.assertEqual([task["id"] for task in with_stopped], ["live-1", "old-1"])
        self.assertEqual(with_stopped[1]["bucket"], "stopped")
        self.assertEqual(with_stopped[1]["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
