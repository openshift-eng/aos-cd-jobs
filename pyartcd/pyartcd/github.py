import requests
from pyartcd.exceptions import GithubApiException
from ghapi.all import GhApi


# create_pr function is kept separate as the owner of the pull request URL has to be the upstream owner
# but with the token of the current repository owner
def create_pr(token: str, upstream_owner: str, repo: str, title: str, head: str, base: str, body: str,
              maintainer_can_modify=True) -> str:
    """
    Function to create a PR against an upstream repo
    :param token: Token of the current repo (where the head branch is)
    :param upstream_owner: The owner of the upstream repo
    :param repo: Name of the repo (same name)
    :param title: The title of the PR
    :param head: The head branch eg: ashwindasr/temp_branch
    :param base: The base branch to which we are creating the PR to eg: openshift-4.10
    :param body: The text body of the PR
    :param maintainer_can_modify: A flag to set maintainer edit permissions
    :return: The html link of the new PR generated
    """
    try:
        client = GhApi(owner=upstream_owner, repo=repo, token=token)
        response = client.pulls.create(
            title=title,
            head=head,
            base=base,
            body=body,
            maintainer_can_modify=maintainer_can_modify  # default set to true
        )
        return response['html_url']
    except Exception as e:
        raise GithubApiException(f"Could not create PR. Error: {repr(e)}")


class GithubAPI(GhApi):
    """
    This API extends ghapi: https://ghapi.fast.ai/
    """

    def __init__(self, owner, repo, token):
        super().__init__(owner, repo, token)
        self.owner = owner
        self.repo = repo

    def branch_exists(self, branch: str) -> bool:
        """
        Function to check if a branch exists in the current repo.
        :param branch: Name of the branch
        :return: bool
        """
        try:
            _ = self.get_branch(branch=branch)
            return True
        except IndexError:  # ghapi will throw an Index error if the branch does not exist
            return False

    def sync_with_upstream(self, branch: str) -> None:
        """
        Function to sync a branch in your GitHub forked repo with the corresponding upstream repo branch.
        This feature is not available in this version of ghapi, so defining new function
        https://docs.github.com/rest/reference/repos#sync-a-fork-branch-with-the-upstream-repository
        :param branch: The name of a branch on GitHub
        """
        json_data = {
            "branch": branch
        }
        url = f"{self.gh_host}/repos/{self.owner}/{self.repo}/merge-upstream"
        response = requests.post(url, headers=self.headers, json=json_data)

        if response.status_code != 200:
            raise GithubApiException(
                f"Could not sync with upstream. Error {response.status_code}: {response.json().get('message')}")

    def get_branch_sha(self, branch: str) -> str:
        """
        Returns the sha of the branch
        :param branch: The branch that we need the sha of
        :returns: The sha of that branch
        """
        try:
            branches = self.list_branches()
            for current_branch in branches:
                if current_branch['ref'] == f"refs/heads/{branch}":  # If this is the branch we are looking for
                    # Get the SHA of the base branch (needed for API to create a new branch)
                    sha = current_branch['object']['sha']
                    return sha
        except Exception as e:
            raise GithubApiException(f"Could not get the sha of the base branch. Error: {repr(e)}")

    def create_branch(self, base: str, new_branch_name: str) -> None:
        """
        Function to create a new branch from the given base branch.
        :param base: The base branch that we are creating the new branch off of
        :param new_branch_name: The name of the new branch to be created. Format "automation_{build_version}_{build_number}"
        :return: None
        """
        try:
            sha = self.get_branch_sha(base)
            _ = self.git.create_ref(ref=f"refs/heads/{new_branch_name}", sha=sha)
        except Exception as e:
            raise GithubApiException(
                f"Could not create new branch {new_branch_name} of off base {base}. Error: {repr(e)}")

    def get_file(self, file_name: str, branch="master") -> str:
        """
        To retrieve a file from the repository
        :param file_name: The name of the file we need to retrive
        :param branch: The branch that we need to get the file from. Default set to master
        :return: The file as string
        """
        try:
            url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{branch}/{file_name}"
            response = requests.get(url)
            return response.text
        except Exception as e:
            raise GithubApiException(
                f"Could not download file {file_name} from {self.owner}/{self.repo}. Error: {repr(e)}")

    def get_file_sha(self, file_name, branch="master") -> str:
        """
        Function to get the SHA of a file from a particular branch.
        :param file_name: The name of the file we need to get the branch from
        :param branch: The branch where the file is. Default set to master
        :return: The SHA value of the file
        """
        try:
            response = self.repos.get_content(path=file_name, ref=branch)
            return response['sha']
        except Exception as e:
            raise GithubApiException(f"Could not retrieve SHA for file {file_name}. Error: {repr(e)}")

    def push_change(self, branch: str, content: str, file_path, commit_message, git_author, git_email) -> None:
        """
        Push changes to repo
        :param branch: Name of the branch which has the file
        :param content: The updated content
        :param file_path: The file path in the branch
        :param commit_message: The commit message
        :param git_author: The name of the author to keep in the commit message
        :param git_email: The email ID of the git author
        :return: None
        """
        try:
            sha = self.get_file_sha(file_path, branch)
            _ = self.update_contents(
                path=file_path,
                message=commit_message,
                content=content,
                sha=sha,
                branch=branch,
                committer={
                    "name": git_author,
                    "email": git_email
                }
            )
        except Exception as e:
            raise GithubApiException(f"Could not push changes to branch {branch}. Error: {repr(e)}")
