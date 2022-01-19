import logging
import re
import smtplib
import time
from datetime import datetime
from email.generator import Generator
from email.message import EmailMessage
from typing import List, Optional, Union

_LOGGER = logging.getLogger(__name__)


class MailService:
    @classmethod
    def from_config(cls, config):
        return MailService(config["email"]["smtp_server"], config["email"]["from"], config["email"].get("reply_to"), config["email"].get("cc"))

    def __init__(self, smtp_server: str, sender: str, reply_to: Optional[str] = None, cc: Optional[Union[str, List[str]]] = None) -> None:
        self.smtp_server = smtp_server
        self.sender = sender
        self.reply_to = reply_to
        self.cc = cc

    def send_mail(self, to: Union[str, List[str]], subject: str, content: str, archive_dir: Optional[str] = None, dry_run: bool = False) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        if self.reply_to:
            msg["Reply-to"] = self.reply_to
        if self.cc:
            msg["CC"] = self.cc
        msg.set_content(content)

        if archive_dir:
            archive_dir.mkdir(parents=True, exist_ok=True)
            filename = (
                "email-"
                + datetime.now().strftime("%Y%m%d-%H%M%S")
                + "-"
                + re.sub(r"[^@.\w]+", "_", msg["To"])
                + "-"
                + re.sub(r"[^@.\w]+", "_", subject)
                + ".eml"
            )
            with open(archive_dir / filename, "w") as f:
                gen = Generator(f)
                gen.flatten(msg)
            _LOGGER.info("Saved email to %s", archive_dir / filename)

        _LOGGER.info("Sending email to %s: %s - %s",
                     msg["To"], subject, content)

        if not dry_run:
            # The SMTP server may have a limit on how many simultaneous open connections it will accept from a single IP address.
            # e.g. smtplib.SMTPConnectError: (421, b'4.7.0 smtp.corp.redhat.com Error: too many connections from 10.0.115.152')
            retry_count = 5
            sleep_secs = 3
            for i in range(retry_count + 1):
                try:
                    smtp = smtplib.SMTP(self.smtp_server)
                    smtp.send_message(msg)
                    smtp.quit()
                    break
                except smtplib.SMTPConnectError as err:
                    _LOGGER.warn("Error connecting to SMTP server %s: %s", self.smtp_server, str(err))
                    if i < retry_count:
                        _LOGGER.warn("(%s/%s) Will retry in %s seconds.", i + 1, retry_count, sleep_secs)
                        time.sleep(sleep_secs)
                        sleep_secs *= 2
            _LOGGER.info("Sent email to %s: %s - %s",
                         msg["To"], subject, content)
        else:
            _LOGGER.warn("[DRY RUN] Would have sent email: %s", msg)
        return msg
