# Odoo Test Tools

`odoo-test-tools` prepares and manages isolated Docker Compose projects for
local Odoo development and testing.

## Requirements

- Python 3.12 or newer
- Docker with the Docker Compose plugin
- A multirepo checkout with repositories laid out as `<root>/<org>/<repo>/`

`repo-add` uses [Git-Autoshare](https://github.com/acsone/git-autoshare) when
its `git-autoshare-clone` executable is available on `PATH`; otherwise it uses
regular `git clone`. Git-Autoshare is optional and can be installed separately,
for example with `pipx install git-autoshare`.

Install the CLI from this repository:

```bash
python -m pip install .
```

For example, repositories may be arranged as:

```text
<root>/
├── odoo/odoo/                      # Odoo Community
├── odoo/enterprise/                # Optional Odoo Enterprise
└── oca/account-invoicing/
```

## Usage

```text
odoo-test-tools ACTION [ACTION OPTIONS]
```

Run commands from `<root>`, the multirepo checkout directory.
`--root-path` defaults to the current directory. Projects are stored in
`<root>/.odoo-test-tools/<name>`, alongside the shared
`<root>/.odoo-test-tools/ODOO-VERSION.txt` marker. The default project name is
the Odoo version. All initialized projects in a root use the same Odoo version;
initializing with a different version is rejected. Use `--name` to select a
named project. Database and Odoo data volumes are named by Odoo version and,
when provided, project name. Supported versions are `14.0` through `19.0`.

```bash
cd <root>
odoo-test-tools init 17.0
odoo-test-tools build
odoo-test-tools createdb
odoo-test-tools install sale stock
odoo-test-tools test sale
```

### Actions

| Action | Behavior |
| --- | --- |
| `init` | Create the project directory and prepare its Compose file, Dockerfile, Odoo config, and requirements file. |
| `build` | Build the services declared in the initialized Compose project. |
| `createdb` | Create the version-specific database and install `base,web` by default. |
| `install` | Install the requested modules, creating the database first when needed. |
| `update` | Update already-installed modules. |
| `uninstall` | Uninstall already-installed modules. |
| `test` | Run tests for the requested installed modules. |
| `ui` | Start Odoo interactively; create the database with `base,web` if needed. |
| `dropdb` | Drop the version-specific database. |
| `stop` | Stop all running project containers. |
| `rm` | Delete selected stopped service containers; optionally remove images and volumes. |
| `deinit` | Remove the project directory after its containers have been deleted. |
| `repo-add` | Clone a repository into `<root>/<org>/<repo>`; optionally add it to a project. |
| `repo-checkout` | Switch a repository to a branch, tag, or commit. |
| `repo-update` | Pull updates from a repository remote. |
| `repo-rm` | Remove a repository; optionally remove it from a project. |

`build` and the project actions other than `init` require an initialized project.
Repository actions work without a project unless their `--init` option is used.
`update`, `uninstall`, and `test` require modules and require those modules to
be installed in the selected database. `install` also requires modules.
`createdb` stops the database service when it had to start it. Database actions
(`createdb`, `install`, `update`, `uninstall`, `test`, `ui`, and `dropdb`) accept
`--keep-db-service` to leave the database container running after the action.
`rm` refuses to remove running selected services unless `--force` is used;
`deinit` requires project containers to be deleted first unless forced.

### Common options

| Option | Description |
| --- | --- |
| `-v`, `--verbose` | Show informational output; without this option, only errors are printed. |
| `--version` | Show the Odoo Test Tools version and exit. |
| `--root-path PATH` | Multirepo root (defaults to the current directory). |
| `--name NAME` | Project name (defaults to the Odoo version). |

### Action options

Options are available only on actions that use them:

| Action | Options |
| --- | --- |
| `init` | required `VERSION` or `--odoo-version VERSION`, `--no-enterprise`, `--composefile-path PATH`, `--dockerfile-path PATH`, `--odoo-cfg-path PATH`, `--requirements-path PATH`, `--exclude-addons-paths ORG/REPO [...]`, `--restrict-addons-paths ORG/REPO [...]`, `--odoo-port [HOST:]CONTAINER`, `--pg-port [HOST:]CONTAINER` |
| `createdb` | `--db NAME`, optional positional `MODULE [...]` or `--addons MODULE [...]` (defaults to `base,web`); `--keep-db-service` |
| `install`, `update`, `uninstall`, `test` | `--db NAME`, required positional `MODULE [...]` or `--addons MODULE [...]`; `--keep-db-service` |
| `ui`, `dropdb` | `--db NAME`, `--keep-db-service`; `ui` also accepts `--odoo-port PORT` |
| `rm` | `--odoo` or `--db` selects a single service (both otherwise); `--images`, `--volumes`, `--force` |
| `deinit` | `--force` |
| `repo-add` | required `URL BRANCH` positional arguments or `--url URL --branch BRANCH`; `--init` |
| `repo-checkout` | required `PATH REF` positional arguments or `--path PATH --ref REF` |
| `repo-update` | optional `PATH` positional argument or `--path PATH` (updates all repositories when omitted); optional `BRANCH` positional argument or `--branch BRANCH` (must match the repository's current branch); `--remote REMOTE` (defaults to `origin`) |
| `repo-rm` | required `PATH` positional argument or `--path PATH`; `--init` |

Database names default to `db_<version_with_underscores>`. `--addons` accepts
comma-separated names or multiple space-separated names.
Repository paths are relative to `--root-path` unless absolute. For
`repo-add --init` and `repo-rm --init`, `--name` selects the initialized
project (defaulting to the Odoo version); these options add or remove the
repository mount and its path in that project's `odoo.cfg`.

### Forwarding options

Tool-specific options can be prefixed and forwarded:

```bash
odoo-test-tools test --addons=sale --pytest-k=test_sale
odoo-test-tools ui --odoo--log-level=debug --docker-e=MYVAR=1
```

- `--docker-*` is forwarded to Docker Compose.
- `--odoo-*` is forwarded to Odoo.
- `--pg-*` is forwarded to PostgreSQL commands.
- `--pytest-*` is forwarded to pytest.
- The tool prefix is removed verbatim, so use a doubled hyphen to forward a
  long option (for example, `--docker--progress=plain` becomes
  `--progress=plain`).
