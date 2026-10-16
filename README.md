# Odoo Test Tools

`odoo-test-tools` prepares and manages isolated Docker Compose projects for
local Odoo development and testing.

## Requirements

- Python 3.12 or newer
- Docker with the Docker Compose plugin
- A multirepo checkout with repositories laid out as `<root>/<org>/<repo>/<version>/`

Install the CLI from this repository:

```bash
python -m pip install .
```

For example, repositories may be arranged as:

```text
<root>/
├── odoo/odoo/17.0/                 # Odoo Community
├── odoo/enterprise/17.0/           # Optional Odoo Enterprise
└── oca/account-invoicing/17.0/
```

## Usage

```text
odoo-test-tools VERSION ACTION [ACTION OPTIONS]
```

The default project directory is `<root>/.odoo-test-tools/<version-without-dots>`.
Use `--root-path` and `--name` to select a different root or project name.
Supported versions are `14.0` through `19.0`.

```bash
odoo-test-tools 17.0 init
odoo-test-tools 17.0 build
odoo-test-tools 17.0 createdb
odoo-test-tools 17.0 install --addons=sale,stock
odoo-test-tools 17.0 test --addons=sale
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
| `drop` | Delete selected stopped service containers; optionally remove images and volumes. |
| `deinit` | Remove the project directory after its containers have been deleted. |

`build` and all actions other than `init` require an initialized project.
`update`, `uninstall`, and `test` require `--addons` and require those modules
to be installed in the selected database. `install` also requires `--addons`.
`createdb` stops the database service when it had to start it. `drop` refuses
to remove running selected services unless `--force` is used; `deinit` requires
project containers to be deleted first unless forced.

### Common options

| Option | Description |
| --- | --- |
| `-v`, `--verbose` | Show informational output; without this option, only errors are printed. |
| `--root-path PATH` | Multirepo root (defaults to the current directory). |
| `--name NAME` | Project name (defaults to the Odoo version without dots). |

### Action options

Options are available only on actions that use them:

| Action | Options |
| --- | --- |
| `init` | `--no-enterprise`, `--composefile-path PATH`, `--dockerfile-path PATH`, `--odoo-cfg-path PATH`, `--requirements-path PATH`, `--exclude-addons-paths ORG/REPO [...]`, `--restrict-addons-paths ORG/REPO [...]`, `--odoo-port [HOST:]CONTAINER`, `--pg-port [HOST:]CONTAINER` |
| `createdb` | `--db NAME`, optional `--addons MODULE[,MODULE...]` (defaults to `base,web`) |
| `install`, `update`, `uninstall`, `test` | `--db NAME`, required `--addons MODULE[,MODULE...]` |
| `ui`, `dropdb` | `--db NAME`; `ui` also accepts `--odoo-port PORT` |
| `drop` | `--odoo` or `--db` selects a single service (both otherwise); `--no-odoo`, `--no-db`, `--images`, `--volumes`, `--force` |
| `deinit` | `--force` |

Database names default to `db_<version_with_underscores>`. `--addons` accepts
comma-separated names or multiple space-separated names.

### Forwarding options

Tool-specific options can be prefixed and forwarded:

```bash
odoo-test-tools 17.0 test --addons=sale --pytest-k=test_sale
odoo-test-tools 17.0 ui --odoo-log-level=debug --docker-e=MYVAR=1
```

- `--docker-*` is forwarded to Docker Compose.
- `--odoo-*` is forwarded to Odoo.
- `--pg-*` is forwarded to PostgreSQL commands.
- `--pytest-*` is forwarded to pytest.
