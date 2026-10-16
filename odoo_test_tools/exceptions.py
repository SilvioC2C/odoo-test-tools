"""odoo-test-tools exceptions"""

from subprocess import CalledProcessError


class OdooProcessError(CalledProcessError):
    def __str__(self):
        res = super().__str__()
        if self.stderr:
            res += f"\n\n"
            res += "Caused by:\n"
            err = self.stderr
            if isinstance(err, bytes):
                err = err.decode()
            for ln in err.strip().splitlines():
                res += f"    {ln}\n"
            res = res.rstrip()
        return res
