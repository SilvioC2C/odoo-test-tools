import io
import unittest

from odoo_test_tools.utils import VerboseConsole


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


if __name__ == "__main__":
    unittest.main()
