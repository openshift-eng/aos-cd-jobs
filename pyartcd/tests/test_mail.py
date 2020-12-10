import pathlib
from unittest import TestCase, mock

from pyartcd.mail import MailService


class TestMailService(TestCase):
    def test_from_config(self):
        config = {
            "email": {
                "smtp_server": "mail.example.com",
                "from": "alice@example.com",
                "reply_to": "reply_to@example.com",
                "cc": ["cc1@example.com", "cc2@example.com"],
            }
        }
        svc = MailService.from_config(config)
        self.assertEqual(svc.smtp_server, config["email"]["smtp_server"])
        self.assertEqual(svc.sender, config["email"]["from"])
        self.assertEqual(svc.reply_to, config["email"]["reply_to"])
        self.assertEqual(svc.cc, config["email"]["cc"])

    @mock.patch("builtins.open")
    @mock.patch("pathlib.Path.mkdir")
    @mock.patch("pyartcd.mail.Generator")
    @mock.patch("smtplib.SMTP")
    def test_send_mail(self, MockSTMP, MockGenerator, mock_mkdir, mock_open):
        subject = "fake subject"
        content = "fake content"
        to = ["bob@example.com"]
        config = {
            "email": {
                "smtp_server": "mail.example.com",
                "from": "alice@example.com",
                "reply_to": "reply_to@example.com",
                "cc": ["cc1@example.com", "cc2@example.com"],
            }
        }
        archive_dir = pathlib.Path("foo/mails")
        svc = MailService.from_config(config)
        mail = svc.send_mail(to, subject, content, archive_dir, dry_run=False)
        MockSTMP.return_value.send_message.assert_called_with(mail)
        MockSTMP.return_value.quit.assert_called_with()
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_open.assert_called()
        MockGenerator.return_value.flatten.assert_called_with(mail)
