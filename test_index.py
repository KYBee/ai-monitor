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

    def test_workspace_folder_groups_use_project_directory(self):
        markup = read_index()
        folder_group = extract_js_function(markup, "folderGroup")
        script = f"""
          {folder_group}
          const groups = [
            folderGroup("/Users/kybee/workspace/toy/tarot"),
            folderGroup("/Users/kybee/workspace/toy/ai-monitor"),
          ];
          console.log(JSON.stringify(groups));
        """
        output = subprocess.check_output(["node", "-e", script], text=True)
        groups = json.loads(output)

        self.assertEqual(groups[0]["key"], "workspace:toy/tarot")
        self.assertEqual(groups[0]["name"], "toy/tarot")
        self.assertEqual(groups[0]["path"], "/Users/kybee/workspace/toy/tarot")
        self.assertEqual(groups[1]["key"], "workspace:toy/ai-monitor")
        self.assertEqual(groups[1]["name"], "toy/ai-monitor")
        self.assertEqual(groups[1]["path"], "/Users/kybee/workspace/toy/ai-monitor")
        self.assertNotEqual(groups[0]["key"], groups[1]["key"])


if __name__ == "__main__":
    unittest.main()
