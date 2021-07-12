import logging
from pathlib import Path
from typing import Any, Dict

import toml


class Runtime:
    def __init__(self, config: Dict[str, Any], working_dir: Path, dry_run: bool):
        self.config = config
        self.working_dir = working_dir
        self.dry_run = dry_run
        self.logger = logging.getLogger()

        # ensures working_dir
        if not self.working_dir.is_dir():
            raise IOError(f"Working directory {self.working_dir} doesn't exist.")

    @classmethod
    def from_config_file(cls, config_filename: Path, working_dir: Path, dry_run: bool):
        with open(config_filename, "r") as config_file:
            config_dict = toml.load(config_file)
        return Runtime(config=config_dict, working_dir=working_dir, dry_run=dry_run)
