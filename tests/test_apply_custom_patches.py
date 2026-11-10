"""Regression checks for GNU patch's automatic reversal during dry runs."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/apply_custom_patches.sh"
PATCH = """diff --git a/sample.c b/sample.c
--- a/sample.c
+++ b/sample.c
@@ -1,3 +1,3 @@
 /* before */
-int value = 1;
+int value = 2;
 /* after */
"""


class ApplyCustomPatchesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.patches = self.root / "patches"
        self.source.mkdir()
        self.patches.mkdir()
        (self.source / "Makefile").write_text(
            "VERSION = 5\nPATCHLEVEL = 15\nSUBLEVEL = 189\n"
        )
        (self.patches / "0001-5.15.0-5.15.222-regression.patch").write_text(PATCH)
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)

    def run_patch(self, value):
        self.source_file = self.source / "sample.c"
        self.source_file.write_text(
            f"/* before */\nint value = {value};\n/* after */\n"
        )
        environment = os.environ.copy()
        environment.pop("GITHUB_EVENT_PATH", None)
        environment.update(
            CUSTOM_PATCH_SELECTION="all",
            APPLY_SELECTED_PATCHES="true",
            SKIP_FAILED_CUSTOM_PATCHES="false",
        )
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.patches)],
            cwd=self.source,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def test_unapplied_patch_changes_source(self):
        result = self.run_patch(1)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("int value = 2;", self.source_file.read_text())
        self.assertIn("成功应用: 1", result.stdout)
        self.assertIn("源码已包含: 0", result.stdout)

    def test_existing_patch_is_not_applied_twice(self):
        result = self.run_patch(2)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("int value = 2;", self.source_file.read_text())
        self.assertIn("成功应用: 0", result.stdout)
        self.assertIn("源码已包含: 1", result.stdout)

    def test_conflicting_patch_fails_without_modifying_source(self):
        result = self.run_patch(3)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("int value = 3;", self.source_file.read_text())
        self.assertIn("自定义补丁失败，已按设置终止当前构建", result.stdout)


if __name__ == "__main__":
    unittest.main()
