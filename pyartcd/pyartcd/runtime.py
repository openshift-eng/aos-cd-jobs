import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import toml

from pyartcd.jira import JIRAClient


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

    def new_jira_client(self, jira_token: Optional[str] = None):
        if not jira_token:
            jira_token = os.environ.get("JIRA_TOKEN")
            if not jira_token:
                raise ValueError("JIRA_TOKEN environment variable is not set")
        return JIRAClient.from_url(self.config["jira"]["url"], token_auth=jira_token)
