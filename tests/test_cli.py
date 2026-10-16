import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from odoo_test_tools.cli import parse_args


class ParseArgsTests(unittest.TestCase):
    def test_parses_core_options_ports_and_forwarded_arguments(self):
        argv = [
            "test",
            "--root-path",
            "/tmp/repos",
            "--db",
            "demo",
            "--addons",
            "sale",
            "stock",
            "--docker-e=MY_VAR=hello",
            "--odoo--log-level",
            "debug",
            "--pg-v",
            "--pytest-k=test_sale",
        ]
        with patch.object(sys, "argv", ["odoo-test-tools", *argv]):
            args, extra = parse_args()

        self.assertEqual(args.root_path, Path("/tmp/repos"))
        self.assertEqual(args.addons, ["sale", "stock"])
        self.assertEqual(extra["docker"], ["-e=MY_VAR=hello"])
        self.assertEqual(extra["odoo"], ["--log-level", "debug"])
        self.assertEqual(extra["pg"], ["-v"])
        self.assertEqual(extra["pytest"], ["-k=test_sale"])

    def test_prefixed_arguments_preserve_all_hyphens_after_tool_name(self):
        argv = [
            "ui",
            "--docker-e",
            "MY_VAR=hello",
            "--odoo--stop-after-init",
        ]
        with patch.object(sys, "argv", ["odoo-test-tools", *argv]):
            _, extra = parse_args()

        self.assertEqual(extra["docker"], ["-e", "MY_VAR=hello"])
        self.assertEqual(extra["odoo"], ["--stop-after-init"])

    def test_single_port_value_is_used_for_host_and_container(self):
        with patch.object(
            sys, "argv", [
                "odoo-test-tools", "init", "--odoo-version", "17.0",
            ],
        ):
            args, extra = parse_args()

        self.assertFalse(args.verbose)
        self.assertEqual((args.odoo_port_host, args.odoo_port_container), ("8069", "8069"))
        self.assertEqual((args.pg_port_host, args.pg_port_container), ("5432", "5432"))
        self.assertEqual(extra, {"docker": [], "odoo": [], "pg": [], "pytest": []})

    def test_verbose_can_be_set_before_or_after_the_action(self):
        for argv in (
            ["-v", "init", "--odoo-version", "17.0"],
            ["init", "--odoo-version", "17.0", "--verbose"],
        ):
            with self.subTest(argv=argv), patch.object(sys, "argv", ["odoo-test-tools", *argv]):
                args, _ = parse_args()

            self.assertTrue(args.verbose)

    def test_drop_can_select_only_database_service(self):
        with patch.object(
            sys,
            "argv",
            ["odoo-test-tools", "dropdb", "--db", "db_17_0"],
        ):
            args, extra = parse_args()

        self.assertEqual(args.db, "db_17_0")
        self.assertEqual(extra["odoo"], [])

    def test_keep_db_service_is_available_on_database_actions_only(self):
        cases = (
            ["createdb"],
            ["install", "sale"],
            ["update", "sale"],
            ["uninstall", "sale"],
            ["test", "sale"],
            ["ui"],
            ["dropdb"],
        )
        for action_args in cases:
            argv = ["odoo-test-tools", *action_args, "--keep-db-service"]
            with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                args, _ = parse_args()

            self.assertTrue(args.keep_db_service)

        with patch.object(
            sys, "argv", ["odoo-test-tools", "build", "--keep-db-service"],
        ), self.assertRaises(SystemExit):
            parse_args()

    def test_init_options_are_scoped_to_init_action(self):
        with patch.object(
            sys, "argv",
            ["odoo-test-tools", "init", "--odoo-version", "17.0",
             "--odoo-port", "8169:8069", "--pg-port=5346:5432"],
        ):
            args, _ = parse_args()

        self.assertEqual((args.odoo_port_host, args.odoo_port_container), ("8169", "8069"))
        self.assertEqual((args.pg_port_host, args.pg_port_container), ("5346", "5432"))

    def test_required_action_arguments_accept_positional_or_keyword_forms(self):
        cases = (
            (["init", "17.0"], "17.0", None),
            (["init", "--odoo-version", "17.0"], "17.0", None),
            (["install", "sale", "stock"], None, ["sale", "stock"]),
            (["install", "--addons", "sale", "stock"], None, ["sale", "stock"]),
            (["install", "sale", "--db", "demo"], None, ["sale"]),
        )
        for action_args, expected_version, expected_addons in cases:
            with self.subTest(argv=action_args), patch.object(
                sys, "argv", ["odoo-test-tools", *action_args],
            ):
                args, _ = parse_args()

            if expected_version:
                self.assertEqual(args.odoo_version, expected_version)
            if expected_addons:
                self.assertEqual(args.addons, expected_addons)

    def test_repository_actions_accept_positional_and_keyword_arguments(self):
        cases = (
            (
                ["repo-add", "https://github.com/OCA/sale-workflow.git", "17.0"],
                ("https://github.com/OCA/sale-workflow.git", "17.0"),
            ),
            (
                ["repo-add", "--url", "https://github.com/OCA/sale-workflow.git",
                 "--branch", "17.0", "--init", "--name", "custom"],
                ("https://github.com/OCA/sale-workflow.git", "17.0"),
            ),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv), patch.object(
                sys, "argv", ["odoo-test-tools", *argv],
            ):
                args, _ = parse_args()

            if argv[1] == "--url":
                self.assertEqual((args.url_opt, args.branch_opt), expected)
                self.assertIsNone(args.url_pos)
                self.assertIsNone(args.branch_pos)
                self.assertTrue(args.init)
                self.assertEqual(args.name, "custom")
            else:
                self.assertEqual((args.url_pos, args.branch_pos), expected)

        with patch.object(
            sys, "argv",
            ["odoo-test-tools", "repo-add", "https://github.com/OCA/sale.git",
             "--branch", "17.0"],
        ):
            args, _ = parse_args()
        self.assertEqual(args.url_pos, "https://github.com/OCA/sale.git")
        self.assertEqual(args.branch_opt, "17.0")

        with patch.object(
            sys, "argv",
            ["odoo-test-tools", "repo-checkout", "--path", "OCA/sale", "--ref", "17.0"],
        ):
            args, _ = parse_args()
        self.assertEqual(args.path_opt, Path("OCA/sale"))
        self.assertEqual(args.ref_opt, "17.0")

        with patch.object(
            sys, "argv",
            [
                "odoo-test-tools", "repo-update", "OCA/sale", "17.0",
                "--remote", "upstream",
            ],
        ):
            args, _ = parse_args()
        self.assertEqual(args.path_pos, Path("OCA/sale"))
        self.assertEqual(args.branch_pos, "17.0")
        self.assertEqual(args.remote, "upstream")

        with patch.object(
            sys, "argv",
            ["odoo-test-tools", "repo-update", "--branch", "17.0"],
        ):
            args, _ = parse_args()
        self.assertEqual(args.branch_opt, "17.0")

        with patch.object(
            sys, "argv", ["odoo-test-tools", "repo-update"],
        ):
            args, _ = parse_args()
        self.assertIsNone(args.path_pos)
        self.assertIsNone(args.path_opt)
        self.assertIsNone(args.branch_pos)
        self.assertIsNone(args.branch_opt)

    def test_module_action_requires_addons(self):
        with patch.object(sys, "argv", ["odoo-test-tools", "install"]):
            with self.assertRaises(SystemExit):
                parse_args()

    def test_init_requires_odoo_version_and_other_actions_reject_it(self):
        for argv in (
            ["odoo-test-tools", "init"],
            ["odoo-test-tools", "build", "--odoo-version", "17.0"],
            ["odoo-test-tools", "build", "17.0"],
        ):
            with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    parse_args()

    def test_global_version_option_prints_and_exits_early(self):
        output = StringIO()
        with patch.object(sys, "argv", ["odoo-test-tools", "nonsense", "--version"]):
            with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                parse_args()

        self.assertEqual(error.exception.code, 0)
        self.assertIn("odoo-test-tools 0.0.1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
