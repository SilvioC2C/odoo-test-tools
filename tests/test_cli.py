import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from odoo_test_tools.cli import parse_args


class ParseArgsTests(unittest.TestCase):
    def test_parses_core_options_ports_and_forwarded_arguments(self):
        argv = [
            "17.0",
            "test",
            "--root-path",
            "/tmp/repos",
            "--db",
            "demo",
            "--addons",
            "sale",
            "stock",
            "--docker-e=MY_VAR=hello",
            "--odoo-log-level",
            "debug",
            "--pg-v",
            "--pytest-k=test_sale",
        ]
        with patch.object(sys, "argv", ["odoo-test-tools", *argv]):
            args, extra = parse_args()

        self.assertEqual(args.root_path, Path("/tmp/repos"))
        self.assertEqual(args.addons, ["sale", "stock"])
        self.assertEqual(extra["docker"], ["--e=MY_VAR=hello"])
        self.assertEqual(extra["odoo"], ["--log-level", "debug"])
        self.assertEqual(extra["pg"], ["--v"])
        self.assertEqual(extra["pytest"], ["--k=test_sale"])

    def test_single_port_value_is_used_for_host_and_container(self):
        with patch.object(sys, "argv", ["odoo-test-tools", "17.0", "init"]):
            args, extra = parse_args()

        self.assertFalse(args.verbose)
        self.assertEqual((args.odoo_port_host, args.odoo_port_container), ("8069", "8069"))
        self.assertEqual((args.pg_port_host, args.pg_port_container), ("5432", "5432"))
        self.assertEqual(extra, {"docker": [], "odoo": [], "pg": [], "pytest": []})

    def test_verbose_can_be_set_before_or_after_the_action(self):
        for argv in (
            ["-v", "17.0", "init"],
            ["17.0", "init", "--verbose"],
        ):
            with self.subTest(argv=argv), patch.object(sys, "argv", ["odoo-test-tools", *argv]):
                args, _ = parse_args()

            self.assertTrue(args.verbose)

    def test_drop_can_select_only_database_service(self):
        with patch.object(
            sys,
            "argv",
            ["odoo-test-tools", "17.0", "dropdb", "--db", "db_17_0"],
        ):
            args, extra = parse_args()

        self.assertEqual(args.db, "db_17_0")
        self.assertEqual(extra["odoo"], [])

    def test_init_options_are_scoped_to_init_action(self):
        with patch.object(
            sys, "argv",
            ["odoo-test-tools", "17.0", "init", "--odoo-port", "8169:8069",
             "--pg-port=5346:5432"],
        ):
            args, _ = parse_args()

        self.assertEqual((args.odoo_port_host, args.odoo_port_container), ("8169", "8069"))
        self.assertEqual((args.pg_port_host, args.pg_port_container), ("5346", "5432"))

    def test_module_action_requires_addons(self):
        with patch.object(sys, "argv", ["odoo-test-tools", "17.0", "install"]):
            with self.assertRaises(SystemExit):
                parse_args()


if __name__ == "__main__":
    unittest.main()
