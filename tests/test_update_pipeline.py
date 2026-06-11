from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_calendar  # noqa: E402


class UpdatePipelineTests(unittest.TestCase):
    @patch("update_calendar.subprocess.run")
    def test_optional_step_failure_does_not_raise(self, mocked_run) -> None:
        mocked_run.return_value = subprocess.CompletedProcess(["python"], 1)
        self.assertFalse(update_calendar.run("optional.py", required=False))

    @patch("update_calendar.subprocess.run")
    def test_required_step_failure_raises(self, mocked_run) -> None:
        mocked_run.return_value = subprocess.CompletedProcess(["python"], 1)
        with self.assertRaises(subprocess.CalledProcessError):
            update_calendar.run("required.py")


if __name__ == "__main__":
    unittest.main()
