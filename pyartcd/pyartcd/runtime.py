import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import tomli

from pyartcd.jira import JIRAClient
from pyartcd.mail import MailService
from pyartcd.slack import SlackClient


class Runtime:
    def __init__(self, config: Dict[str, Any], working_dir: Path, dry_run: bool):
        self.config = config
        self.working_dir = working_dir
        self.dry_run = dry_run
        self.logger = self.init_logger()

        # checks working_dir
        if not self.working_dir.is_dir():
            raise IOError(f"Working directory {self.working_dir.absolute()} doesn't exist.")

    @staticmethod
    def init_logger():
        logging.getLogger().removeHandler(logging.getLogger().handlers[0])
        logger = logging.getLogger('pyartcd')
        formatter = logging.Formatter('%(asctime)s %(name)s:%(levelname)s %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    @classmethod
    def from_config_file(cls, config_filename: Path, working_dir: Path, dry_run: bool):
        with open(config_filename, "rb") as config_file:
            config_dict = tomli.load(config_file)
        return Runtime(config=config_dict, working_dir=working_dir, dry_run=dry_run)

    def new_jira_client(self, jira_token: Optional[str] = None):
        if not jira_token:
            jira_token = os.environ.get("JIRA_TOKEN")
            if not jira_token:
                raise ValueError("JIRA_TOKEN environment variable is not set")
        return JIRAClient.from_url(self.config["jira"]["url"], token_auth=jira_token)

    def new_slack_client(self, token: Optional[str] = None):
        if not token and not self.dry_run:
            token = os.environ.get("SLACK_BOT_TOKEN")
            if not token and not self.dry_run:
                raise ValueError("SLACK_BOT_TOKEN environment variable is not set")
        return SlackClient(token, dry_run=self.dry_run,
                           job_name=self.get_job_name(),
                           job_run_url=self.get_job_run_url(),
                           job_run_name=self.get_job_run_name())

    def new_mail_client(self):
        return MailService.from_config(self.config)

    def get_job_name(self):
        return os.environ.get("JOB_NAME")

    def get_job_run_name(self):
        return os.environ.get("BUILD_ID")

    def get_job_run_url(self):
        url = os.environ.get("BUILD_URL")
        if not url:
            return None
        return f"{url.rstrip('/')}"
