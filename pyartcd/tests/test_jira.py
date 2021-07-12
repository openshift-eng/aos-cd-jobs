from unittest import TestCase, mock

import jira
from pyartcd.jira import JIRAClient


class TestJIRAClient(TestCase):
    @mock.patch("pyartcd.jira.JIRA")
    def test_from_url(self, MockJIRA):
        url = "https://jira.example.com"
        basic_auth = ("username", "password")
        client = JIRAClient.from_url(url, basic_auth=basic_auth)
        self.assertEqual(client._client, MockJIRA.return_value)
        MockJIRA.assert_called_once_with(url, basic_auth=basic_auth)

    def test_get_issue(self):
        client = JIRAClient(mock.MagicMock())
        client.get_issue("FOO-1")
        client._client.issue.assert_called_once_with("FOO-1")

    def test_clone_issue(self):
        source_issue = mock.MagicMock(
            key="FOO-1",
            raw={
                "fields": {
                    "project": {"key": "FOO"},
                    "summary": "Fake issue",
                    "description": "Fake description",
                    "issuetype": {"name": "Fake-issue-type", "subtask": True},
                    "components": [],
                    "labels": ["label-1", "label-2"],
                    "reporter": {"name": "someone"},
                }
            })
        source_issue.fields.issuetype.subtask = True
        mock_jira = mock.MagicMock()
        mock_jira.create_issue.side_effect = lambda fields: mock.MagicMock(raw={"fields": fields.copy()})

        client = JIRAClient(mock_jira)
        mock_fields_transform = mock.MagicMock(side_effect=lambda fields: fields)

        new_issue = client.clone_issue(source_issue, "BAR", "12345", mock_fields_transform, True)
        self.assertEqual(new_issue.raw["fields"]["summary"], "Fake issue")
        self.assertEqual(new_issue.raw["fields"]["project"]["key"], "BAR")
        self.assertEqual(new_issue.raw["fields"]["parent"]["id"], "12345")
        mock_fields_transform.assert_called_once_with(new_issue.raw["fields"])
        mock_jira.create_issue_link.assert_called_once_with("Cloners", new_issue, source_issue)

    def test_clone_issue_with_subtasks(self):
        source_issue = mock.MagicMock(
            key="FOO-1",
            id="1",
            raw={
                "fields": {
                    "project": {"key": "FOO"},
                    "summary": "Fake issue 1",
                    "description": "Fake description",
                    "issuetype": {"name": "Fake-parent-type", "subtask": False},
                    "components": [],
                    "labels": ["label-1", "label-2"],
                    "reporter": {"name": "someone"},
                }
            })
        source_issue.fields.subtasks = [
            mock.MagicMock(
                key="FOO-2",
                id="2",
                raw={
                    "fields": {
                        "project": {"key": "FOO"},
                        "summary": "Fake issue 2",
                        "description": "Fake description",
                        "issuetype": {"name": "Fake-subtask-type", "subtask": True},
                        "components": [],
                        "labels": ["label-1", "label-2"],
                        "reporter": {"name": "someone"},
                    }
                }),
            mock.MagicMock(
                key="FOO-3",
                id="3",
                raw={
                    "fields": {
                        "project": {"key": "FOO"},
                        "summary": "Fake issue 3",
                        "description": "Fake description",
                        "issuetype": {"name": "Fake-subtask-type", "subtask": True},
                        "components": [],
                        "labels": ["label-1", "label-2"],
                        "reporter": {"name": "someone"},
                    }
                }),
        ]

        mock_jira = mock.MagicMock()
        mock_jira.create_issues.side_effect = lambda field_list: [{"error": None, "input_fields": fields.copy(), "issue": mock.MagicMock(raw={"fields": fields.copy()})} for fields in field_list]
        client = JIRAClient(mock_jira)
        client.get_issue = mock.MagicMock(side_effect=lambda key: next(filter(lambda issue: issue.key == key, source_issue.fields.subtasks)))
        client.clone_issue = mock.MagicMock()
        client.clone_issue.return_value = mock.MagicMock(id="42", raw={"fields": source_issue.raw["fields"].copy()})
        mock_fields_transform = mock.MagicMock(side_effect=lambda fields: fields)
        new_issues = client.clone_issue_with_subtasks(source_issue, "BAR", mock_fields_transform)
        self.assertEqual(new_issues[0], client.clone_issue.return_value)
        for new_subtask in new_issues[1:]:
            self.assertEqual(new_subtask.raw["fields"]["parent"]["id"], "42")
        mock_fields_transform.assert_called()
