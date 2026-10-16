import io
import subprocess
import unittest
from unittest.mock import patch

from odoo_test_tools import utils
from odoo_test_tools.console import VerboseConsole, console


class VerboseConsoleTests(unittest.TestCase):
    def test_suppresses_non_error_output_by_default(self):
        output = io.StringIO()
        console = VerboseConsole(file=output, force_terminal=False)

        console.print("informational output")
        console.print("an error", error=True, style="bold red")

        self.assertEqual(output.getvalue(), "an error\n")

    def test_shows_all_output_in_verbose_mode(self):
        output = io.StringIO()
        console = VerboseConsole(file=output, force_terminal=False)
        console.verbose = True

        console.print("informational output")
        console.print("an error", error=True, style="bold red")

        self.assertEqual(output.getvalue(), "informational output\nan error\n")

    def test_subprocess_output_is_suppressed_unless_verbose(self):
        with patch.object(utils.subprocess, "run") as subprocess_run, \
                patch.object(console, "verbose", False):
            utils.run(["command"])

        self.assertIs(subprocess_run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(subprocess_run.call_args.kwargs["stderr"], subprocess.DEVNULL)

        with patch.object(utils.subprocess, "run") as subprocess_run, \
                patch.object(console, "verbose", True):
            utils.run(["command"])

        self.assertNotIn("stdout", subprocess_run.call_args.kwargs)
        self.assertNotIn("stderr", subprocess_run.call_args.kwargs)

    def test_explicit_subprocess_capture_is_preserved(self):
        with patch.object(utils.subprocess, "run") as subprocess_run, \
                patch.object(console, "verbose", False):
            utils.run(["command"], capture_output=True)

        self.assertTrue(subprocess_run.call_args.kwargs["capture_output"])
        self.assertNotIn("stdout", subprocess_run.call_args.kwargs)
        self.assertNotIn("stderr", subprocess_run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
