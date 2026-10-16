"""Per-version Docker configuration for the official Odoo image."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionConfig:
    postgres_image: str
    pip_cmd: str
    dockerfile_template: str


# -- Dockerfile templates -------------------------------------------------------------

# 14.0: Debian Buster is EOL - must redirect apt to the archive mirror before
# any apt-get call, otherwise package installation fails entirely.
_DOCKERFILE_14 = """
FROM odoo:{version}

USER root

# Buster is EOL: redirect apt to the Debian archive mirror
RUN sed -i \\
      's|deb.debian.org/debian-security|archive.debian.org/debian-security|g; \\
       s|deb.debian.org/debian|archive.debian.org/debian|g; \\
       s|security.debian.org/debian-security|archive.debian.org/debian-security|g' \\
      /etc/apt/sources.list \\
  && sed -i '/buster-updates/d' /etc/apt/sources.list \\
  && echo 'Acquire::Check-Valid-Until "false";' \\
       > /etc/apt/apt.conf.d/99no-check-valid-until

# Copy merged repo requirements (assembled by odoo-test-tools)
RUN mkdir -p /tmp/odoo-requirements/
COPY requirements.txt /tmp/odoo-requirements/requirements.txt

RUN apt-get update \\
  && apt-get install -y --no-install-recommends libmagic1 parallel python3-dev python3-venv build-essential libffi-dev \\
  && python3 -m venv --system-site-packages /opt/venv \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir --upgrade pip setuptools wheel \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir -r /tmp/odoo-requirements/requirements.txt \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir pytest-odoo \\
  && apt-get purge -y --auto-remove python3-dev build-essential libffi-dev \\
  && rm -rf /var/lib/apt/lists/*

USER odoo
""".lstrip()

# 15.0 / 16.0: Debian Bullseye - still supported, no mirror fix needed.
_DOCKERFILE_BULLSEYE = """
FROM odoo:{version}

USER root

RUN mkdir -p /tmp/odoo-requirements/
COPY requirements.txt /tmp/odoo-requirements/requirements.txt

RUN apt-get update \\
  && apt-get install -y --no-install-recommends libmagic1 parallel python3-dev python3-venv build-essential libffi-dev \\
  && python3 -m venv --system-site-packages /opt/venv \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir --upgrade pip setuptools wheel \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir -r /tmp/odoo-requirements/requirements.txt \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir pytest-odoo \\
  && apt-get purge -y --auto-remove python3-dev build-essential libffi-dev \\
  && rm -rf /var/lib/apt/lists/*

USER odoo
""".lstrip()

# 17.0 / 18.0 / 19.0: Debian Bookworm - modern, no quirks.
_DOCKERFILE_BOOKWORM = """
FROM odoo:{version}

USER root

RUN mkdir -p /tmp/odoo-requirements/
COPY requirements.txt /tmp/odoo-requirements/requirements.txt

RUN apt-get update \\
  && apt-get install -y --no-install-recommends libmagic1 parallel python3-dev python3-venv build-essential libffi-dev \\
  && python3 -m venv --system-site-packages /opt/venv \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir --upgrade pip setuptools wheel \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir -r /tmp/odoo-requirements/requirements.txt \\
  && /opt/venv/bin/{pip_cmd} install --no-cache-dir pytest-odoo \\
  && apt-get purge -y --auto-remove python3-dev build-essential libffi-dev \\
  && rm -rf /var/lib/apt/lists/*

USER odoo
""".lstrip()

# -- docker-compose.yml template ------------------------------------------------------

COMPOSEFILE_TEMPLATE = """
services:
  db:
    image: {postgres_image}
    command: ["postgres", "-p", "{pg_container_port}"]
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo -p {pg_container_port}"]
      interval: 5s
      retries: 5
    ports:
      - "{pg_host_port}:{pg_container_port}"
    volumes:
      - pgdata_{version_id}{project_suffix}:/var/lib/postgresql/data

  odoo:
    build:
      context: {work_dir}
      dockerfile: {dockerfile}
    image: odoo-test-tools:{version}
    depends_on:
      db:
        condition: service_healthy
    environment:
      HOST: db
      PORT: "{pg_container_port}"
      USER: odoo
      PASSWORD: odoo
    ports:
      - "{odoo_port}"
    volumes:
{volumes_block}
      - odoo_data_{version_id}{project_suffix}:/var/lib/odoo

volumes:
  pgdata_{version_id}{project_suffix}:
  odoo_data_{version_id}{project_suffix}:
""".lstrip()


# -- Version registry -----------------------------------------------------------------

VERSION_CONFIGS: dict[str, VersionConfig] = {
    "14.0": VersionConfig(
        postgres_image="postgres:13",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_14,
    ),
    "15.0": VersionConfig(
        postgres_image="postgres:14",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_BULLSEYE,
    ),
    "16.0": VersionConfig(
        postgres_image="postgres:15",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_BULLSEYE,
    ),
    "17.0": VersionConfig(
        postgres_image="postgres:16",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_BOOKWORM,
    ),
    "18.0": VersionConfig(
        postgres_image="postgres:16",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_BOOKWORM,
    ),
    "19.0": VersionConfig(
        postgres_image="postgres:16",
        pip_cmd="pip3",
        dockerfile_template=_DOCKERFILE_BOOKWORM,
    ),
}

SUPPORTED_VERSIONS = tuple(VERSION_CONFIGS)


def get_config(version: str) -> VersionConfig:
    """Return the VersionConfig for ``version``"""
    return VERSION_CONFIGS[version]


def validate_version(version: str):
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported Odoo version '{version}'. "
            f"Supported versions: {", ".join(SUPPORTED_VERSIONS)}"
        )
