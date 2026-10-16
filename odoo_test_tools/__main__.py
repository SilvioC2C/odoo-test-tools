"""odoo-test-tools - package entry point"""


def main():
    import sys

    from .runner import run
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
