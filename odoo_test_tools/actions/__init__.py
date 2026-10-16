"""Individual project actions."""

from .build import action_build
from .createdb import action_createdb
from .deinit import action_deinit
from .dropdb import action_dropdb
from .init import action_init
from .install import action_install
from .rm import action_rm
from .repositories import (
    action_repo_add,
    action_repo_checkout,
    action_repo_rm,
    action_repo_update,
)
from .stop import action_stop
from .test import action_test
from .ui import action_ui
from .uninstall import action_uninstall
from .update import action_update

ACTIONS_MAP = {
    "init": action_init,
    "build": action_build,
    "createdb": action_createdb,
    "install": action_install,
    "update": action_update,
    "uninstall": action_uninstall,
    "test": action_test,
    "ui": action_ui,
    "dropdb": action_dropdb,
    "stop": action_stop,
    "rm": action_rm,
    "deinit": action_deinit,
    "repo-add": action_repo_add,
    "repo-checkout": action_repo_checkout,
    "repo-update": action_repo_update,
    "repo-rm": action_repo_rm,
}
