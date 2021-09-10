from typing import Optional, Tuple, Callable, Dict, List, Any
from jira import JIRA, Issue
import logging

_LOGGER = logging.getLogger(__name__)


class JIRAClient:
    @classmethod
    def from_url(cls, server_url: str, basic_auth: Optional[Tuple[str, str]] = None):
        client = JIRA(server_url, basic_auth=basic_auth)
        return JIRAClient(client)

    def __init__(self, jira: JIRA) -> None:
        self._client = jira

    def get_issue(self, key) -> Issue:
        return self._client.issue(key)

    @classmethod
    def _copy_issue_fields(cls, fields: Dict[str, Any]):
        new_fields = {
            "project": {"key": fields["project"]["key"]},
            "summary": fields["summary"],
            "description": fields["description"] or "",
            "issuetype": {"name": fields["issuetype"]["name"]},
            "components": fields.get("components", []).copy(),
            "labels": fields.get("labels", []).copy(),
            "security": fields.get("security", {}).copy(),
            # "reporter": {"name": fields["reporter"]["name"]},
        }
        assignee = fields.get("assignee", None)
        if assignee:
            new_fields["assignee"] = {"name": assignee["name"]}
        if "parent" in fields:
            new_fields["parent"] = {"id": fields["parent"]["id"]}
        return new_fields

    def clone_issue(self, source_issue: Issue,
                    dest_project: Optional[str] = None,
                    reparent_to: Optional[str] = None,
                    fields_transform: Optional[Callable] = None,
                    create_link=True) -> Issue:
        # copy needed fields
        fields = self._copy_issue_fields(source_issue.raw["fields"])
        # override specific fields
        if dest_project:
            fields["project"] = {"key": dest_project}
        if reparent_to and source_issue.fields.issuetype.subtask:
            fields["parent"] = {"id": reparent_to}
        # apply fields_transform function if needed
        if fields_transform:
            fields = fields_transform(fields)
        _LOGGER.debug("Copying JIRA issue %s to project %s...",
                      source_issue.key, fields["project"]["key"])
        new_issue = self._client.create_issue(fields=fields)
        # create a link between the cloned and the original issue
        if create_link:
            self._client.create_issue_link("Cloners", new_issue, source_issue)
        _LOGGER.debug("Created JIRA issue %s: %s",
                      new_issue.key, new_issue.permalink())
        return new_issue

    def clone_issue_with_subtasks(self, source_issue: Issue,
                                  dest_project: Optional[str] = None,
                                  fields_transform: Optional[Callable] = None
                                  ) -> List[Issue]:
        new_issues = [self.clone_issue(
            source_issue, dest_project, fields_transform=fields_transform)]
        if source_issue.fields.subtasks:
            _LOGGER.debug("Cloning %d subtasks...",
                          len(source_issue.fields.subtasks))
            # refetch subtasks to populate all needed fields
            subtasks = [self.get_issue(subtask.key)
                        for subtask in source_issue.fields.subtasks]
            # populate field list
            field_list = [self._copy_issue_fields(subtask.raw["fields"])
                          for subtask in subtasks]
            # reparent
            for fields in field_list:
                fields["parent"] = {"id": new_issues[0].id}
            # apply fields_transform function to each list item
            if fields_transform:
                field_list = list(map(fields_transform, field_list))
            # bulk create issues
            results = self._client.create_issues(field_list)
            errors = []
            for r in results:
                if r.get("error"):
                    errors.append(f"Error creating issue {r['input_fields']['summary']}: {r.get('error')}")
                else:
                    new_issues.append(r["issue"])
            if errors:
                raise IOError(f"Failed to clone subtasks: {errors}")
            _LOGGER.debug("Cloned %d subtasks...",
                          len(source_issue.fields.subtasks))
        return new_issues
