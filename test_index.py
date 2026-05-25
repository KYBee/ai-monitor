import os
import json
import subprocess
import unittest


def read_index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as index_file:
        return index_file.read()


def extract_js_function(markup, name):
    marker = f"function {name}("
    start = markup.index(marker)
    brace_start = markup.index("{", start)
    depth = 0
    for index in range(brace_start, len(markup)):
        char = markup[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return markup[start : index + 1]
    raise AssertionError(f"Could not extract {name}")


class IndexBehaviorTest(unittest.TestCase):
    def test_tasks_are_not_refreshed_periodically(self):
        markup = read_index()

        self.assertNotIn("window.setInterval", markup)
        self.assertNotIn("AUTO_REFRESH_INTERVAL_MS", markup)

    def test_mobile_layout_keeps_conversation_detail_visible(self):
        markup = read_index()
        mobile_media_start = markup.index("@media (max-width: 720px)")
        mobile_css = markup[mobile_media_start:]

        self.assertIn(".pane.detail-pane", mobile_css)
        self.assertIn("display: block", mobile_css)
        self.assertIn(".chat-log", mobile_css)
        self.assertIn("max-height", mobile_css)

    def test_home_folder_groups_use_path_after_tilde(self):
        markup = read_index()
        folder_group = extract_js_function(markup, "folderGroup")
        script = f"""
          {folder_group}
          const groups = [
            folderGroup("/Users/example/projects/alpha"),
            folderGroup("/Users/example/projects/beta"),
            folderGroup("/Users/example/projects"),
          ];
          console.log(JSON.stringify(groups));
        """
        output = subprocess.check_output(["node", "-e", script], text=True)
        groups = json.loads(output)

        self.assertEqual(groups[0]["key"], "home:projects/alpha")
        self.assertEqual(groups[0]["name"], "alpha")
        self.assertEqual(groups[0]["path"], "~/projects/alpha")
        self.assertEqual(groups[1]["key"], "home:projects/beta")
        self.assertEqual(groups[1]["name"], "beta")
        self.assertEqual(groups[1]["path"], "~/projects/beta")
        self.assertEqual(groups[2]["key"], "home:projects")
        self.assertEqual(groups[2]["name"], "projects")
        self.assertEqual(groups[2]["path"], "~/projects")
        self.assertNotEqual(groups[0]["key"], groups[1]["key"])


if __name__ == "__main__":
    unittest.main()
